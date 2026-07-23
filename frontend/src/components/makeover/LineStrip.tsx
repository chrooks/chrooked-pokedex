/* The right strip: the line's sprites (anchor + pre-evos) and the facts that
   accumulate as design stages close — typing, stats, abilities, then the learnset
   lock. Each fact blooms once as it lands (a CSS LED bloom, reduced-motion
   respected). Reuses DexSprite and TypeChip. */

import type { DexEntry } from "../../types";
import type { StageFacts } from "../../lib/makeoverApi";
import { STAT_ORDER, STAT_LABEL, bst } from "../../lib/format";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";

interface Props {
  anchor: DexEntry;
  preEvos: DexEntry[];
  facts: StageFacts;
  lockedLearnset: boolean;
  backdropTargetId?: string | null;
}

export function LineStrip({ anchor, preEvos, facts, lockedLearnset, backdropTargetId }: Props) {
  const line = [...preEvos, anchor];
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
        {facts.types && (
          <Fact label="typing" k="typing">
            <span className="mk-line__chips">
              {facts.types.map((t) => (
                <TypeChip key={t} type={t} />
              ))}
            </span>
          </Fact>
        )}
        {facts.stats && (
          <Fact label="stats" k="stats">
            <span className="mono mk-line__stats">
              {STAT_ORDER.map((key) => (
                <span key={key} className="mk-line__stat">
                  <span className="mk-line__stat-k">{STAT_LABEL[key]}</span>
                  {facts.stats?.[key]}
                </span>
              ))}
              <span className="mk-line__stat mk-line__stat--bst">
                <span className="mk-line__stat-k">BST</span>
                {bst(facts.stats)}
              </span>
            </span>
          </Fact>
        )}
        {facts.abilities && (
          <Fact label="abilities" k="abilities">
            <span className="mono mk-line__abilities">
              {[facts.abilities.primary, facts.abilities.secondary, facts.abilities.hidden]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </Fact>
        )}
        {lockedLearnset && (
          <Fact label="learnset" k="learnset">
            <span className="mono mk-line__learnset-mark">locked · mirrored to line</span>
          </Fact>
        )}
      </dl>
    </aside>
  );
}

/** One locked fact. Keyed so React remounts it when it first lands, running the
    one-shot LED bloom (CSS). */
function Fact({ label, k, children }: { label: string; k: string; children: React.ReactNode }) {
  return (
    <div className="mk-line__fact" data-fact={k}>
      <dt className="mk-line__fact-label mono">
        <span className="mk-line__fact-led" aria-hidden="true" />
        {label}
      </dt>
      <dd className="mk-line__fact-value">{children}</dd>
    </div>
  );
}
