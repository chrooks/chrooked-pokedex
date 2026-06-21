import { useState } from "react";
import { spriteUrl, targetSpriteUrl } from "../lib/sprites";
import "./dex-cell.css";

type Props = {
  chrookedId: string;
  dex: number | null;
  name: string;
  backdropTargetId?: string | null;
  size?: number;
};

/**
 * Shared sprite renderer used across the dex grid, table, detail ledger, and
 * evolution section.  Falls back through three tiers: target-local file →
 * PokéAPI CDN → placeholder number.  The clip box shows only frame 0 of
 * Essentials animated sprite-sheets; plain square CDN sprites fill the box
 * exactly (no-op).
 */
export function DexSprite({
  chrookedId,
  dex,
  name,
  backdropTargetId,
  size = 72,
}: Props) {
  const targetUrl =
    backdropTargetId != null ? targetSpriteUrl(backdropTargetId, dex) : null;
  const cdnUrl = spriteUrl(chrookedId, dex);

  // Fallback chain: target file → CDN → placeholder.
  // `targetFailed` tracks whether the target endpoint 404ed so we step to CDN.
  // `cdnFailed` tracks whether CDN also failed so we step to the placeholder.
  const [targetFailed, setTargetFailed] = useState(false);
  const [cdnFailed, setCdnFailed] = useState(false);

  // Pick the active src: target (when available and not yet failed) → CDN → null.
  const src = !targetFailed && targetUrl !== null ? targetUrl : cdnUrl;

  if (src === null || cdnFailed) {
    return (
      <span
        id={`dex-sprite-missing-${chrookedId}`}
        className="dex-cell__sprite dex-cell__sprite--missing mono"
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        {dex ?? "—"}
      </span>
    );
  }

  const handleError = () => {
    if (!targetFailed && targetUrl !== null && src === targetUrl) {
      // Step 1 → 2: target file not found, try CDN.
      setTargetFailed(true);
    } else {
      // Step 2 → 3: CDN also failed, show placeholder.
      setCdnFailed(true);
    }
  };

  // Essentials front battlers are animated sprite-sheets: a single row of
  // square frames. The box clips to one cell-square so only frame 0 shows; the
  // img scales by height so each square frame becomes one box-width. A plain
  // square (PokéAPI CDN) fills the box exactly, so this is a no-op for it.
  return (
    <span
      id={`dex-sprite-box-${chrookedId}`}
      className="dex-cell__sprite-box"
      style={{ width: size, height: size }}
    >
      <img
        id={`dex-sprite-img-${chrookedId}`}
        className="dex-cell__sprite-img"
        src={src}
        alt={name}
        loading="lazy"
        decoding="async"
        style={{ height: size }}
        onError={handleError}
      />
    </span>
  );
}
