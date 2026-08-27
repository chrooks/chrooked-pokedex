import { useSyncExternalStore } from "react";

/**
 * Subscribe to a CSS media query.
 *
 * `useSyncExternalStore` rather than useState+useEffect: the matcher IS an
 * external store, and this shape reads the value during render instead of
 * after a commit, so the first paint is already correct — no flash of the
 * desktop shell before the compact one takes over.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = (onChange: () => void) => {
    const list = window.matchMedia(query);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  };
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false, // server/no-DOM: assume the roomy shell
  );
}

/**
 * The shell is "compact" when the viewport cannot afford the desktop chrome.
 *
 * Height is the real constraint on the handheld this was built for: an AYN Thor
 * in landscape is 833x468 CSS px, so it clears every conventional width
 * breakpoint while having barely 400px of height once the browser's address bar
 * is subtracted. A width-only rule would leave it on the desktop layout, which
 * is exactly the bug this replaced. Width is still checked so genuine phones
 * get the same treatment.
 *
 * Keep this threshold in sync with the compact media block in
 * device-frame.css; the CSS handles styling, this handles the two places where
 * markup itself has to move. They are one decision expressed twice, and letting
 * them drift is not a cosmetic bug: the CSS collapsed the rail to 52px while
 * this still rendered the full-width search and filters inside it, so they
 * spilled out over the page (2026-08-27).
 *
 * The coarse-pointer clause exists because a landscape handheld (1024x640)
 * clears both of the first two thresholds and would otherwise get the full
 * desktop chrome — a 128px two-row header and a 232px labeled rail.
 */
export const COMPACT_SHELL_QUERY =
  "(max-height: 620px), (max-width: 860px), (pointer: coarse) and (max-width: 1400px)";

export function useCompactShell(): boolean {
  return useMediaQuery(COMPACT_SHELL_QUERY);
}
