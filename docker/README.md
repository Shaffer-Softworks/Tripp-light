# Docker dev Home Assistant

Use this stack for integration testing. It keeps changes off your production Home Assistant instance.

The compose file bind-mounts `custom_components/tripp_lite_srcool` from the repo, so code edits on the host are picked up after a reload (or container restart).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2) running
- Network access from the container to your SRCOOLNET adapter (same LAN as the host)

## Quick start

From the repo root:

```bash
cd docker
docker compose up -d
```

Open **http://localhost:8125** and complete first-time onboarding (create a dev account — not your prod credentials).

Add the integration: **Settings → Devices & services → Add integration → Tripp Lite SRCOOL** with your SRCOOLNET host, port, username, and password.

Integration debug logging is already enabled in `config/configuration.yaml`.

## Daily commands

```bash
cd docker

docker compose up -d          # start (or recreate after compose changes)
docker compose logs -f        # follow HA logs
docker compose restart        # restart after manifest/requirements changes
docker compose down           # stop (config persists under config/)
```

Reload the integration without a full restart: **Settings → Devices & services → Tripp Lite SRCOOL → ⋮ → Reload**.

After changing `manifest.json` `requirements` (e.g. new PyPI deps), restart the container so Home Assistant reinstalls dependencies.

## Verify from the host

Entity states and config entry (reads the dev HA SQLite DB):

```bash
python3 scripts/ha_docker_check.py
```

Live telnet stress test against the physical unit (does not use Home Assistant):

```bash
python3 scripts/docker_live_test.py --host 10.10.0.61 --polls 5
```

## Port and data

| Item | Value |
|------|--------|
| UI | http://localhost:8125 |
| Container name | `tripp-light-ha` |
| Config / DB | `docker/config/` (gitignored runtime files) |
| Integration mount | `../custom_components/tripp_lite_srcool` → `/config/custom_components/tripp_lite_srcool` |

Production Home Assistant typically uses port **8123**; this dev instance uses **8125** so both can run at once.

## Cursor / MCP

The Home Assistant MCP server may still point at production. For integration testing, prefer this Docker UI and `scripts/ha_docker_check.py` rather than prod MCP tools unless you explicitly reconfigure MCP to `http://localhost:8125`.

## Reset dev instance

To wipe onboarding, integrations, and entity history:

```bash
cd docker
docker compose down
rm -rf config/.storage config/home-assistant_v2.db* config/.HA_VERSION
docker compose up -d
```

Then complete onboarding again at http://localhost:8125.
