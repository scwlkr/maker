# File Layout

## Runtime Source

- `controller.py`: wake orchestration, model clients, settings, loop command.
- `maker_place.py`: event log, wake summaries, snapshots, lock handling.
- `sandbox.py`: Docker image, container, volume, shell, snapshot, inspect, stop.
- `tools.py`: tool schemas, shell/search/fetch execution, tool result messages.

## CLI

- `cmd/maker/main.go`: Go CLI implementation, including start/stop,
  inspection, evaluation, and dashboard commands.
- `go.mod`: Go module declaration.

## Operations

- `scripts/run-once.sh`: run one wake.
- `scripts/start.sh`: legacy wrapper to start the loop with `nohup`.
- `scripts/stop.sh`: legacy wrapper to stop the loop and active sandbox
  containers.
- `scripts/watch.sh`: tail Maker Place events.
- `scripts/show-last.sh`: show latest wake.
- `scripts/show-wake.sh`: show a specific wake.
- `scripts/inspect-world.sh`: list `/world` through the sandbox image.
- `scripts/reset-world.sh`: delete and recreate the Docker world volume.

## Containers And Config

- `Dockerfile.sandbox`: Finn sandbox image.
- `Dockerfile.controller`: controller image for compose use.
- `docker-compose.yml`: controller service definition.
- `.env.example`: documented environment defaults.

## Tests

- `tests/test_controller_unit.py`: controller and model-client units.
- `tests/test_tools.py`: fetch URL blocking and public fetch.
- `tests/test_cli.py`: Go CLI behavior.
- `tests/test_scripts.py`: shell script behavior.
- `tests/test_docker_integration.py`: Docker-backed sandbox behavior.
- `tests/conftest.py`: shared pytest fixtures and Docker availability skip.

## Related

- [Architecture overview](overview.md)
- [Docs map](../map.md)
- [Config files](../reference/config.md)
