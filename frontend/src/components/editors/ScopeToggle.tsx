/* The edit-scope toggle, shown in an editor only when a Target backdrop with a
   bound Override namespace is active. It makes the save destination an Honest
   Signifier: the author picks base (applies everywhere) vs this target only,
   before they save. Defaults to the target — opening a game's backdrop to edit
   is a deliberate "tune this game" act. */

type Props = {
  /** The bound Target's display label (e.g. "Chrooked Africanvs"). */
  targetLabel: string;
  /** True = scope edits to the target namespace; false = base Ruleset. */
  scopeToTarget: boolean;
  onChange: (scopeToTarget: boolean) => void;
};

export function ScopeToggle({ targetLabel, scopeToTarget, onChange }: Props) {
  return (
    <div
      className="editor-scope"
      id="editor-scope-toggle"
      role="radiogroup"
      aria-label="Edit scope"
    >
      <span className="editor-scope__label">This edit saves to</span>
      <div className="editor-scope__options">
        <button
          type="button"
          id="editor-scope-base"
          className="editor-scope__option"
          role="radio"
          aria-checked={!scopeToTarget}
          data-on={!scopeToTarget}
          onClick={() => onChange(false)}
        >
          Base Ruleset
        </button>
        <button
          type="button"
          id="editor-scope-target"
          className="editor-scope__option"
          role="radio"
          aria-checked={scopeToTarget}
          data-on={scopeToTarget}
          onClick={() => onChange(true)}
        >
          {targetLabel} only
        </button>
      </div>
    </div>
  );
}
