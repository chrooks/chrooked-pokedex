/* The offline strip (#122): one line under the header that says, honestly,
   whether this dex works without a network, and the one action that makes it
   so. A State Change control (Save → Saving n/N → Saved ✓), never a spinner,
   because the count is the only thing that tells a phone user on a slow link
   that anything is happening.

   States:
   - online, never saved  → "Works offline after one save"  [Save for offline]
   - online, saving       → "Saving for offline · 312 / 812" + progress track
   - online, saved        → "Saved for offline · Oct 27"     [Refresh]
   - offline, saved       → lamp lit, "Offline · showing what was saved Oct 27"
   - offline, never saved → lamp lit, "Offline · nothing saved yet…"

   Hidden entirely where no service worker can exist (plain http, old WebView):
   the button would lie. */

import { useCallback, useEffect, useRef, useState } from "react";
import type { DexEntry } from "../types";
import { isReachable, savedAt, warmOffline } from "../lib/offline";
import "./offline-bar.css";

type Props = {
  entries: DexEntry[];
  targetId: string | null;
};

type Saving = { done: number; total: number } | null;

const fmtDate = (d: Date) =>
  d.toLocaleDateString(undefined, { month: "short", day: "numeric" });

export function OfflineBar({ entries, targetId }: Props) {
  const [online, setOnline] = useState(() => navigator.onLine);
  const [saved, setSaved] = useState<Date | null>(() => savedAt(targetId));
  const [saving, setSaving] = useState<Saving>(null);
  const [failed, setFailed] = useState(false);
  const abort = useRef<AbortController | null>(null);

  // onLine is a hint; the probe is the truth (see isReachable). Re-probe on
  // every network event and when the tab comes back to the foreground.
  useEffect(() => {
    let alive = true;
    const probe = () => {
      if (!navigator.onLine) {
        setOnline(false);
        return;
      }
      void isReachable().then((ok) => alive && setOnline(ok));
    };
    const onVisible = () => document.visibilityState === "visible" && probe();
    probe();
    window.addEventListener("online", probe);
    window.addEventListener("offline", probe);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      window.removeEventListener("online", probe);
      window.removeEventListener("offline", probe);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  // Backdrop switch: a different route set, so its own stamp and a stopped run.
  useEffect(() => {
    abort.current?.abort();
    setSaving(null);
    setFailed(false);
    setSaved(savedAt(targetId));
  }, [targetId]);
  useEffect(() => () => abort.current?.abort(), []);

  const save = useCallback(async () => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setFailed(false);
    setSaving({ done: 0, total: 0 });
    const result = await warmOffline({
      entries,
      targetId,
      signal: controller.signal,
      // An aborted run's jobs still drain; their ticks must not touch state.
      onProgress: (done, total) => !controller.signal.aborted && setSaving({ done, total }),
    });
    if (controller.signal.aborted) return;
    setSaving(null);
    const stamp = savedAt(targetId);
    setSaved(stamp);
    // Routes short → nothing stamped → say so instead of pretending.
    setFailed(stamp === null || result.done < result.total * 0.9);
  }, [entries, targetId]);

  if (!("serviceWorker" in navigator)) return null;

  const lamp = <span className="offline-bar__lamp" data-on={!online} aria-hidden="true" />;

  if (!online) {
    return (
      <div className="offline-bar mono" role="status" data-offline="true">
        {lamp}
        {saved ? (
          <span>Offline · showing what was saved {fmtDate(saved)}</span>
        ) : (
          <span>Offline · nothing saved yet. Connect, then tap Save for offline.</span>
        )}
      </div>
    );
  }

  if (saving) {
    const pct = saving.total === 0 ? 0 : Math.round((saving.done / saving.total) * 100);
    return (
      <div className="offline-bar mono" role="status" aria-live="polite">
        {lamp}
        <span>
          Saving for offline · {saving.done} / {saving.total || "…"}
        </span>
        <span className="offline-bar__track" aria-hidden="true">
          <span className="offline-bar__fill" style={{ width: `${pct}%` }} />
        </span>
      </div>
    );
  }

  return (
    <div className="offline-bar mono" role="status">
      {lamp}
      {failed ? (
        <span className="offline-bar__warn">Some pieces did not save. Try again on Wi-Fi.</span>
      ) : saved ? (
        <span>Saved for offline · {fmtDate(saved)}</span>
      ) : (
        <span>Works offline after one save</span>
      )}
      <button
        type="button"
        id="offline-save"
        className="offline-bar__btn"
        disabled={entries.length === 0}
        onClick={save}
      >
        {saved && !failed ? "Refresh" : "Save for offline"}
      </button>
    </div>
  );
}
