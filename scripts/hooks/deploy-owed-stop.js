#!/usr/bin/env node
/* Stop hook: enforce the dex redeploy when the session forgets.
 *
 * The machine rule says a service-affecting push to origin/main is not "done"
 * until dex.hestia.chrooks.com runs it. This hook is the runtime half of that
 * promise: at end of turn, if origin/main carries service-affecting changes
 * beyond the last recorded deploy, block the stop and tell Claude to run
 * /deploy-dex (scripts/deploy-hestia.sh writes the marker on success).
 *
 * Design constraints:
 * - No network. Truth is the local marker `.deployed-commit` (gitignored)
 *   vs the local origin/main ref. ponytail: a deploy done from another
 *   machine would leave this marker stale and cause one spurious block —
 *   the deploy that clears it also refreshes the marker, so it self-heals.
 * - Yields after one block (stop_hook_active) so a hestia outage cannot
 *   trap the session in a loop — Claude reports the failure and may stop.
 * - Ruleset-only pushes never block: the container bind-mounts ruleset/.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

// Paths that ship inside the container image — anything else (ruleset/,
// scripts/, docs/, .claude/, tests/) does not owe a redeploy. frontend/ is
// deliberately whole: over-deploying on a test-only change is cheap and safe.
const SERVICE_PATHS = [
  /^src\/chrooked_pokedex\//,
  /^frontend\//,
  /^Dockerfile$/,
  /^docker-compose\.yml$/,
  /^pyproject\.toml$/,
];

let input = "";
try {
  input = fs.readFileSync(0, "utf8");
} catch {
  /* no stdin — treat as a plain stop check */
}
try {
  if (JSON.parse(input).stop_hook_active === true) process.exit(0);
} catch {
  /* unparseable stdin — proceed with the check */
}

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const git = (...args) =>
  execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();

let deployed;
try {
  deployed = fs.readFileSync(path.join(root, ".deployed-commit"), "utf8").trim();
} catch {
  process.exit(0); // no marker yet — the first /deploy-dex run seeds it
}
if (!deployed) process.exit(0);

let head;
try {
  head = git("rev-parse", "origin/main");
} catch {
  process.exit(0); // not a repo state we can judge — stay silent
}

let owed;
let changed = [];
try {
  if (git("rev-parse", `${deployed}^{commit}`) === head) process.exit(0);
  changed = git("diff", "--name-only", `${deployed}..origin/main`)
    .split("\n")
    .filter(Boolean);
  owed = changed.some((f) => SERVICE_PATHS.some((re) => re.test(f)));
} catch {
  owed = true; // marker names an unknown commit — stale; a deploy refreshes it
}
if (!owed) process.exit(0);

const shortHead = head.slice(0, 7);
process.stdout.write(
  JSON.stringify({
    decision: "block",
    reason:
      `Deploy owed: origin/main (${shortHead}) carries service-affecting changes ` +
      `beyond the last dex deploy (${deployed}). Run /deploy-dex ` +
      `(./scripts/deploy-hestia.sh) now, or — if deploying is genuinely wrong at ` +
      `this moment — tell the user why and name the pending deploy in your report.`,
  }) + "\n",
);
process.exit(0);
