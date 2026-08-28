---
name: deploy-dex
description: Redeploy the dex service on hestia (dex.hestia.chrooks.com) after a service-affecting change lands on main — pull the hestia clone, rebuild the compose image, recreate the container, and prove health through the real URL. Use when the user asks to deploy/redeploy the dex, when a pushed change touches the web service (src/chrooked_pokedex/web, frontend/, Dockerfile, docker-compose.yml, pyproject deps), or when a report would otherwise end with "hestia still serves the old build".
---

# Deploy the dex to hestia

The dex at `dex.hestia.chrooks.com` is a Docker Compose service on hestia,
built from the repo clone at `/home/chrooks/projects/chrooked-pokedex`
(`docker-compose.yml`, service `web`, container `chrooked-pokedex`). The
Dockerfile builds the SPA in its own stage, so one rebuild ships backend and
frontend together. This skill is the ONE sanctioned exception to the
"hands off hestia services" machine rule — and it reaches only this stack.

## When to run

- A change that affects the running service has been **committed and pushed to
  `origin/main`**: backend (`src/chrooked_pokedex/`), frontend (`frontend/`),
  `Dockerfile`, `docker-compose.yml`, or dependencies.
- Part of close-the-loop: a session that pushes a service-affecting change
  redeploys automatically — don't leave the report on "redeploy still needed".
- NOT for Ruleset-only changes (`ruleset/`): the container bind-mounts
  `ruleset/` and loads it per request, and hestia's autocommit loop owns that
  sync. No redeploy needed.

## Steps

1. Confirm the change is on `origin/main` (`git log origin/main -1`). The
   deploy pulls on hestia; it never pushes. Unpushed work → push first
   (or stop if the user hasn't asked for that).
2. Run the deploy script from the repo root:

   ```bash
   ./scripts/deploy-hestia.sh
   ```

   It fast-forwards the hestia clone, runs `docker compose up -d --build`,
   then polls `https://dex.hestia.chrooks.com/api/health` from this machine.
3. Report the line the script prints (`deployed <sha> — healthy`). That sha
   matching `origin/main` IS the proof; don't re-verify by hand.

## Enforcement

This isn't guidance alone. `scripts/hooks/deploy-owed-stop.js` (a Stop hook in
`.claude/settings.json`) compares `.deployed-commit` — the marker
`deploy-hestia.sh` writes on success — against `origin/main`, and blocks
ending the turn while service-affecting changes sit undeployed. It yields
after one block, so if the deploy genuinely can't run (hestia down), report
why and the hook lets the session stop. Ruleset-only pushes never trigger it.

## Failure modes

- **`git pull --ff-only` fails** — hestia's clone diverged (the autocommit
  loop pushes ruleset edits; a race is possible). Inspect with
  `ssh hestia 'cd /home/chrooks/projects/chrooked-pokedex && git status'`,
  reconcile by pulling/rebasing THERE, never by force-push from here.
- **Health check never passes** — read
  `ssh hestia 'docker logs --tail 50 chrooked-pokedex'` and report; do not
  restart other services or reboot hestia while diagnosing.

## Boundaries

- Only this compose stack. Never `docker compose` in other directories,
  never `systemctl` on hestia (the autocommit unit included), never edits to
  hestia's files outside this clone's git state.
- Destructive recovery (down -v, image prune, force-push) needs an explicit
  ask from the user.
