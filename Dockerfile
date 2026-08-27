# Two stages: build the React SPA with node, then serve it from the Python app.
# ponytail: editable install (-e) on purpose — the app derives _REPO_ROOT from
# its own source path, so the package must stay at /app/src, not site-packages,
# or the default ruleset/ and frontend/dist paths break.

# ---- build the frontend ----
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build   # -> /fe/dist

# ---- runtime ----
FROM python:3.12-slim
# rsync + ssh: the post-apply mirror to the handheld runs in-process
# (web/targets.py::_sync_after_apply shells out to them).
RUN apt-get update && apt-get install -y --no-install-recommends rsync openssh-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[web]"
COPY --from=frontend /fe/dist ./frontend/dist
EXPOSE 8000
# ruleset/ is bind-mounted at runtime (see docker-compose.yml) so edits land on
# the host checkout, where the autocommit loop can commit + push them.
CMD ["chrooked-pokedex", "ui", "--host", "0.0.0.0", "--port", "8000", "--no-reload"]
