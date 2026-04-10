# Bootstrap

Guidelines for completing tasks when working on Bittensor subnets. If a task matches, all its rules must be applied and its workflow closely followed.

## Designing Subnet

**requires:** user's subnet idea
**grounding knowledge:** bittensor
**do not load:** nexus, pylon
**definition of done:**
- all design rules discovered and met
- subnet design approved by user
- subnet design written to a file

**after completion:** start implementing validator automatically

## Implementing Validator

**requires:** subnet design approved by user, uv sync
**grounding knowledge:** bittensor, nexus, pylon
**do not load:** localnet
**definition of done:**
- project directory ready for development
- validator.py created
- README.md created / rewritten; contains brief subnet description; doesn't reiterate subnet design
- QA gates pass

**after completion:** start setting up localnet automatically

## Setting Up Localnet

**requires:** validator implemented
**grounding knowledge:** bittensor/subnet.lifecycle, localnet
**definition of done:**
- localnet/docker-compose.yml adapted to subnet
- localnet/.env.example adapted to subnet
- localnet/bootstrap.py adapted to subnet if needed
- miner stub profiles created from miner.template.py
- README.md updated; added: required config, steps to run locally, managing localnet setup, running validator, running miner stubs
- end-to-end flow works: localnet bootstrap, miner stubs and validators cooperate, weights are being set

**additional quality gates:**
- no temporary workarounds left in place; setup is clean and has good DX

## Default

When no task matches, infer grounding knowledge and definition of done from context.
