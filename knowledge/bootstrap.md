# Bootstrap

Guidelines for completing tasks when working on Bittensor subnets. If a task matches, all its rules must be applied and
its workflow closely followed.

Do not mention specific tasks you do or files you load, it's irrelevant to the user.

## Designing Subnet

**requires:** user's subnet idea
**grounding knowledge:** bittensor
**do not load:** nexus, pylon, localnet, anything else
**definition of done:**

- all design rules discovered and met
- subnet design approved by user
- subnet design written to a file

**after done:** start implementing validator

## Implementing Validator

**requires:** subnet design approved by user
**grounding knowledge:** bittensor, nexus, pylon
**do not load:** localnet
**definition of done:**

- project directory ready for development
- validator.py created
- all validator error sources wired up to some logger
- README.md created / rewritten; contains brief subnet description; doesn't reiterate subnet design
- QA gates pass

**after done:** start setting up localnet

## Setting Up Localnet

**requires:** validator implemented
**grounding knowledge:** bittensor/subnet.lifecycle, localnet
**definition of done:**

- compose.yml adapted to subnet
- .env.example adapted to subnet; grouped; tweakable vars first, then constants
- localnet/bootstrap.py adapted to subnet if needed
- honest miner fixture profile created from miner.template.py
- README.md updated; added: required config, steps to run locally, managing localnet setup, running validator, running
  miner fixtures
- end-to-end flow works: all goals described in localnet/localnet.setup.md
- no temporary workarounds left; setup is clean and has good DX; all components work together and perform the subnet's
  designed goals;

## Default

When no task matches, infer grounding knowledge and definition of done from context.
