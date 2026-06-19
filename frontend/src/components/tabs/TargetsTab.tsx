/* The Targets panel (M3): register game forks, then Preview or Apply the Ruleset
   to one. Container — owns the targets fetch, the selected target, and removal;
   delegates the add form, the list, and the preview/apply workspace.

   "View this target's backdrop" bubbles up to App via `onViewBackdrop`, which
   flips the dex onto that fork's values ⊕ Ruleset and jumps to the Dex tab. */

import { useMemo, useState } from "react";
import { api, ApiError } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Target } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import { TargetAddForm } from "../targets/TargetAddForm";
import { TargetList } from "../targets/TargetList";
import { ApplyPanel } from "../targets/ApplyPanel";
import "../targets/targets.css";
import "../editors/editors.css";

type Props = {
  /** Show the dex with this target's backdrop (target ⊕ Ruleset). */
  onViewBackdrop: (targetId: string) => void;
};

export function TargetsTab({ onViewBackdrop }: Props) {
  const { data, error, status, isLoading, reload } =
    useResource<Target[]>(api.targets);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const targets = useMemo(() => data ?? [], [data]);
  const selected = targets.find((t) => t.id === selectedId) ?? null;

  async function handleRemove(id: string) {
    setRemovingId(id);
    setRemoveError(null);
    try {
      await api.deleteTarget(id);
      if (selectedId === id) setSelectedId(null);
      reload();
    } catch (caught: unknown) {
      setRemoveError(
        caught instanceof ApiError
          ? caught.message
          : "Could not remove the target.",
      );
    } finally {
      setRemovingId(null);
    }
  }

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading targets…</p>;

  return (
    <div className="tab tab--targets" id="tab-targets">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {targets.length} registered {targets.length === 1 ? "target" : "targets"}
        </span>
      </div>

      <TargetAddForm onAdded={reload} />

      {removeError !== null && (
        <p className="target-add__error" id="target-remove-error" role="alert">
          {removeError}
        </p>
      )}

      {targets.length === 0 ? (
        <EmptyView message="No targets registered yet. Add one above to preview and apply the Ruleset." />
      ) : (
        <div className="targets-grid">
          <TargetList
            targets={targets}
            selectedId={selectedId}
            removingId={removingId}
            onSelect={setSelectedId}
            onRemove={(id) => void handleRemove(id)}
          />

          {selected !== null ? (
            <ApplyPanel
              key={selected.id}
              target={selected}
              onViewBackdrop={onViewBackdrop}
            />
          ) : (
            <div className="apply-panel apply-panel--empty" id="apply-panel-empty">
              <p className="apply-panel__hint">
                Select a target to Preview or Apply the Ruleset.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
