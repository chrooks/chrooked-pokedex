import { memo } from "react";
import type { DexEntry } from "../types";
import { dexLabel, isEdited } from "../lib/format";
import { TypeChip } from "./TypeChip";
import { EditedLed } from "./EditedLed";
import { DexSprite } from "./DexSprite";
import "./dex-cell.css";

type Props = {
  entry: DexEntry;
  isSelected: boolean;
  onOpen: (chrookedId: string) => void;
  backdropTargetId?: string | null;
};

/** One species in the grid: sprite, mono dex №, name, type codes, edited LED. */
function DexCellBase({ entry, isSelected, onOpen, backdropTargetId }: Props) {
  const edited = isEdited(entry);
  const label =
    `${entry.name}, ${dexLabel(entry.dex)}` + (edited ? ", edited by the Ruleset" : "");
  return (
    <button
      type="button"
      className="dex-cell"
      data-edited={edited}
      data-selected={isSelected}
      aria-haspopup="dialog"
      aria-expanded={isSelected}
      aria-label={label}
      onClick={() => onOpen(entry.chrooked_id)}
    >
      <span className="dex-cell__corner mono">{dexLabel(entry.dex)}</span>
      <EditedLed on={edited} />
      <DexSprite
        chrookedId={entry.chrooked_id}
        dex={entry.dex}
        name={entry.name}
        backdropTargetId={backdropTargetId}
        size={72}
      />
      <span className="dex-cell__name">{entry.name}</span>
      <span className="dex-cell__types">
        {entry.types.map((type) => (
          <TypeChip key={type} type={type} variant="code" />
        ))}
      </span>
    </button>
  );
}

/** Cells re-render only when their entry or selection changes (1451-cell grid). */
export const DexCell = memo(DexCellBase);
