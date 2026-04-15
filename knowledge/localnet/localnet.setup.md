# Localnet Setup

## End Goal

Minimal requirements to deem the setup "working":

- subtensor starts and bootstraps with no errors
- subnet registered, starts
- miner fixtures registered and running
- validator registered and running
- validator sends challenges to miners, scores results
- validator sets scores according to subnet rules
- neurons visible on chain, neuron info correct
- weights set and available on chain; weights reflect miner performance according to subnet rules
- all miners behaving according to their profiles; miner profiles simulating failures fail in the expected way

Depending on the subnet, there may be more.

## Components

- **subtensor:** local chain, runs via docker-compose, fast blocks
- **pylon:** HTTP proxy to subtensor, runs via docker-compose, used by validator
- **validator:** long-lived process on host, connects to pylon, registered on chain
- **miner fixtures:** long-lived processes on host, behaves according to its profile

## Scripts

- **bootstrap.py** — creates owner and validator wallets, sets tempo, disables commit-reveal, registers subnet,
  registers and stakes validator
- **miners/miner.template.py** — not runnable; copy to miner-{profile}.py and customize per subnet's needs
- **miners/miner-{profile}.py** — self-registers and serves, supports -n for multi-instance

## Startup Order

1. `docker compose up` (subtensor + pylon)
2. `bootstrap.py` (one-time setup)
3. start miner fixtures (long-lived)
4. start validator (long-lived)

## Gotchas

- **tempo:** locked on mainnet/testnet; on localnet, set via root sudo in bootstrap
- **admin freeze window:** last N blocks of each tempo reject owner admin extrinsics (default 10); with default tempo=10
  every block is frozen — for any sudo calls to work, set to 0; bootstrap disables this
- **netuid:** netuid 1 reserved and unusable; bootstrap attempts to register netuid 2
- **owner UID:** subnet owner is automatically uid 0
- **activation:** subnet inactive until start_call (after get_start_call_delay().value blocks); bootstrap does this
- **funding:** no faucet — transfer from Alice (//Alice)
- **axon IP:** 127.0.0.1 silently rejected by subtensor; use 127.0.0.2
- **pylon cache:** pylon caches neurons; restart pylon to clear after miner, neuron, axon changes
- **subtensor txn collisions:** concurrent transactions cause nonce collisions; Alice transactions may fail, retries
  advised
- **miners get vpermit:** emissions accumulate and eventually cross vpermit threshold; vpermit != neuron is validator

## localnet/README Sections

Must be customized with subnet-specific information.

Suggestions for what the agent should include in the user-facing README, at least:

- how to run the validator (against any subtensor)
- how to set up and use the localnet
- how to run and customize miner fixtures
