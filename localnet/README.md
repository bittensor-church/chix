# Localnet

Run a complete local subnet for development and testing.

## Prerequisites

- Docker and Docker Compose
- uv

## Infrastructure

```sh
docker compose up -d
```

Starts a local subtensor blockchain (port 9944) and a pylon proxy (port 8000).

## Bootstrap

```sh
uv run localnet/bootstrap.py
```

Creates owner and validator wallets, funds them from Alice (pre-funded devnet account), creates subnet (netuid 2), and registers + stakes the validator. Idempotent — safe to re-run.

## Running the validator

```sh
cp .env.example .env
uv run python validator.py
```

The `.env.example` is pre-configured to connect to the local pylon.

## Miner fixtures

Good miner profiles only. Adversarial profiles are TODO.

Each miner profile is a standalone script in `localnet/miners/`. Copy `miner.template.py` to create a new profile:

Each instance finds a free port and self-registers on the subnet

### Creating a new profile

Copy the template and customize:

```sh
cp localnet/miners/miner.template.py localnet/miners/miner-yourname.py
# edit MINER_NAME, TARGET_PATH, handle_request(), anything else necessary for the subnet
```


## Resetting

Full reset — clears chain state. Restart any running miners and validators afterwards so they re-register against the fresh chain.

```sh
docker compose down && docker compose up -d
```

Restart chain only:

```sh
docker compose restart subtensor
```
