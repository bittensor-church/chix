# Context

This is the cat-inpainting Bittensor subnet: miners receive a user-submitted
photo and return the same photo with one additional natural-looking cat added.
The validator (`validator.py`) routes user traffic to miners, judges outputs
with a VLM via OpenRouter, and sets per-miner weights each epoch.

See `README.md` for operator docs and `subnet_design.md` for the full design
(what is measured, scoring formula, trust analysis, deferred items).

Originally adapted from the Nexus subnet template. The bootstrap workflows in
`knowledge/tasks.project-bootstrap.md` describe the original
"design → implement validator → set up localnet" path; the design and validator
phases are complete and live in `subnet_design.md` / `validator.py`. Later
phases (localnet adaptation, etc.) may still be open — consult that file if
something appears unfinished.

# Knowledge base

## Preparing for tasks

Start by discovering the information available in the knowledge base with `find knowledge -type f | sort`
Crucially: Never summarize index files. Never delegate reading indices to agents or exploration tools.
During your tasks and conversations, eagerly read additional files if they could be relevant.
After compaction, re-read indices directly and read relevant files again so as not to forget crucial details.

## Bittensor domain

Whenever Bittensor domain knowledge is required, focus on the Bittensor knowledge files and skip the rest.
It is important to first understand the specifics of the Bittensor ecosystem, work with high-level concepts,
and iterate on the subnet's design rather than jumping straight into implementation details. Designing a subnet is
a complex reasoning process and requires careful consideration on multiple levels.

Contains, among others:

- how to frame subnet ideas into the bittensor ecosystem
- requirements and invariants that must be satisfied by a good subnet design
- theory behind validation, mining, incentives, miner-validator contract
- suggested external integrations and tools in the ecosystem

Index: knowledge/bittensor/INDEX.yaml
Recommended subnet design location: ./subnet_design.md (create when needed)

## Nexus

Nexus is the framework for building Bittensor subnet validators. It replaces the
bittensor SDK for validator development. All validator code runs inside Nexus — it is
the complete runtime. You must use Nexus for implementing the validator.

Nexus provides a large set of reusable components that handle common validator concerns.
Before writing any code, making any decisions, or responding with recommendations —
discover what Nexus offers. It will likely already handle most of the requirements
of the subnet you are working on.

The Nexus knowledge base ships with the Nexus package — find it in `.venv` within the
installed Nexus package under `docs/`. Make sure Nexus is installed first (follow this
project's package management guidelines). Read `docs/nexus.md` in the Nexus package — it
is the grounding document for all validator implementation work.

Skip for higher level tasks that do not touch the code.

### Pylon

Sidecar subtensor communication proxy. Nexus uses Pylon for all subtensor (blockchain) communication.
The pylon client's source code can be found and inspected in `.venv`.

Skip for higher level tasks that do not touch the code.

## localnet

Local development environment that allows running a subnet locally, as opposed to testnet or mainnet.
KB contains everything needed to set it up and operate it: templates, recipes, requirements, operational guidelines,
best practices, gotchas, and much more.

Index: knowledge/localnet/INDEX.md
Localnet resources: localnet/*

Read when working on or debugging issues during development on localnet.
Skip for higher level tasks that do not touch the code.

## Coding guidelines

Location: knowledge/guidelines.coding-and-qa.md

Conventions, tooling, best practices, QA gates, comments, documentation, and more.

Read when working with any kind of code, be it validator, localnet, or any other code in this repository.
Skip for higher level tasks that do not touch the code.

# General hints

- use `uv` instead of `python` for managing dependencies, running scripts, entrypoints, ad-hoc code
    - `uv add ...` / `uv remove ...` / `uv sync` (+ `--all-groups`, `--all-extras`)
    - `uv run --with foo,bar ...` (with temporary dependencies)
    - `uv run python -c '...'` / `uv run some/script.py` (code or script)

# Documentation rules

Keep README.md, AGENTS.md, tests, docstrings, and code up to date and in sync. If one changes, update the others.
Whenever updated, all information, claims, guides, commands, etc. in these files must be verified and tested.
Take great care to avoid drift between these files.


---

Note: CLAUDE.md and .cursorrules both link to CLAUDE.md - they are all the same file. No need to re-read it. 