# Localnet Setup

## Components
- **subtensor:** local chain, runs via docker-compose on port 9944 (`ghcr.io/opentensor/subtensor-localnet:devnet-ready`)
- **pylon:** HTTP proxy to subtensor, runs via docker-compose on port 8000
- **validator:** long-lived process on host, connects to pylon
- **miner stubs:** long-lived processes on host, registered on local chain

## Scripts
- **bootstrap.py** — creates owner and validator wallets, subnet, registers and stakes validator
- **miners/miner.template.py** — copy to miner-{profile}.py and customize per subnet
- **miners/miner-{profile}.py** — self-registers and serves, supports -n for multi-instance

## Startup Order
1. `docker compose up` (subtensor + pylon)
2. `bootstrap.py` (one-time setup)
3. start miner stubs (long-lived)
4. start validator (long-lived)

## End Goal
Full end-to-end flow: honest miner stubs running and registered, validator discovers them via pylon, sends tasks, miners submit results, validator scores positively, weights set on chain.

## Gotchas
- **tempo:** locked on mainnet/testnet, may be settable on localnet depending on subtensor version
- **netuid:** netuid 1 reserved and unusable; start with 2+
- **owner UID:** register_subnet auto-registers owner as uid 0
- **activation:** subnet inactive until start_call (after get_start_call_delay().value blocks)
- **funding:** no faucet — transfer from Alice (//Alice)
- **axon IP:** 127.0.0.1 silently rejected; use 127.0.0.2
- **pylon cache:** start miners before pylon or restart pylon after
- **miner ID:** use axon info (ip:port) to identify miners on localnet; query pylon for this
- **subtensor txn collisions:** concurrent transactions cause nonce collisions; Alice transactions may fail, retries advised

## Project README Sections
Suggestions for what the agent should include in the user-facing README:
- how to run the validator (against any subtensor)
- how to set up and use the localnet
- how to run and customize miner stubs
