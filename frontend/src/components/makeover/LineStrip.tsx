/* The right strip: the line's sprites (anchor + pre-evos) and the BEFORE→AFTER
   diff of the facets that change as design stages close (ac12). The baseline is
   the anchor's profile captured at workbench OPEN; each facet reads
   `facts[facet] ?? entry[facet]` as its after-state. A changed facet shows the old
   value struck+dim and the new value amber (--edited), with numeric deltas + BST
   for stats and an expandable row list for the learnset. An unchanged facet renders
   the anchor's compact CURRENT profile (type chips, stat line, ability slots,
   learnset count) in a quiet dim — never amber — and flips to the before→after diff
   the moment it changes. Each fact blooms once as it lands (a one-shot LED bloom,
   reduced-motion respected). Reuses DexSprite and TypeChip. */

import type { ReactNode } from "react";
import type { AbilitySlots, DexEntry } from "../../types";
import type { StageFacts } from "../../lib/makeoverApi";
import { diffProfile, type ProfileSnapshot } from "../../lib/profileDiff";
import { STAT_ORDER, STAT_LABEL, bst } from "../../lib/format";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";

interface Props {
  anchor: DexEntry;
  preEvos: DexEntry[];
  before: ProfileSnapshot;
  facts: StageFacts;
  lockedLearnset: boolean;
  backdropTargetId?: string | null;
}

function abilityList(abilities: AbilitySlots): string {
  return [abilities.primary, abilities.secondary, abilities.hidden].filter(Boolean).join(" · ") || "—";
}

function signed(delta: number): string {
  return delta > 0 ? `+${delta}` : `${delta}`;
}

export function LineStrip({ anchor, preEvos, before, facts, lockedLearnset, backdropTargetId }: Props) {
  const line = [...preEvos, anchor];
  const diff = diffProfile(before, anchor, facts);
  // The anchor's OWN learnset diff — the only honest driver of the amber/changed
  // state. A mirror-only run leaves the anchor's learnset untouched (only pre-evos
  // were written), so lockedLearnset alone must NOT light this facet amber.
  const learnsetChanged =
    diff.learnset.added.length + diff.learnset.moved.length + diff.learnset.removed.length > 0;

  return (
    <aside className="mk-line" aria-label="The evolution line" id="mk-line-strip">
      <div className="mk-line__sprites">
        {line.map((member) => (
          <div
            key={member.chrooked_id}
            className="mk-line__member"
            data-anchor={member.chrooked_id === anchor.chrooked_id || undefined}
          >
            <DexSprite
              chrookedId={member.chrooked_id}
              dex={member.dex}
              name={member.name}
              backdropTargetId={backdropTargetId}
              size={member.chrooked_id === anchor.chrooked_id ? 72 : 44}
            />
            <span className="mk-line__member-name mono">{member.name}</span>
          </div>
        ))}
      </div>

      <dl className="mk-line__facts">
        <Fact label="typing" k="typing" landed={facts.types != null} changed={diff.types.changed}>
          {diff.types.changed ? (
            <span className="mk-line__diff">
              <span className="mk-line__was mono">{diff.types.before.join("/") || "—"}</span>
              <span className="mk-line__now-chips">
                {diff.types.after.map((t) => (
                  <TypeChip key={t} type={t} />
                ))}
              </span>
            </span>
          ) : (
            <span className="mk-line__now-chips">
              {diff.types.after.length === 0 ? (
                <span className="mono mk-line__unchanged">—</span>
              ) : (
                diff.types.after.map((t) => <TypeChip key={t} type={t} />)
              )}
            </span>
          )}
        </Fact>

        <Fact label="stats" k="stats" landed={facts.stats != null} changed={diff.stats.changed}>
          {diff.stats.changed ? (
            <span className="mono mk-line__stats">
              {STAT_ORDER.map((key) => {
                const now = diff.stats.after[key] ?? 0;
                const was = diff.stats.before[key] ?? 0;
                const d = now - was;
                return (
                  <span key={key} className="mk-line__stat" data-changed={d !== 0 || undefined}>
                    <span className="mk-line__stat-k">{STAT_LABEL[key]}</span>
                    {now}
                    {d !== 0 && <span className="mk-line__stat-delta"> {signed(d)}</span>}
                  </span>
                );
              })}
              <span className="mk-line__stat mk-line__stat--bst">
                <span className="mk-line__stat-k">BST</span>
                <span className="mk-line__was">{bst(diff.stats.before)}</span>
                <span className="mk-line__now"> {bst(diff.stats.after)}</span>
                {bstDelta(diff.stats.before, diff.stats.after)}
              </span>
            </span>
          ) : (
            <span className="mono mk-line__stats mk-line__stats--current">
              {STAT_ORDER.map((key) => (
                <span key={key} className="mk-line__stat">
                  <span className="mk-line__stat-k">{STAT_LABEL[key]}</span>
                  {diff.stats.after[key] ?? 0}
                </span>
              ))}
              <span className="mk-line__stat mk-line__stat--bst">
                <span className="mk-line__stat-k">BST</span>
                {bst(diff.stats.after)}
              </span>
            </span>
          )}
        </Fact>

        <Fact
          label="abilities"
          k="abilities"
          landed={facts.abilities != null}
          changed={diff.abilities.changed}
        >
          {diff.abilities.changed ? (
            <span className="mono mk-line__abilities">
              <span className="mk-line__was">{abilityList(diff.abilities.before)}</span>
              <span className="mk-line__now"> {abilityList(diff.abilities.after)}</span>
            </span>
          ) : (
            <span className="mono mk-line__abilities">{abilityList(diff.abilities.after)}</span>
          )}
        </Fact>

        <Fact label="learnset" k="learnset" landed={learnsetChanged} changed={learnsetChanged}>
          {learnsetChanged ? (
            <div className="mk-line__learnset">
              <span className="mono mk-line__learnset-head">
                <span className="mk-line__ls-add">+{diff.learnset.added.length} added</span>
                {" · "}
                <span className="mk-line__ls-move">{diff.learnset.moved.length} moved</span>
                {" · "}
                <span className="mk-line__ls-drop">−{diff.learnset.removed.length} dropped</span>
              </span>
              <details className="mk-line__ls-details">
                <summary className="mono mk-line__ls-summary">rows</summary>
                <ul className="mk-line__ls-list mono">
                  {diff.learnset.added.map((row) => (
                    <li key={`a-${row.level}-${row.move}`} className="mk-line__ls-row mk-line__ls-row--add">
                      + {row.level === 0 ? "—" : `L${row.level}`} {row.move}
                    </li>
                  ))}
                  {diff.learnset.moved.map((row) => (
                    <li key={`m-${row.move}`} className="mk-line__ls-row mk-line__ls-row--move">
                      {row.move} L{row.from} → L{row.to}
                    </li>
                  ))}
                  {diff.learnset.removed.map((row) => (
                    <li key={`r-${row.level}-${row.move}`} className="mk-line__ls-row mk-line__ls-row--drop">
                      − {row.level === 0 ? "—" : `L${row.level}`} {row.move}
                    </li>
                  ))}
                </ul>
              </details>
              {lockedLearnset && (
                <span className="mono mk-line__learnset-mark">mirrored to line</span>
              )}
            </div>
          ) : (
            // Anchor learnset unchanged — compact current, never amber. A mirror-only
            // run still notes it went to the line (the pre-evos got the copy-down).
            <span className="mono mk-line__abilities">
              {anchor.learnset.length} moves
              {lockedLearnset && <span className="mk-line__learnset-mark"> · mirrored to line</span>}
            </span>
          )}
        </Fact>
      </dl>
    </aside>
  );
}

function bstDelta(
  before: Record<string, number>,
  after: Record<string, number>,
): ReactNode {
  const b = bst(before);
  const a = bst(after);
  if (b === undefined || a === undefined || a === b) return null;
  return <span className="mk-line__stat-delta"> ({signed(a - b)})</span>;
}

/** One fact row. When `landed` flips true (a facet locks this session) the LED
    span is inserted fresh, replaying the one-shot bloom (CSS runs on insertion).
    `changed` drives the amber/quiet styling. */
function Fact({
  label,
  k,
  landed,
  changed,
  children,
}: {
  label: string;
  k: string;
  landed: boolean;
  changed: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mk-line__fact" data-fact={k} data-changed={changed || undefined}>
      <dt className="mk-line__fact-label mono">
        {landed && <span className="mk-line__fact-led" aria-hidden="true" />}
        {label}
      </dt>
      <dd className="mk-line__fact-value">{children}</dd>
    </div>
  );
}
