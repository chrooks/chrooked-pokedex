/* The battlefield target picker + its read-only mini glyph.

   TargetGridField renders the standard triple-battle diagram (three foes over
   user + two allies) with the current preset's pattern lit. Clicking a battler
   snaps to the nearest legal preset (the Ruleset stores a closed enum — see
   lib/moveTargets); the select beside it lists the presets directly. Both drive
   the same `value`, so they can never disagree.

   TargetGlyph is the dense-table rendering: the same six slots as dots. */

import {
  MOVE_TARGETS,
  SLOT_ROLE,
  TARGET_SLOTS,
  patternOf,
  snapTarget,
  type TargetSlot,
} from "../lib/moveTargets";
import "./target-grid.css";

const ROLE_LABEL: Record<"foe" | "user" | "ally", string> = {
  foe: "Foe",
  user: "User",
  ally: "Ally",
};

/** "pick 1" / "random" / "side" — the qualifier chip next to the caption; each
    and varies need no chip (the lit set / the caption says it all). */
const KIND_CHIP: Partial<Record<ReturnType<typeof patternOf>["kind"], string>> = {
  choose: "pick 1",
  random: "random",
  field: "side",
};

type FieldProps = {
  /** Base element id — the select gets `${id}-select`, slots `${id}-slot-f0`… */
  id: string;
  value: string;
  onChange: (target: string) => void;
};

export function TargetGridField({ id, value, onChange }: FieldProps) {
  const pattern = patternOf(value);
  const lit = new Set<TargetSlot>(pattern.slots);
  const foeBand = pattern.kind === "field" && lit.has("f0");
  const userBand = pattern.kind === "field" && lit.has("u");

  const rows: { slots: TargetSlot[]; band: boolean }[] = [
    { slots: ["f0", "f1", "f2"], band: foeBand },
    { slots: ["u", "a1", "a2"], band: userBand },
  ];

  return (
    <div className="tgrid-field" id={id}>
      <div className="tgrid" role="group" aria-label="Target pattern — click a battler to change it">
        {rows.map(({ slots, band }, i) => (
          <div key={i} className="tgrid__row" data-band={band || undefined}>
            {slots.map((slot) => {
              const on = lit.has(slot);
              const role = SLOT_ROLE[slot];
              return (
                <button
                  key={slot}
                  type="button"
                  id={`${id}-slot-${slot}`}
                  className="tgrid__slot"
                  data-role={role}
                  data-on={on || undefined}
                  data-kind={on ? pattern.kind : undefined}
                  aria-pressed={on}
                  aria-label={`${ROLE_LABEL[role]}${on ? ", targeted" : ", not targeted"}`}
                  onClick={() => onChange(snapTarget(value, slot))}
                >
                  {ROLE_LABEL[role]}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div className="tgrid-side">
        <select
          id={`${id}-select`}
          className="field__select"
          aria-label="Target preset"
          value={MOVE_TARGETS.includes(value as (typeof MOVE_TARGETS)[number]) ? value : "selected"}
          onChange={(e) => onChange(e.target.value)}
        >
          {MOVE_TARGETS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <p className="tgrid__caption">
          {KIND_CHIP[pattern.kind] && (
            <span className="tgrid__chip mono">{KIND_CHIP[pattern.kind]}</span>
          )}
          {pattern.caption}
        </p>
      </div>
    </div>
  );
}

/** The table/detail mini glyph: six dots, lit per the preset's pattern. Kind is
    carried by dot shape (each = filled, choose/random = hollow ring, field =
    the row's band) so the pattern survives grayscale. */
export function TargetGlyph({ target }: { target: string }) {
  const pattern = patternOf(target);
  const lit = new Set<TargetSlot>(pattern.slots);
  return (
    <span
      className="tglyph"
      data-kind={pattern.kind}
      role="img"
      aria-label={`Target: ${target} — ${pattern.caption}`}
      title={`${target} — ${pattern.caption}`}
    >
      {TARGET_SLOTS.map((slot) => (
        <span
          key={slot}
          className="tglyph__dot"
          data-role={SLOT_ROLE[slot]}
          data-on={lit.has(slot) || undefined}
        />
      ))}
    </span>
  );
}
