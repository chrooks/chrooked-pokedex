import { useEffect, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useSubmit } from "../../hooks/useSubmit";
import { rowId } from "../../lib/rowId";
import { TYPES } from "../../lib/format";
import type { TypeChartEntry } from "../../types";
import { ErrorView } from "../StatusView";
import { FormError } from "../editors/FormFeedback";
import "./tabs.css";
import "../editors/editors.css";

/** The type-chart override list, editable as one whole-list save (it's a single
    file on disk). Add/remove rows, set a multiplier, then Save replaces the set.
    A multiplier reads with its meaning: 0 = immune, 0.5 = resisted, 2 = super. */
const MULTIPLIERS = [0, 0.5, 1, 2] as const;

type Row = TypeChartEntry & { _id: number };

const strip = (rows: Row[]): TypeChartEntry[] =>
  rows.map((r) => ({
    attacker: r.attacker,
    defender: r.defender,
    multiplier: r.multiplier,
  }));

const seed = (entries: TypeChartEntry[]): Row[] =>
  entries.map((entry) => ({ ...entry, _id: rowId() }));

export function TypeChartTab() {
  const { data, error, status, isLoading, reload } =
    useResource<TypeChartEntry[]>(api.typeChart);
  const { isSaving, error: saveError, citing, run } = useSubmit();
  const [rows, setRows] = useState<Row[]>([]);

  // Seed the working list from the fetched data. `reload()` only fires after a
  // successful save, so re-seeding then is intended (it adopts the canonical
  // server sort); the `null` loading phase is skipped so edits don't flash away.
  useEffect(() => {
    if (data !== null) setRows(seed(data));
  }, [data]);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading type chart…</p>;

  const dirty = JSON.stringify(strip(rows)) !== JSON.stringify(data ?? []);

  function setRow(index: number, patch: Partial<TypeChartEntry>) {
    setRows((rs) => rs.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function addRow() {
    setRows((rs) => [
      ...rs,
      { _id: rowId(), attacker: "", defender: "", multiplier: 0 },
    ]);
  }

  function removeRow(index: number) {
    setRows((rs) => rs.filter((_, i) => i !== index));
  }

  async function save() {
    const ok = await run(() => api.putTypeChart(strip(rows)));
    if (ok) reload();
  }

  return (
    <div className="tab" id="tab-type-chart">
      <datalist id="tc-type-options">
        {TYPES.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">{rows.length} matchup overrides</span>
        <button type="button" className="btn btn--new" onClick={addRow}>
          <span aria-hidden="true">+ </span>Add override
        </button>
      </div>

      <div className="row-list">
        {rows.length === 0 && (
          <p className="row-list__empty">
            No overrides. The base type chart applies as-is.
          </p>
        )}
        {rows.map((row, index) => (
          <div key={row._id} className="row-list__row row-list__row--inline">
            <div className="tc-row">
              <input
                className="field__input"
                list="tc-type-options"
                autoComplete="off"
                aria-label={`Attacker type for override ${index + 1}`}
                placeholder="Attacker"
                value={row.attacker}
                onChange={(e) => setRow(index, { attacker: e.target.value })}
              />
              <span className="tc-row__vs" aria-hidden="true">
                vs
              </span>
              <input
                className="field__input"
                list="tc-type-options"
                autoComplete="off"
                aria-label={`Defender type for override ${index + 1}`}
                placeholder="Defender"
                value={row.defender}
                onChange={(e) => setRow(index, { defender: e.target.value })}
              />
              <select
                className="field__select"
                aria-label={`Multiplier for override ${index + 1}`}
                value={row.multiplier}
                onChange={(e) =>
                  setRow(index, { multiplier: Number(e.target.value) })
                }
              >
                {MULTIPLIERS.map((m) => (
                  <option key={m} value={m}>
                    ×{m} · {meaning(m)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="row-list__remove"
                aria-label={`Remove override ${index + 1}`}
                onClick={() => removeRow(index)}
              >
                ×
              </button>
            </div>
          </div>
        ))}
      </div>

      {saveError !== null && (
        <FormError key={saveError} message={saveError} citing={citing} />
      )}

      <div className="editor-actions">
        <span className="editor-actions__spacer" />
        {dirty && (
          <button
            type="button"
            className="btn"
            disabled={isSaving}
            onClick={() => setRows(seed(data ?? []))}
          >
            Discard
          </button>
        )}
        <button
          type="button"
          className="btn btn--primary"
          disabled={!dirty || isSaving}
          onClick={() => void save()}
        >
          {isSaving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}

function meaning(multiplier: number): string {
  if (multiplier === 0) return "immune";
  if (multiplier < 1) return "resisted";
  if (multiplier > 1) return "super effective";
  return "neutral";
}
