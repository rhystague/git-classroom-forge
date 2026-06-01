# Development Workflow

Docker Compose is the preferred development workflow for this repository. The workflow
is designed for parallel Git worktrees: each worktree gets its own Compose project name,
host port, containers, and network while dependency images are shared when lockfiles
match.

## Requirements

- macOS with Docker Desktop running
- Docker Compose v2
- Git worktrees, if you want multiple branches active at once

No Python install is required on the host for normal Docker-backed development commands.

## First Run

From the repository root:

```bash
scripts/dev init
scripts/dev up
```

`scripts/dev init` creates:

- `.env` from `.env.example` if it does not already exist
- `.docker/local.env` with generated Docker settings for this worktree

Set real `GITLAB_URL` and `GITLAB_TOKEN` values in `.env` before using GitLab API
validation or future provisioning features. CSV-only local validation works without a
token.

`scripts/dev up` starts the Flask app on the generated host port. The first active
worktree uses `http://127.0.0.1:8080` when the port is free; later active worktrees get
nearby free ports from `8081-8099`.

## Daily Commands

```bash
scripts/dev up
scripts/dev status
scripts/dev logs
scripts/dev shell
scripts/dev run python -m compileall app
scripts/dev run pytest
scripts/dev check
scripts/dev down
```

Use `scripts/dev init --reset` only when you want this worktree to choose a new port. If
a persisted port is occupied by another process, `scripts/dev up` fails with a reset
hint instead of silently changing URLs.

## Cleanup

```bash
scripts/dev down
```

Stops and removes this worktree's containers and network. It keeps generated files under
`data/`.

```bash
scripts/dev clean
scripts/dev clean --force
```

Removes this worktree's containers, network, and Compose volumes. It does not delete
the bind-mounted `data/` directory.

```bash
scripts/dev prune
scripts/dev prune --force
```

Removes unused Docker resources labelled for this repo, including stopped containers,
unused networks, unused volumes, and unused dependency images. It does not remove
running projects.

## Git Worktrees

A typical parallel branch flow is:

```bash
git worktree add ../class-git-forge-feature-a -b feature-a
cd ../class-git-forge-feature-a
scripts/dev up
```

Each worktree has a generated Compose project name based on the branch or detached HEAD
plus a short path hash, for example:

```text
class-git-forge-feature-a-a1b2c3d4
```

Before deleting a worktree, run:

```bash
scripts/dev clean --force
```

Then remove the worktree with Git:

```bash
git worktree remove ../class-git-forge-feature-a
```

If a worktree was deleted before cleanup, run `scripts/dev prune` from any remaining
copy of this repo to remove unused labelled Docker resources.

## Runtime State

Generated runtime files write under:

```text
data/uploads
data/reports
data/logs
```

These files may contain student IDs or provisioning details and are ignored by git.

## Images

The app image uses Python 3.11. The image tag is derived from:

- `requirements.txt`
- `docker/dev/app.Dockerfile`

When dependencies change, `scripts/dev` refreshes `.docker/local.env` with the new image
tag and `scripts/dev up` builds the image. `scripts/dev prune` removes unused old images
labelled for this repo.

## Troubleshooting

If Docker is not running, start Docker Desktop and rerun the command.

If `scripts/dev up` reports a persisted port conflict, stop the process using that port
or run:

```bash
scripts/dev init --reset
scripts/dev up
```
