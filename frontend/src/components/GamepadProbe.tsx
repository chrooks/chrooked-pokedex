import { useEffect, useState } from "react";
import "./gamepad-probe.css";

/**
 * A live readout of what the controller is actually sending. Open the Dex with
 * `?gamepad=probe` on the handheld, press each control, and read the indices.
 *
 * This exists because the mapping cannot be verified from a development
 * machine: no gamepad dump has been published for this hardware, and three
 * things genuinely vary — which index the BOTTOM face button reports (the
 * device's Controller Style setting swaps it), whether the D-pad arrives as
 * buttons 12-15 or as an axis pair, and whether `mapping` comes back empty
 * because the vendor id is missing from Chromium's table.
 *
 * Deliberately self-contained: it runs its own poll rather than sharing
 * useGamepad, so a probe session can never perturb the real input path.
 */
export function GamepadProbe() {
  const [pads, setPads] = useState<string[]>([]);
  const [pressed, setPressed] = useState<number[]>([]);
  const [axes, setAxes] = useState<string[]>([]);
  const [seen, setSeen] = useState<Set<number>>(new Set());

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      let list: (Gamepad | null)[] = [];
      try {
        list = navigator.getGamepads();
      } catch {
        setPads(["getGamepads() threw — a Permissions-Policy is blocking it"]);
        return;
      }
      const live = list.filter((pad): pad is Gamepad => pad !== null);
      setPads(live.map((pad) => `${pad.id} · mapping="${pad.mapping}" · ${pad.buttons.length} buttons`));
      const down = live.flatMap((pad) =>
        pad.buttons.map((button, index) => (button.pressed ? index : -1)).filter((index) => index >= 0),
      );
      setPressed(down);
      if (down.length > 0) {
        setSeen((was) => {
          const next = new Set(was);
          down.forEach((index) => next.add(index));
          return next;
        });
      }
      setAxes(live.flatMap((pad) => pad.axes.map((axis) => axis.toFixed(2))));
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const shell = document.querySelector("#app-shell")?.getAttribute("data-compact");

  return (
    <div className="gp-probe" id="gamepad-probe">
      <p className="gp-probe__head mono">DEVICE PROBE</p>
      {/* The layout numbers matter as much as the buttons: the compact shell is
          driven by viewport size, and a screen that reports something other
          than expected is the difference between a tidy strip and an
          overlapping one. Read these off the device rather than guessing. */}
      <p className="gp-probe__row mono">
        <span className="gp-probe__label">VIEWPORT</span>
        <span className="gp-probe__value">
          {window.innerWidth} x {window.innerHeight} @ {window.devicePixelRatio}x
          {shell === "true" ? " · compact" : " · DESK"}
        </span>
      </p>
      {pads.length === 0 ? (
        <p className="gp-probe__hint">
          No controller seen yet. Press any button — the browser withholds
          gamepad data until the first press.
        </p>
      ) : (
        pads.map((label) => (
          <p key={label} className="gp-probe__id mono">
            {label}
          </p>
        ))
      )}
      <p className="gp-probe__row mono">
        <span className="gp-probe__label">DOWN NOW</span>
        <span className="gp-probe__value">{pressed.length ? pressed.join(" · ") : "—"}</span>
      </p>
      <p className="gp-probe__row mono">
        <span className="gp-probe__label">SEEN</span>
        <span className="gp-probe__value">
          {seen.size ? [...seen].sort((a, b) => a - b).join(" · ") : "—"}
        </span>
      </p>
      <p className="gp-probe__row mono">
        <span className="gp-probe__label">AXES</span>
        <span className="gp-probe__value">{axes.length ? axes.join(" · ") : "—"}</span>
      </p>
      <p className="gp-probe__hint">
        Expected: bottom face button 0, right face 1, shoulders 4 / 5, D-pad
        12-15. If the D-pad shows nothing here but moves the AXES numbers, it is
        on an axis pair — that case is already handled.
      </p>
    </div>
  );
}
