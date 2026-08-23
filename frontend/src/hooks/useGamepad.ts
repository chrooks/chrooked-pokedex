import { useEffect, useRef } from "react";

/**
 * Physical-controller input, for the handheld this app is used on.
 *
 * Why the Gamepad API and not key events: Android sends the D-pad through as
 * arrow keys, but Chromium's Android keycode table has no mapping for
 * KEYCODE_BUTTON_A/B/X/Y/L1/R1 — those sit in a commented-out "unsupported"
 * block — so face buttons can never arrive as `keydown`. The API is the only
 * way to read them.
 *
 * Plain HTTP is fine: the secure-context restriction people associate with this
 * API shipped in Firefox, never in Chrome. Chromium's IDL carries no
 * [SecureContext] and insecure origins are only counted for telemetry.
 *
 * Two traps this deliberately avoids:
 *   * It never checks `mapping === "standard"`. AYN's vendor id is not in
 *     Chromium's mapping table, so the string comes back empty even though the
 *     canonical button indices are filled in correctly. Gating on it would mean
 *     silently never running.
 *   * It reads directions from the axes as well as the D-pad buttons, because
 *     whether a given pad reports its hat as buttons 12-15 or as an axis pair
 *     varies and is not worth detecting.
 */

/**
 * Named by ROLE, not by position — because on this hardware position is not
 * stable and role is.
 *
 * The W3C mapping is defined positionally (index 0 = bottom face button), but
 * the Thor reports by printed label instead. Probed on-device 2026-08-23: the
 * BOTTOM button is printed "B" and reports index 1, so index 0 is the button
 * printed "A", sitting on the right in Nintendo arrangement.
 *
 * That turns out not to matter, because the label convention is what stays put:
 *
 *   Nintendo style — "A" on the right, reports 0, means confirm.
 *   Xbox style     — "A" on the bottom, reports 0, means confirm.
 *
 * Index 0 is the confirm button and index 1 the cancel button in BOTH of the
 * device's Controller Style modes, so this mapping survives the user flipping
 * that setting. Naming these `south`/`east` would have documented a position
 * that is wrong here half the time.
 */
export type GamepadAction =
  | "up" | "down" | "left" | "right"
  | "confirm" | "cancel"
  | "l1" | "r1";

const BUTTON_INDEX: Record<GamepadAction, number> = {
  confirm: 0, cancel: 1, l1: 4, r1: 5,
  up: 12, down: 13, left: 14, right: 15,
};

const ACTIONS = Object.keys(BUTTON_INDEX) as GamepadAction[];

/** Only directions auto-repeat. A held "open detail" firing twice is never wanted. */
const REPEATABLE = new Set<GamepadAction>(["up", "down", "left", "right"]);
const REPEAT_DELAY_MS = 400;
const REPEAT_INTERVAL_MS = 90;
const AXIS_DEADZONE = 0.5;
const BUTTON_THRESHOLD = 0.5;

function isActionDown(pad: Gamepad, action: GamepadAction): boolean {
  const button = pad.buttons[BUTTON_INDEX[action]];
  if (button && (button.pressed || button.value > BUTTON_THRESHOLD)) return true;
  const [x = 0, y = 0] = pad.axes;
  if (action === "left") return x < -AXIS_DEADZONE;
  if (action === "right") return x > AXIS_DEADZONE;
  if (action === "up") return y < -AXIS_DEADZONE;
  if (action === "down") return y > AXIS_DEADZONE;
  return false;
}

/**
 * Poll connected gamepads and call `onAction` on each press.
 *
 * The API has no press events, only connect/disconnect, so polling is the only
 * option. The loop runs whenever the page is visible rather than only after a
 * `gamepadconnected` event: the browser withholds gamepad data until the first
 * user gesture, so that event does not arrive until a button is pressed — and
 * waiting for it would silently eat the very first press.
 *
 * Battery: requestAnimationFrame is not scheduled while the page is hidden, and
 * Blink stops sampling the OS then too, so a closed clamshell costs nothing.
 * The per-frame work is a scan of 10 indices.
 */
export function useGamepad(
  onAction: (action: GamepadAction) => void,
  isEnabled = true,
): void {
  // The callback lives in a ref so a re-render never restarts the loop, and a
  // held direction never re-renders the host.
  const actionRef = useRef(onAction);
  actionRef.current = onAction;

  useEffect(() => {
    if (!isEnabled) return;
    if (typeof navigator.getGamepads !== "function") return;

    const heldUntilRepeat = new Map<GamepadAction, number>();
    let rafId = 0;

    function poll() {
      rafId = requestAnimationFrame(poll);
      const now = performance.now();

      let pads: (Gamepad | null)[];
      try {
        pads = navigator.getGamepads();
      } catch {
        // SecurityError means a Permissions-Policy is blocking us — a real
        // misconfiguration. Stop rather than spin every frame forever.
        cancelAnimationFrame(rafId);
        rafId = 0;
        return;
      }

      for (const action of ACTIONS) {
        const down = pads.some((pad) => pad !== null && isActionDown(pad, action));
        if (!down) {
          heldUntilRepeat.delete(action);
          continue;
        }
        const repeatAt = heldUntilRepeat.get(action);
        if (repeatAt === undefined) {
          heldUntilRepeat.set(action, now + REPEAT_DELAY_MS);
          actionRef.current(action);
        } else if (REPEATABLE.has(action) && now >= repeatAt) {
          heldUntilRepeat.set(action, now + REPEAT_INTERVAL_MS);
          actionRef.current(action);
        }
      }
    }

    const start = () => {
      if (rafId === 0) rafId = requestAnimationFrame(poll);
    };
    const stop = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      heldUntilRepeat.clear();
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") stop();
      else start();
    };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [isEnabled]);
}
