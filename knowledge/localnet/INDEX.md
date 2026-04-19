# Localnet Knowledge Base

Local subnet development infrastructure.

## What is localnet?

Lightweight, isolated development environment modeling a toy subnet for rapid prototyping and testing:

- Single-node local subtensor performs real runtime operations
- Production validator code runs actual validation and weighing
- Parametrizable miner fixtures with various behaviors simulate real-world miners with various operational profiles:
  honest, malicious, malfunctioning, etc.
- Streamlined bootstrap and teardown of the environment allow testing various scenarios

## How to adapt for localnet

While this can be used for any code touching the subnet, we are primarily focused on the validator code.
External dependencies and services, including subnet-specific supporting services are simplified, replaced or mocked
out.

## Files

- **localnet.setup.md** — components, scripts, dependency order, gotchas
- **localnet.miner-fixtures.md** — creating and working on miner fixtures

## Note

Actual setup steps live in localnet/README.md and the scripts themselves. This KB covers concepts, constraints and
pitfalls. The README is user-facing, compiled by an agent during bootstrap and adapted to the specific subnet.

## Localnet gotchas

- **tempo:** locked on mainnet/testnet; on localnet, set via root sudo in bootstrap script
- **admin freeze window:** last N blocks of each tempo reject owner admin extrinsics (default 10); with default tempo=10
  every block is frozen — for any sudo calls to work, set to 0; bootstrap disables this and sets tempo to whatever is
  set in .env, probably 360 but check
- **netuid:** netuid 1 reserved and unusable; bootstrap attempts to register netuid 2
- **owner UID:** subnet owner is automatically uid 0
- **activation:** subnet inactive until start_call (after get_start_call_delay().value blocks); bootstrap does this
- **funding:** no faucet — transfer from Alice (//Alice)
- **axon IP:** 127.0.0.1 silently rejected by subtensor; use 127.0.0.2
- **pylon cache:** pylon caches metagraph; restart pylon to clear it after any miner, neuron, axon changes
- **subtensor txn collisions:** concurrent transactions cause nonce collisions; Alice transactions may fail, retries
  advised
- **miners get vpermit:** emissions accumulate and eventually cross vpermit threshold; vpermit != neuron is validator
