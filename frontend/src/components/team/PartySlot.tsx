import { useMemo } from "react";
import type { DexEntry } from "../../types";
import { hasTypeModifier } from "../../lib/abilityTypeModifiers";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";

type Props = {
  entry: DexEntry;
  ability: string | null;
  index: number;
  onRemove: () => void;
  onAbility: (ability: string | null) => void;
  /** Open this mon's profile (the dex detail ledger). */
  onOpen: () => void;
  backdropTargetId: string | null;
};

/** The mon's distinct abilities (primary/secondary/hidden deduped), each flagged
    for whether it alters type matchups — Marill's doubled "Huge Power" collapses
    to one entry, and only Levitate-style abilities carry `alters`. */
function abilityOptions(entry: DexEntry): { name: string; alters: boolean }[] {
  const seen = new Set<string>();
  const options: { name: string; alters: boolean }[] = [];
  for (const name of [entry.abilities.primary, entry.abilities.secondary, entry.abilities.hidden]) {
    if (name && !seen.has(name)) {
      seen.add(name);
      options.push({ name, alters: hasTypeModifier(name) });
    }
  }
  return options;
}

/**
 * One party card: sprite, name, type chips, a remove control, and — only when
 * one of the mon's abilities would actually change a matchup — an ability
 * selector. All abilities are offered; the matchup-altering ones are marked so
 * the choice's consequence is visible.
 */
export function PartySlot({ entry, ability, index, onRemove, onAbility, onOpen, backdropTargetId }: Props) {
  const options = useMemo(() => abilityOptions(entry), [entry]);
  const hasAltering = options.some((option) => option.alters);
  const selectId = `party-slot-ability-${index}`;

  return (
    <li className="party-slot" id={`party-slot-${index}`}>
      <button
        type="button"
        className="party-slot__remove"
        id={`party-slot-remove-${index}`}
        aria-label={`Remove ${entry.name} from team`}
        title={`Remove ${entry.name}`}
        onClick={onRemove}
      >
        ✕
      </button>

      <button
        type="button"
        className="party-slot__open"
        id={`party-slot-open-${index}`}
        aria-label={`Open ${entry.name} profile`}
        title={`Open ${entry.name}`}
        onClick={onOpen}
      >
        <span className="party-slot__sprite">
          <DexSprite
            chrookedId={entry.chrooked_id}
            dex={entry.dex}
            name={entry.name}
            backdropTargetId={backdropTargetId}
            size={64}
          />
        </span>
        <span className="party-slot__name">{entry.name}</span>
      </button>

      <span className="party-slot__types">
        {entry.types.map((type) => (
          <TypeChip key={type} type={type} variant="full" />
        ))}
      </span>

      {hasAltering && (
        <label className="party-slot__ability" htmlFor={selectId}>
          <span className="party-slot__ability-label">Ability</span>
          <select
            id={selectId}
            className="party-slot__ability-select"
            value={ability ?? ""}
            onChange={(event) => onAbility(event.target.value === "" ? null : event.target.value)}
          >
            <option value="">Base typing</option>
            {options.map((option) => (
              <option key={option.name} value={option.name}>
                {option.name}
                {option.alters ? " ★" : ""}
              </option>
            ))}
          </select>
        </label>
      )}
    </li>
  );
}
