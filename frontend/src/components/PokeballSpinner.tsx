import "./pokeball-spinner.css";

type Props = {
  /** Diameter in px. Default 28 — the inline/loading-row size. */
  size?: number;
  /** Optional visible + accessible label (e.g. "Loading moves…"). */
  label?: string;
  /** Override the default id when more than one spinner can co-exist. */
  id?: string;
};

/** Reusable on-brand pending Affordance: a spinning Poké Ball.
 *
 * One loading cue used app-wide (tab loads, the LLM proposal flows). The ball is
 * pure CSS (compositor-friendly `transform: rotate`) and respects reduced-motion.
 * Announced politely as status — never as an error. */
export function PokeballSpinner({ size = 28, label, id = "pokeball-spinner" }: Props) {
  return (
    <div
      id={id}
      className="pokeball-spinner"
      role="status"
      aria-live="polite"
      aria-label={label ?? "Loading"}
    >
      <span
        className="pokeball-spinner__ball"
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
      {label && <span className="pokeball-spinner__label">{label}</span>}
    </div>
  );
}
