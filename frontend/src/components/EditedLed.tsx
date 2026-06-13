import "./edited-led.css";

type Props = {
  /** When false, renders nothing — only edited entries get the LED. */
  on: boolean;
  /** "dot" for the grid corner; "tag" for the labelled detail header. */
  variant?: "dot" | "tag";
};

/**
 * The amber status LED: the single signal that the Ruleset has touched a
 * species. Never color-alone — the dot pairs with an accessible label (visually
 * hidden in the dot variant) so it survives grayscale and color-blindness.
 */
export function EditedLed({ on, variant = "dot" }: Props) {
  if (!on) {
    return null;
  }
  if (variant === "tag") {
    // No live region: the tag is read naturally when the dialog takes focus, so
    // role="status" would just re-announce on every species change.
    return (
      <span className="edited-led edited-led--tag">
        <span className="edited-led__lamp" aria-hidden="true" />
        EDITED
      </span>
    );
  }
  return (
    <span className="edited-led edited-led--dot">
      <span className="edited-led__lamp" aria-hidden="true" />
      <span className="sr-only">edited by the Ruleset</span>
    </span>
  );
}
