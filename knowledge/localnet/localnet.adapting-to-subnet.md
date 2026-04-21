# Adapting localnet setup to a specific subnet

## End Goal

Minimum requirements to deem the setup "working":

- subtensor starts and bootstraps with no errors
- subnet registered, starts
- miner fixtures registered and running
- validator registered and running
- validator sends challenges to miners, scores results
- validator sets scores according to subnet rules
- neurons visible on chain, neuron info correct
- weights set and available on chain; weights reflect miner performance according to subnet rules
- all miners behaving according to their profiles
- chain-related goals are verified against subtensor directly, bypassing nexus and pylon

Minimum set of tasks to do:

- files in `localnet/` directory discovered and adapted to the subnet according to the subnet's design
- miner fixtures created, see localnet/localnet.miner-fixtures.md

## localnet/README Sections

Must be customized with subnet-specific information.

Targeted at both human and AI readers.

Suggestions for what the agent should include in the user-facing README, at least:

- how to run the validator (against any subtensor)
- how to set up and use the localnet
- how to run and customize miner fixtures

All claims and instructions must be verified and correct.
