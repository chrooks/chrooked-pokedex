/* Track the observed inner size (width + height) of an element via a callback
   ref + ResizeObserver, so observation starts the moment the node mounts (no
   null-guard race). Mirrors DexGrid's useElementWidth, but reports both axes —
   the type chart sizes its cells to fit BOTH the container's width and height. */

import { useCallback, useRef, useState } from "react";

export interface Box {
  width: number;
  height: number;
}

export function useFitBox(): {
  box: Box;
  measureRef: (node: HTMLElement | null) => void;
} {
  const [box, setBox] = useState<Box>({ width: 0, height: 0 });
  const observerRef = useRef<ResizeObserver | null>(null);

  const measureRef = useCallback((node: HTMLElement | null) => {
    observerRef.current?.disconnect();
    if (node === null) {
      return;
    }
    const rect = node.getBoundingClientRect();
    setBox({ width: rect.width, height: rect.height });
    observerRef.current = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setBox({ width, height });
    });
    observerRef.current.observe(node);
  }, []);

  return { box, measureRef };
}
