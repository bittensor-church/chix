# Miner Fixtures

Miner fixtures are local-only scripts that stand in for miners so the validator can be exercised end-to-end on localnet.
Each fixture is one profile — one behavior the subnet needs to observe to verify its scoring. They are not reference
implementations, not suggested mining strategies, and never ship as production code; their job is to make the subnet
runnable, not to show how to mine it.

Miner fixtures must not perform heavy work locally. Delegate to external services where possible (e.g. inference via
OpenRouter).

## Naming

- **MINER_NAME:** short, descriptive of the profile behavior
- **instance name:** {MINER_NAME}-{index} — index always appended, even for single instance
- **file:** localnet/miners/miner-{profile}.py
- **example:** localnet/miners/miner-honest.py

## Structure

- one file per profile
- standalone script with PEP 723 inline deps
- suggested deps: litestar, httpx, click, python-dotenv

## Multi-Instance

- **mechanism:** click option `-n`, default 1
- **effect:** spawns N instances from same profile on random ports
- **wallet:** created automatically, named {MINER_NAME}-{index} per instance
- **registration and funding:** if needed, self-funds from Alice and self-registers on startup; noop otherwise

## CLI Args

Miner fixtures may accept additional CLI args via click (e.g. model names).
