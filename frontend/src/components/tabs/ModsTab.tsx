import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { PokeballSpinner } from "../PokeballSpinner";
import { useResource } from "../../hooks/useResource";
import type { ModTarget, StaticMod, Target } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import "./tabs.css";
import "./mods.css";

const GROUPS: { key: StaticMod["group"]; label: string }[] = [
  { key: "convenience", label: "Convenience" },
  { key: "form", label: "Form switchers" },
  { key: "battle", label: "Battle rules" },
  { key: "shim", label: "Kirin shims" },
  { key: "diagnostic", label: "Diagnostics" },
];

/** The engine the mod catalog is written for (the server's `engine`). */
function slugFor(label: string): string {
  return label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** The detail view drops the structured `mod-` lines — the row already shows them. */
function notes(mod: StaticMod): string {
  return mod.header
    .split("\n")
    .filter((line) => !line.startsWith("mod-") && !line.startsWith("encoding:"))
    .join("\n")
    .trim();
}

interface ModsTabProps {
  /** The Target the dex is backdropped against; the default pick here. */
  backdropTargetId?: string | null;
}

/** Static mods: the script files an Applier installs into a Target outside the
    Ruleset data (QoL hotkeys, form switchers, Kirin shims). Each Target turns
    mods on or off; apply installs what is on and REMOVES what is off. */
export function ModsTab({ backdropTargetId }: ModsTabProps) {
  const targets = useResource<Target[]>(api.targets);
  const [targetId, setTargetId] = useState<string | null>(backdropTargetId ?? null);

  // Default to the backdrop, else the first Target the catalog's engine runs on.
  useEffect(() => {
    if (targetId !== null || targets.data === null) return;
    const pick = targets.data.find((t) => t.engine === "rejuv") ?? targets.data[0];
    if (pick) setTargetId(pick.id);
  }, [targetId, targets.data]);

  const fetchMods = useMemo(
    () => (signal: AbortSignal) => api.mods(targetId, signal),
    [targetId],
  );
  const catalog = useResource(fetchMods);
  const [target, setTarget] = useState<ModTarget | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    setTarget(catalog.data?.target ?? null);
    setSaveError(null);
  }, [catalog.data]);

  if (catalog.error !== null)
    return <ErrorView message={catalog.error} status={catalog.status} />;
  if (catalog.isLoading || catalog.data === null)
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading mods…" />
      </div>
    );

  const mods = catalog.data.mods;
  const off = new Set(target?.off ?? []);
  const isOn = (mod: StaticMod) => mod.locked !== null || !off.has(mod.id);
  const byId = new Map(mods.map((m) => [m.id, m]));
  const canSwitch = target !== null && target.supported && target.namespace !== null;
  const onCount = mods.filter(isOn).length;

  async function toggle(mod: StaticMod) {
    if (target === null) return;
    const next = new Set(off);
    if (next.has(mod.id)) next.delete(mod.id);
    else next.add(mod.id);
    const previous = target;
    setTarget({ ...target, off: [...next].sort() }); // optimistic
    setSaveError(null);
    try {
      setTarget(await api.setTargetMods(target.id, [...next]));
    } catch (error) {
      setTarget(previous);
      setSaveError(error instanceof Error ? error.message : String(error));
    }
  }

  async function bindNamespace(slug: string) {
    if (target === null) return;
    setSaveError(null);
    try {
      await api.setTargetNamespace(target.id, slug);
      catalog.reload();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    }
  }

  function toggleOpen(id: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="tab tab--mods" id="tab-mods">
      <div className="tab-toolbar mods-toolbar">
        <span className="tab-toolbar__title">{mods.length} mods</span>
        <label className="mods-target">
          <span className="mods-target__label">Target</span>
          <select
            id="mods-target-select"
            className="mods-target__select mono"
            value={targetId ?? ""}
            onChange={(event) => setTargetId(event.target.value || null)}
          >
            {(targets.data ?? []).length === 0 && <option value="">No Targets</option>}
            {(targets.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.label} · {t.engine}
              </option>
            ))}
          </select>
        </label>
        {target !== null && target.supported && (
          <span className="mods-count mono" id="mods-count">
            {onCount} on · {mods.length - onCount} off
          </span>
        )}
      </div>

      {target !== null && !target.supported && (
        <p className="mods-notice" role="status" id="mods-unsupported">
          <strong>No port for {target.engine}.</strong> These mods are written
          for {catalog.data.engine} and do not install on {target.label}.
        </p>
      )}
      {target !== null && target.supported && target.namespace === null && (
        <BindNamespace target={target} onBind={bindNamespace} suggested={slugFor(target.label)} />
      )}
      {canSwitch && (
        <p className="mods-consequence" id="mods-consequence">
          Apply installs each mod that is on and removes each mod that is off.
          Saved to{" "}
          <span className="mono">ruleset/targets/{target.namespace}/mods.yaml</span>.
        </p>
      )}
      {saveError !== null && (
        <p className="mods-error" role="alert">
          {saveError}
        </p>
      )}

      {mods.length === 0 ? (
        <EmptyView message="No static mods in references/rejuv-harness/." />
      ) : (
        GROUPS.map((group) => {
          const rows = mods.filter((m) => m.group === group.key);
          if (rows.length === 0) return null;
          return (
            <section key={group.key} className="mods-group" aria-labelledby={`mods-group-${group.key}`}>
              <h2 className="mods-group__title" id={`mods-group-${group.key}`}>
                {group.label}
                <span className="mods-group__count mono">{rows.length}</span>
              </h2>
              <ul className="mods-list">
                {rows.map((mod) => {
                  const on = isOn(mod);
                  const missing = mod.needs.filter((n) => {
                    const need = byId.get(n);
                    return need === undefined || !isOn(need);
                  });
                  const dependents = on
                    ? []
                    : mods.filter((m) => isOn(m) && m.needs.includes(mod.id));
                  const expanded = open.has(mod.id);
                  return (
                    <li
                      key={mod.id}
                      className="mod"
                      id={`mod-${mod.id}`}
                      data-off={!on || undefined}
                      data-blocked={(on && missing.length > 0) || undefined}
                    >
                      <button
                        type="button"
                        role="switch"
                        className="mod__switch mono"
                        aria-checked={on}
                        aria-label={`${mod.id}: ${on ? "on" : "off"}`}
                        disabled={!canSwitch || mod.locked !== null}
                        title={mod.locked !== null ? `Locked: ${mod.locked}` : undefined}
                        onClick={() => void toggle(mod)}
                      >
                        {mod.locked !== null ? "lock" : on ? "on" : "off"}
                      </button>
                      <button
                        type="button"
                        className="mod__main"
                        aria-expanded={expanded}
                        aria-controls={`mod-notes-${mod.id}`}
                        onClick={() => toggleOpen(mod.id)}
                      >
                        <span className="mod__id mono">{mod.id}</span>
                        <span className="mod__summary">{mod.summary}</span>
                      </button>
                      {(mod.needs.length > 0 || mod.locked !== null || dependents.length > 0) && (
                        <p className="mod__meta">
                          {mod.needs.length > 0 && (
                            <span className={missing.length > 0 ? "mod__warn" : undefined}>
                              needs <span className="mono">{mod.needs.join(", ")}</span>
                              {on && missing.length > 0 && " — off, so this will not install"}
                            </span>
                          )}
                          {dependents.length > 0 && (
                            <span className="mod__warn">
                              <span className="mono">{dependents.map((d) => d.id).join(", ")}</span>{" "}
                              {dependents.length === 1 ? "needs" : "need"} this and will not install
                            </span>
                          )}
                          {mod.locked !== null && <span>locked on: {mod.locked}</span>}
                        </p>
                      )}
                      {expanded && (
                        <pre className="mod__notes" id={`mod-notes-${mod.id}`}>
                          <span className="mod__file">{mod.file}</span>
                          {"\n\n"}
                          {notes(mod)}
                        </pre>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
}

function BindNamespace({
  target,
  suggested,
  onBind,
}: {
  target: ModTarget;
  suggested: string;
  onBind: (slug: string) => Promise<void>;
}) {
  const [slug, setSlug] = useState(suggested);
  return (
    <form
      className="mods-notice mods-bind"
      id="mods-bind"
      onSubmit={(event) => {
        event.preventDefault();
        if (slug.trim()) void onBind(slug.trim());
      }}
    >
      <span>
        <strong>{target.label} has no namespace.</strong> Switches are saved
        under <span className="mono">ruleset/targets/&lt;namespace&gt;/</span>.
      </span>
      <input
        className="mods-bind__input mono"
        aria-label="Namespace"
        value={slug}
        onChange={(event) => setSlug(event.target.value)}
      />
      <button type="submit" className="btn btn--primary">
        Bind namespace
      </button>
    </form>
  );
}
