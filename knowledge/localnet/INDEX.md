# Localnet Knowledge Base

Local subnet development infrastructure.

## What is localnet?

Lightweight, isolated development environment modeling a toy subnet for rapid prototyping and testing:

- Single-node local subtensor performs real runtime operations
- Production validator code runs actual validation and weighing
- Parametrizable miner fixtures with various behaviors simulate real-world miners with various operational profiles:
  honest, malicious, malfunctioning, etc.
- Streamlined bootstrap and teardown of the environment allow testing various scenarios

## Components

- **subtensor:** local chain, runs via docker-compose, fast blocks
- **pylon:** HTTP proxy to subtensor, runs via docker-compose, used by validator
- **validator:** long-lived process on host, connects to pylon, registered on chain
- **miner fixtures:** long-lived processes on host, behave according to their profile

## Resources

- **bootstrap.py** — creates owner and validator wallets, sets tempo, disables commit-reveal, registers subnet,
  registers, and stakes validator
- **miners/miner.template.py** — not runnable; copy to miner-{profile}.py and customize per subnet's needs
- **miners/miner-{profile}.py** — created miner fixtures go here; they self-register and serve, support -n for
  multi-instance
- **wallets/** — stores all wallets for localnet; ~/.bittensor must never be used for localnet

## Startup Order

1. `cd localnet && docker compose up` (subtensor + pylon)
2. `bootstrap.py` (one-time setup)
3. start miner fixtures (long-lived)
4. start validator (long-lived)

## Adapting the subnet for localnet

Localnet can be used for any code touching the subnet but we are focused on validator code.
External dependencies and services, including subnet-specific supporting services are simplified, replaced, or mocked
out.

## Files

- **localnet.adapting-to-subnet.md** — workflow and definition of done for adapting localnet setup
- **localnet.miner-fixtures.md** — designing, creating, working on, and using miner fixtures

## Localnet gotchas

- **tempo:** locked on mainnet/testnet; on localnet, set via root sudo in bootstrap script
- **admin freeze window:** last N blocks of each tempo reject owner admin extrinsics (default 10); with default tempo=10
  every block is frozen — for any sudo calls to work, set to 0; bootstrap disables this and sets tempo to whatever is
  set in localnet/.env, probably 360 but check
- **netuid:** netuid 1 reserved and unusable; bootstrap attempts to register netuid 2
- **owner UID:** subnet owner is automatically uid 0
- **activation:** subnet inactive until start_call (after get_start_call_delay().value blocks); bootstrap does this
- **funding:** no faucet — transfer from Alice (//Alice)
- **axon IP:** 127.0.0.1 silently rejected by subtensor; use 127.0.0.2
- **pylon cache:** pylon caches metagraph; restart pylon to clear it after any miner, neuron, axon changes
- **subtensor txn collisions:** concurrent transactions cause nonce collisions; Alice transactions may fail, retries
  advised
- **miners get vpermit:** emissions accumulate and eventually cross vpermit threshold; vpermit != neuron is validator
