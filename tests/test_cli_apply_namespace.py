"""A CLI apply must compose the Target Override namespace like the web apply does.

Found 2026-10-22 on Nova: ``targets.json`` bound the Target to namespace ``nova``,
the CLI printed "Target namespace 'nova'", loaded that slug's holds/edits/mods —
and applied the *base* Ruleset, so the Nova-only Poipole override never reached
``pokemon.txt``. ``web/targets.py`` composes ``base ⊕ overlay`` first; the CLI did not.
"""

from __future__ import annotations

from pathlib import Path

from chrooked_pokedex.cli import _run_apply


def _essentials_target(tmp_path: Path) -> Path:
    target = tmp_path / "game"
    pbs = target / "PBS"
    pbs.mkdir(parents=True)
    (target / "Data").mkdir()
    (target / "Data" / "species.dat").write_bytes(b"\x04\x08")
    (pbs / "pokemon.txt").write_text(
        "[POIPOLE]\nName = Poipole\nTypes = POISON\nBaseStats = 67,73,67,73,73,67\n"
        "Abilities = BEASTBOOST\nMoves = 1,PECK\n",
        encoding="utf-8",
    )
    (pbs / "moves.txt").write_text("[PECK]\nName = Peck\n", encoding="utf-8")
    (pbs / "abilities.txt").write_text("[BEASTBOOST]\nName = Beast Boost\n", encoding="utf-8")
    (pbs / "types.txt").write_text(
        "[POISON]\nName = Poison\n[DRAGON]\nName = Dragon\n", encoding="utf-8"
    )
    return target


def _ruleset_with_namespace(tmp_path: Path) -> Path:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    ns = root / "targets" / "nova"
    (ns / "species").mkdir(parents=True)
    (ns / "meta.yaml").write_text("engine: essentials\nlabel: Nova\nslug: nova\n")
    (ns / "species" / "poipole.yaml").write_text(
        "name: Poipole\nchrooked_id: poipole\naka: { essentials: POIPOLE }\n"
        "types: [Poison, Dragon]\n",
        encoding="utf-8",
    )
    return root


def test_cli_apply_composes_target_override_namespace(tmp_path, capsys):
    target = _essentials_target(tmp_path)
    ruleset_dir = _ruleset_with_namespace(tmp_path)

    rc = _run_apply(
        target, "essentials", "species", ruleset_dir,
        force=True, dialect="essentials21", slug="nova", sync=False,
    )

    assert rc == 0
    text = (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8")
    assert "Types = POISON,DRAGON" in text
    assert "Composed Target Override 'nova'" in capsys.readouterr().out


def test_cli_apply_without_namespace_leaves_base_only(tmp_path):
    # Same files, no slug: the override must not leak into a base apply.
    target = _essentials_target(tmp_path)
    ruleset_dir = _ruleset_with_namespace(tmp_path)

    rc = _run_apply(
        target, "essentials", "species", ruleset_dir,
        force=True, dialect="essentials21", slug=None, sync=False,
    )

    assert rc == 0
    text = (target / "PBS" / "pokemon.txt").read_text(encoding="utf-8")
    assert "Types = POISON\n" in text
    assert "DRAGON" not in text
