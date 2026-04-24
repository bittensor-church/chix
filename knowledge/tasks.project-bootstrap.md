# Designing Subnet

**requires:** user's subnet idea
**grounding knowledge:** bittensor
**do not load:** nexus, pylon, localnet, coding guidelines
**definition of done:**

- all design rules discovered and met
- subnet design approved by user
- subnet design written to a file

**after done:** start implementing validator

# Implementing Validator

**requires:** subnet design approved by user
**grounding knowledge:** bittensor, subnet design, nexus
**do not load:** localnet
**definition of done:**

- project directory ready for development
- validator.py created
- README.md adapted to subnet; template-related info removed; contains brief subnet description; doesn't
  reiterate subnet design
- QA gates pass

**after done:** start setting up localnet

# Setting Up Localnet

**requires:** validator implemented
**grounding knowledge:** bittensor/subnet.lifecycle.yaml, localnet
**definition of done:**

- localnet adapting complete as specified by localnet/localnet.adapting-to-subnet.md
- end-to-end flow works as described in localnet/localnet.adapting-to-subnet.md
- no temporary workarounds left
- repo is clean and has good DX
- all localnet components work together and perform the subnet's designed goals
- root README.md updated; added at least: localnet section with steps to run, configure, pointer to localnet
  readme for dev setup
- all claims and instructions in READMEs verified and correct
- subnet-specific artifacts, if relevant, proving the subnet's work prepared and presented to the user (but not
  committed)

---

TODO: more to come.