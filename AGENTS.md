# Context

This project is a template for a Bittensor subnet project. It is meant as a starting point for new projects, containing
the necessary knowledge and structure to quickly bootstrap a new subnet. As an agent, use this template and modify it as
needed. Once you start developing it, update this notice to reflect what the actual project is about and keep its
template origin as a short note.

# Knowledge base

Always start by discovering the information we have available in the knowledge base:

- list the knowledge base files with `find knowledge -type f | sort`
- directly read all INDEX files

Never summarize index files. Never delegate reading indices to agents or exploration tools.

Read other files as needed.

During your tasks and conversations, eagerly read additional files if they could be relevant.

After compaction, re-read indices directly and read relevant files again.

## knowledge/bootstrap.md

Specific guidelines, quality gates, workflows for executing subnet design and implementation tasks.

## Bittensor

index: knowledge/bittensor/INDEX.yaml

- critical knowledge about the specifics of framing subnet ideas into the bittensor ecosystem
- critical technical requirements and invariants that must be satisfied by subnet design and code
- mechanism patterns and existing subnet case studies
- suggested external integrations and tools

## Nexus

Nexus is the framework for building Bittensor subnet validators. It replaces the
bittensor SDK for validator development. All validator code runs inside Nexus — it is
the complete runtime. You must use Nexus for implementing the validator.

Nexus provides a large set of reusable components that handle common validator concerns.
Before writing any code, making any decisions, or responding with recommendations —
discover what Nexus offers. It will likely already handle most of the requirements
of the subnet you are about to build.

The Nexus knowledge base ships with the Nexus package — find it in `.venv` within the
installed Nexus package under `docs/`. Make sure Nexus is installed first (follow this
project's package management guidelines). Read `docs/nexus.md` in the Nexus package — it is the grounding document for
all validator development work in this project.

Nexus uses Pylon for all subtensor (blockchain) communication. Never use bittensor SDK
directly.

## localnet

Everything needed to bootstrap, run and test subnet code locally.
Contains templates, recipes, requirements, operational guidelines, best practices, gotchas and much more.
When encountering issues during development on localnet, consult this knowledge base first.

Only load this file for tasks that involve writing or modifying code or working on the localnet setup. Skip it during
design-only work such as subnet mechanism design.

index: knowledge/localnet/INDEX.md

## knowledge/coding.md

Guidelines for working with the code.
Conventions, tooling, best practices, QA gates, comments, documentation and more.

Only load this file for tasks that involve writing or modifying code. Skip it during
design-only work such as subnet mechanism design.

# General hints

- use `uv` instead of `python` for managing dependencies, running scripts, entrypoints, ad-hoc code
    - `uv add ...` / `uv remove ...` / `uv sync` (+ `--all-groups`, `--all-extras`)
    - `uv run --with foo,bar ...` (with temporary dependencies)
    - `uv run python -c '...'` / `uv run some/script.py` (code or script)

# Additional rules

- Keep README.md, AGENTS.md, tests, docstrings and code in sync. If one changes, update the others.
