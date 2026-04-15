# Localnet Setup

## Components

- **subtensor:** local chain, runs via docker-compose on port 9944 (
  `ghcr.io/opentensor/subtensor-localnet:devnet-ready`)
- **pylon:** HTTP proxy to subtensor, runs via docker-compose on port 8000
- **validator:** long-lived process on host, connects to pylon
- **miner stubs:** long-lived processes on host, registered on local chain

## Scripts

- **bootstrap.py** — creates owner and validator wallets, subnet, registers and stakes validator
- **miners/miner.template.py** — copy to miner-{profile}.py and customize per subnet's needs
- **miners/miner-{profile}.py** — self-registers and serves, supports -n for multi-instance

## Startup Order

1. `docker compose up` (subtensor + pylon)
2. `bootstrap.py` (one-time setup)
3. start miner stubs (long-lived)
4. start validator (long-lived)

## End Goal

Full end-to-end flow: honest miner stubs running and registered, validator discovers them via pylon, sends tasks, miners
submit results, validator scores positively, weights set on chain.

## Gotchas

- **tempo:** locked on mainnet/testnet; on localnet, set via root sudo
- **admin freeze window:** last N blocks of each tempo reject owner admin extrinsics (default 10); with default tempo=10
  every block is frozen — for any sudo calls to work, set to 0
- **netuid:** netuid 1 reserved and unusable; start with 2+
- **register_subnet netuid:** auto-assigned next free; no way to request one
- **owner UID:** owner is automatically uid 0
- **activation:** subnet inactive until start_call (after get_start_call_delay().value blocks)
- **funding:** no faucet — transfer from Alice (//Alice)
- **axon IP:** 127.0.0.1 silently rejected; use 127.0.0.2
- **pylon cache:** pylon caches neurons; restart pylon to clear after neuron or axon changes
- **miner ID:** use axon info (ip:port) to identify miners on localnet; query pylon for this # TODO: Why?
- **subtensor txn collisions:** concurrent transactions cause nonce collisions; Alice transactions may fail, retries
  advised

## Project README Sections

Suggestions for what the agent should include in the user-facing README:

- how to run the validator (against any subtensor)
- how to set up and use the localnet
- how to run and customize miner stubs
