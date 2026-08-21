"""Build the neutral per-Target snapshot from a Rejuvenation game folder.

The engine-aware sibling of ``snapshot.py`` / ``snapshot_essentials.py`` for the
Reborn-family engine. Rejuv's data is Ruby hash literals (MONHASH/MOVEHASH/
ABILHASH/TYPEHASH) compiled at boot — so instead of parsing 73k lines of Ruby
with regexes, this shells out to ``ruby`` and *evaluates* the definitions the
exact way the game's compiler does, preferring the ``patch/Definitions/`` delta
when present (the delta evals its base first, so the result is base ⊕ patch —
the applied truth). The dump comes back as JSON and is mapped to the same
neutral snapshot dict ``web/dex.py`` consumes.

Scope mirrors the Essentials snapshot's D4: species (base form only), abilities,
moves, and the 18×18 type chart. Evolution edges are deferred; the merge
``.get``-defaults them so omission renders cleanly.

Join key: ``nz.slug(<hash symbol>)``. A couple of Rejuv symbols differ from the
English-name slug (``VICEGRIP`` vs ``visegrip``) — those entries simply miss the
Ruleset overlay and render base values. ponytail: same accepted mismatch class
as the Essentials InternalName join.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from dataclasses import dataclass

from ..model.schema import STAT_KEYS
from ..seed import neutralize as nz
from .evolution import build_evolution_graph
from .essentials_evolution import essentials_method_label


@dataclass(frozen=True)
class _RejuvEvolution:
    """One outgoing edge, duck-typed to what ``build_evolution_graph`` reads."""

    target_species: str
    method: str
    param: str

SNAPSHOT_VERSION = "rejuv"

_BATTLE_TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug",
    "Ghost", "Steel", "Fire", "Water", "Grass", "Electric", "Psychic",
    "Ice", "Dragon", "Dark", "Fairy",
)

# Evaluates the (patched) definitions exactly like the game's compiler and dumps
# them as JSON. The patch delta evals its base file itself, so "patch if present,
# else base" always yields the applied state.
_DUMP_SCRIPT = r'''
require "json"

def load_def(name)
  patch = "patch/Definitions/#{name}"
  base = "Scripts/Rejuv/Definitions/#{name}"
  if File.exist?(patch)
    eval(File.read(patch), TOPLEVEL_BINDING)
  elsif File.exist?(base)
    eval(File.read(base), TOPLEVEL_BINDING)
  end
end

def puts(*args); end  # silence delta skip-guards; real output goes to STDOUT.write

%w[montext.rb movetext.rb abiltext.rb typetext.rb].each { |f| load_def(f) }

out = { "mons" => [], "moves" => {}, "abils" => {}, "types" => {} }
if defined?(MONHASH)
  MONHASH.each do |key, forms|
    next unless forms.is_a?(Hash)
    base = forms.values.first
    forms.each_with_index do |(form_name, form), i|
      next unless form.is_a?(Hash)
      # non-base forms inherit unset fields from the base form at compile time
      merged = i.zero? ? form : (base || {}).merge(form)
      evos = (merged[:evolutions] || []).map { |e|
        { "species" => e[:species], "form" => e[:form],
          "method" => e[:method].to_s, "parameter" => e[:parameter].to_s }
      }
      out["mons"] << {
        "key" => key, "form" => form_name, "base_form" => i.zero?, "form_index" => i,
        "evolutions" => evos,
        "name" => merged[:name], "dexnum" => merged[:dexnum],
        "type1" => merged[:Type1], "type2" => merged[:Type2],
        "abilities" => merged[:Abilities] || [], "hidden" => merged[:HiddenAbility],
        "stats" => merged[:BaseStats] || [], "moveset" => merged[:Moveset] || [],
      }
    end
  end
end
if defined?(MOVEHASH)
  MOVEHASH.each do |key, m|
    next unless m.is_a?(Hash)
    out["moves"][key] = {
      "name" => m[:name], "type" => m[:type], "category" => m[:category],
      "power" => m[:basedamage], "accuracy" => m[:accuracy], "pp" => m[:maxpp],
      "desc" => m[:desc],
      "flags" => %i[contact soundmove punchmove bitingmove sharpmove ballmove bombmove windmove pulsemove]
                   .select { |f| m[f] }.map(&:to_s),
    }
  end
end
if defined?(ABILHASH)
  ABILHASH.each do |key, a|
    next unless a.is_a?(Hash)
    out["abils"][key] = { "name" => a[:name], "desc" => a[:desc] }
  end
end
if defined?(TYPEHASH)
  TYPEHASH.each do |key, t|
    next unless t.is_a?(Hash)
    out["types"][key] = {
      "weaknesses" => t[:weaknesses] || [],
      "resistances" => t[:resistances] || [],
      "immunities" => t[:immunities] || [],
    }
  end
end
STDOUT.write(JSON.generate(out))
'''


class RejuvSnapshotError(Exception):
    """The ruby dump failed — carries the honest reason for a 500."""


def _dump(target: Path) -> dict[str, Any]:
    if shutil.which("ruby") is None:
        raise RejuvSnapshotError(
            "ruby is required to snapshot a Rejuvenation target and was not found on PATH."
        )
    proc = subprocess.run(
        ["ruby", "-e", _DUMP_SCRIPT], cwd=target, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RejuvSnapshotError(
            f"Rejuv definitions eval failed under {target}: {proc.stderr.strip()[:800]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RejuvSnapshotError(f"Rejuv dump was not valid JSON: {exc}") from exc


# Rejuv keeps move flags as loose symbol keys on the move hash (anything the
# compiler doesn't recognise lands in MoveData's @flags). These seven are the ones
# the neutral schema models — verified against the game's own exporter in
# `Scripts/DataObjects - Yeeters.rb`. Rejuv flags we don't model (magiccoat,
# powdermove, dancemove, ...) are dropped, same as every other reader.
_REJUV_FLAG_TO_NEUTRAL = {
    "contact": "contact",
    "soundmove": "sound",
    "punchmove": "punching",
    "bitingmove": "biting",
    "sharpmove": "slicing",
    # Rejuv splits ballistic in two — `:ballmove` (ball-shaped) and `:bombmove`.
    # Bulletproof checks both (Battle_Move.rb:165), so both fold to one neutral flag.
    "ballmove": "ballistic",
    "bombmove": "ballistic",
    "windmove": "wind",
    "pulsemove": "pulse",
}


# Form labels that carry no information and must not reach a display name.
# Rejuv gives ~975 of its ~1025 base forms the placeholder "Normal Form"; a
# handful (Rotom, Arceus) label form 0 with the species' own name instead.
_EMPTY_FORM_LABELS: frozenset[str] = frozenset({"normal form", "normal forme", ""})


def _display_name(name: str, form_label: str) -> str:
    """Species name with its form in parentheses, when the form actually names something.

    Labelling only non-base forms leaves the *first* form of a genuinely
    multi-form species bare — Rejuv's form 0 for Deerling is "Spring Form", so
    Spring Deerling rendered as plain "Deerling" beside its three labelled
    siblings. Keying on the label instead of the base-form flag labels all four,
    and still leaves single-form species (label "Normal Form") untouched.
    """
    label = form_label.strip()
    if label.lower() in _EMPTY_FORM_LABELS or label == name:
        return name
    return f"{name} ({label})"


def _neutral_type(sym: str | None) -> str | None:
    if not sym or sym == "QMARKS":
        return None
    return sym.capitalize()


def build_snapshot_rejuv(target: Path) -> dict[str, Any]:
    """Neutral snapshot of a Rejuv game (base ⊕ patch), same shape as the others."""
    raw = _dump(Path(target))

    moves: dict[str, dict[str, Any]] = {}
    for sym, m in raw["moves"].items():
        cid = nz.slug(sym)
        moves[cid] = {
            "chrooked_id": cid,
            "name": m.get("name") or sym.capitalize(),
            "aka": {},
            "type": _neutral_type(m.get("type")) or "",
            "category": (m.get("category") or "").lower(),
            "power": m.get("power"),
            "accuracy": m.get("accuracy"),
            "pp": m.get("pp"),
            "description": (m.get("desc") or "").strip(),
            # dict.fromkeys dedupes (ball+bomb both fold to `ballistic`) order-stably.
            "flags": list(dict.fromkeys(
                _REJUV_FLAG_TO_NEUTRAL[f]
                for f in m.get("flags") or []
                if f in _REJUV_FLAG_TO_NEUTRAL
            )),
        }

    abilities: dict[str, dict[str, Any]] = {}
    for sym, a in raw["abils"].items():
        cid = nz.slug(sym)
        abilities[cid] = {
            "chrooked_id": cid,
            "name": a.get("name") or sym.capitalize(),
            "description": (a.get("desc") or "").strip(),
            "aka": {},
        }

    species: dict[str, dict[str, Any]] = {}
    for index, mon in enumerate(raw["mons"], start=1):
        # Base form keeps the plain slug (joins the Ruleset overlay); every other
        # form is its own entry — Rejuv-original content (Aevian forms, megas)
        # renders even though the Ruleset never names it. Values come from the
        # patched eval, so overridden forms are already post-patch truth.
        cid = nz.slug(mon["key"])
        form_label = mon.get("form") or ""
        if not mon.get("base_form", True):
            cid = f"{cid}--{nz.slug(form_label)}"
        types = [t for t in (_neutral_type(mon.get("type1")), _neutral_type(mon.get("type2"))) if t]
        listed = mon.get("abilities") or []
        stats_raw = mon.get("stats") or []
        learnset = []
        for pair in mon.get("moveset") or []:
            if not (isinstance(pair, list) and len(pair) == 2):
                continue
            move_id = nz.slug(str(pair[1]))
            display = moves.get(move_id, {}).get("name") or str(pair[1]).capitalize()
            learnset.append({"level": pair[0], "move": display, "move_id": move_id})
        species[cid] = {
            # The game's own battler art: Graphics/Battlers/<species>/<form>.png
            "sprite": {"folder": nz.slug(mon["key"]), "form": mon.get("form_index", 0)},
            "dex": mon.get("dexnum") or index,
            "chrooked_id": cid,
            # Rejuv's own form label ("Spring Form", "Galarian Form"). Carried so the
            # Ruleset overlay can be rekeyed onto form entries — Rejuv slugs a form
            # `<base>--<label>` while the Ruleset names it `<base><suffix>`.
            "form": form_label,
            "name": _display_name(
                mon.get("name") or str(mon["key"]).capitalize(), form_label
            ),
            "types": types,
            "abilities": {
                "primary": listed[0] if listed else None,
                "secondary": listed[1] if len(listed) > 1 else None,
                "hidden": mon.get("hidden"),
            },
            "stats": {
                key: stats_raw[i]
                for i, key in enumerate(STAT_KEYS)
                if i < len(stats_raw) and isinstance(stats_raw[i], int)
            },
            "learnset": learnset,
        }

    # Evolution edges: sources/targets are entry ids; a `form:` index on the
    # edge routes to that form's entry (Aevian lines evolve within the family),
    # defaulting to the base form. Reuses the shared invert+resolve transform.
    entry_by_form: dict[tuple[str, int], str] = {}
    for mon in raw["mons"]:
        base_cid = nz.slug(mon["key"])
        cid = base_cid if mon.get("base_form", True) else f"{base_cid}--{nz.slug(mon.get('form') or '')}"
        entry_by_form[(base_cid, mon.get("form_index", 0))] = cid

    forward: dict[str, list[_RejuvEvolution]] = {}
    for mon in raw["mons"]:
        base_cid = nz.slug(mon["key"])
        source_cid = entry_by_form[(base_cid, mon.get("form_index", 0))]
        edges = []
        for evo in mon.get("evolutions") or []:
            target_base = nz.slug(str(evo["species"]))
            form = evo.get("form")
            # Engine rule (Evolution.rb getEvolutionForm): an edge without a
            # form: index keeps the evolving mon's own form — Icy Aevian
            # Sandygast becomes Icy Aevian Palossand. Fall back to the target's
            # base form when that form index does not exist on the target.
            if not isinstance(form, int):
                form = mon.get("form_index", 0)
            target_cid = entry_by_form.get(
                (target_base, form),
                entry_by_form.get((target_base, 0)),
            )
            if target_cid is None or target_cid not in species:
                continue
            edges.append(_RejuvEvolution(target_cid, evo.get("method") or "", evo.get("parameter") or ""))
        if edges:
            forward[source_cid] = edges

    def _resolver(cid: str):
        entry = species.get(cid)
        return (cid, entry["name"], entry["dex"]) if entry else None

    graph = build_evolution_graph(forward, _resolver, labeler=essentials_method_label)
    for cid, entry in species.items():
        edges = graph.get(cid)
        entry["evolution"] = edges["evolution"] if edges else None
        entry["evolves_into"] = edges["evolves_into"] if edges else []
        entry["fully_evolved"] = cid not in forward

    chart: list[dict[str, Any]] = []
    overrides: dict[str, dict[str, float]] = {}
    for defender_sym, buckets in raw["types"].items():
        defender = _neutral_type(defender_sym)
        if defender is None:
            continue
        cell: dict[str, float] = {}
        for bucket, multiplier in (("weaknesses", 2.0), ("resistances", 0.5), ("immunities", 0.0)):
            for attacker_sym in buckets.get(bucket, []):
                attacker = _neutral_type(attacker_sym)
                if attacker:
                    cell[attacker] = multiplier
        overrides[defender] = cell
    if overrides:
        for attacker in _BATTLE_TYPES:
            for defender in _BATTLE_TYPES:
                chart.append({
                    "attacker": attacker,
                    "defender": defender,
                    "multiplier": overrides.get(defender, {}).get(attacker, 1.0),
                })
        chart.sort(key=lambda c: (c["attacker"], c["defender"]))

    return {
        "version": SNAPSHOT_VERSION,
        "species": species,
        "abilities": abilities,
        "moves": moves,
        "type_chart": chart,
    }
