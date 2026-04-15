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
