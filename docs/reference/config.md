# Config Files

## `.env.example`

Example runtime environment file. Copy it to `.env` for local use:

```bash
cp .env.example .env
```

`.env` is ignored by git.

## Dockerfiles

- `Dockerfile.sandbox` builds the Ubuntu sandbox image used for Finn wakes and
  world inspection.
- `Dockerfile.controller` builds a Python controller image with Docker CLI
  installed.

## Docker Compose

`docker-compose.yml` defines a `controller` service that builds
`Dockerfile.controller`, loads `.env`, mounts the host Docker socket, mounts
`./maker-place` into `/app/maker-place`, and runs `python controller.py loop`.

Current tests do not verify the compose service. See
[needs verification](../todo/needs-verification.md).

## Git Ignore Rules

`.gitignore` excludes `.env`, Python caches, `.venv`, `bin/`, and generated
Maker Place contents while keeping `maker-place/.gitkeep`.

`.dockerignore` excludes `.env`, `.git`, Python caches, `.venv`, and Maker Place
from Docker build context.

## Related

- [Environment variables](env.md)
- [Workspace model](../concepts/workspace.md)
- [Dependencies](../architecture/dependencies.md)
