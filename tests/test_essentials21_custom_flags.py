"""Kicking, Hammer and Piercing reach an Essentials 21 game's move data (mjolnir NV-7).

They are custom flags: Essentials keeps Flags as free strings and only tests the
ones it knows, and the ports in references/essentials21-harness/ (striker,
martialartist, sledgehammer, hammerfist, impale) read them. The Ruleset owns them,
like every modeled flag: apply adds them, removes them when the Ruleset drops
them, and never touches the engine's own unmodeled flags.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials import pbs_edit
from chrooked_pokedex.appliers.essentials.creation import create_owned_content
from chrooked_pokedex.appliers.essentials.move_apply import apply_moves
from chrooked_pokedex.appliers.essentials.resolution import build_resolution_map
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import MoveDef
from chrooked_pokedex.report import ApplyReport

pytestmark = pytest.mark.unit

_MOVES = """\
[HIGHJUMPKICK]
Name = High Jump Kick
Type = FIGHTING
Category = Physical
Power = 130
Accuracy = 90
TotalPP = 10
Target = NearOther
FunctionCode = CrashDamageIfFailsUnusableInGravity
Flags = Contact,CanProtect,CanMirrorMove
Description = The user jumps up high, then strikes with a knee kick.
[HAMMERARM]
Name = Hammer Arm
Type = FIGHTING
Category = Physical
Power = 100
Accuracy = 90
TotalPP = 10
Target = NearOther
FunctionCode = LowerUserSpeed1
Flags = Contact,CanProtect,CanMirrorMove,Punching,Kicking
Description = The user swings and hits with its strong, heavy fist.
"""


def _target(tmp_path: Path) -> Path:
    target = tmp_path / "essentials"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (pbs / "moves.txt").write_text(_MOVES, encoding="utf-8")
    (pbs / "pokemon.txt").write_text(
        "[NUMEL]\nName = Numel\nTypes = FIRE,GROUND\nBaseStats = 60,60,40,35,65,45\n"
        "Abilities = OBLIVIOUS\nMoves = 1,TACKLE\n", encoding="utf-8")
    (pbs / "abilities.txt").write_text("[OBLIVIOUS]\nName = Oblivious\n", encoding="utf-8")
    (pbs / "types.txt").write_text("[FIGHTING]\nName = Fighting\n[ROCK]\nName = Rock\n", encoding="utf-8")
    return target


def _flags(target: Path, symbol: str) -> list[str]:
    text = (target / "PBS" / "moves.txt").read_text(encoding="utf-8")
    span = pbs_edit.find_section(text, symbol)
    return pbs_edit.get_field(text[span[0]:span[1]], "Flags").split(",")


def _move(name, cid, flags, **kw):
    return MoveDef(name=name, chrooked_id=cid, type="Fighting", category="physical",
                   power=kw.pop("power", 100), aka={"essentials": cid.upper()}, flags=flags, **kw)


def test_existing_move_gains_its_custom_flag_and_keeps_engine_flags(tmp_path):
    target = _target(tmp_path)
    ruleset = Ruleset(moves={"highjumpkick": _move("High Jump Kick", "highjumpkick", ("contact", "kicking"), power=130)})
    report = ApplyReport()

    apply_moves(target, ruleset, build_resolution_map(target, ruleset), report)

    flags = _flags(target, "HIGHJUMPKICK")
    assert "Kicking" in flags
    assert {"Contact", "CanProtect", "CanMirrorMove"} <= set(flags)  # engine flags survive
    assert not any("flag:kicking" in f for e in report.entries for f in e.partial_fields)


def test_custom_flag_the_ruleset_drops_is_removed(tmp_path):
    # HAMMERARM carries a stray Kicking; the Ruleset says punching + hammer.
    target = _target(tmp_path)
    ruleset = Ruleset(moves={"hammerarm": _move("Hammer Arm", "hammerarm", ("contact", "punching", "hammer"))})

    apply_moves(target, ruleset, build_resolution_map(target, ruleset), ApplyReport())

    flags = _flags(target, "HAMMERARM")
    assert "Hammer" in flags and "Punching" in flags
    assert "Kicking" not in flags


def test_created_move_writes_custom_flags_without_partial(tmp_path):
    target = _target(tmp_path)
    move = MoveDef(name="Rock Drill", chrooked_id="rockdrill", type="Rock", category="physical",
                   power=80, accuracy=100, aka={"essentials": "ROCKDRILL"}, flags=("contact", "piercing"))
    ruleset = Ruleset(moves={"rockdrill": move})
    report = ApplyReport()

    create_owned_content(target, ruleset, build_resolution_map(target, ruleset), report)

    assert "Piercing" in _flags(target, "ROCKDRILL")
    entry = next(e for e in report.entries if e.chrooked_id == "rockdrill")
    assert not any(f.startswith("flag:") for f in entry.partial_fields)
