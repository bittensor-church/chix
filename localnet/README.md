# Localnet

Run a complete local subnet for development and testing.

## Prerequisites

- Docker and Docker Compose
- uv

## Infrastructure

Start a local subtensor and pylon:

```sh
docker compose -f localnet/docker-compose.yml up -d
```

This starts a local subtensor blockchain (port 9944) and a pylon proxy (port 8000).

## Bootstrap

Create wallets, subnet, and register the validator:

```sh
uv run localnet/bootstrap.py
```

Creates owner and validator wallets, funds them from Alice (pre-funded devnet account), creates subnet (netuid 2), and registers + stakes the validator. Idempotent — safe to re-run.

## Running the validator

```sh
cp localnet/.env.example .env
uv run python validator.py
```

The `.env.example` is pre-configured to connect to the local pylon.

## Stub miners

Each miner profile is a standalone script in `localnet/miners/`. Copy `miner.template.py` to create a new profile:

```sh
cp localnet/miners/miner.template.py localnet/miners/miner-honest.py
# edit MINER_NAME, TARGET_PATH, handle_request()
```

Run a miner:

```sh
uv run localnet/miners/miner-honest.py       # single instance
uv run localnet/miners/miner-honest.py -n 3  # three instances
```

Each instance finds a free port automatically and self-registers on the subnet with wallet name `{MINER_NAME}-{index}`.

## Resetting

```sh
# Full reset (chain state + wallets)
docker compose -f localnet/docker-compose.yml down -v
rm -rf localnet/wallets/

# Restart chain only (keeps wallets)
docker compose -f localnet/docker-compose.yml restart subtensor
```
