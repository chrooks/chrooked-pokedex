import { memo, useState } from "react";
import type { DexEntry } from "../types";
import { dexLabel, isEdited } from "../lib/format";
import { spriteUrl } from "../lib/sprites";
import { TypeChip } from "./TypeChip";
import { EditedLed } from "./EditedLed";
import "./dex-cell.css";

type Props = {
  entry: DexEntry;
  isSelected: boolean;
  onOpen: (chrookedId: string) => void;
};

/** One species in the grid: sprite, mono dex №, name, type codes, edited LED. */
function DexCellBase({ entry, isSelected, onOpen }: Props) {
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
      <Sprite chrookedId={entry.chrooked_id} dex={entry.dex} name={entry.name} />
      <span className="dex-cell__name">{entry.name}</span>
      <span className="dex-cell__types">
        {entry.types.map((type) => (
          <TypeChip key={type} type={type} variant="code" />
        ))}
      </span>
    </button>
  );
}

function Sprite({
  chrookedId,
  dex,
  name,
}: {
  chrookedId: string;
  dex: number | null;
  name: string;
}) {
  const url = spriteUrl(chrookedId, dex);
  const [failed, setFailed] = useState(false);

  if (url === null || failed) {
    return (
      <span className="dex-cell__sprite dex-cell__sprite--missing mono" aria-hidden="true">
        {dex ?? "—"}
      </span>
    );
  }
  return (
    <img
      className="dex-cell__sprite"
      src={url}
      alt={name}
      loading="lazy"
      decoding="async"
      width={72}
      height={72}
      onError={() => setFailed(true)}
    />
  );
}

/** Cells re-render only when their entry or selection changes (1451-cell grid). */
export const DexCell = memo(DexCellBase);
