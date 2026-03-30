# Context

Cat Inpainting Subnet -- a Bittensor subnet where miners add realistic cats to user-submitted images via inpainting.
Built from the ChiX template for Bittensor subnet development.

# Behavioral guidelines

ALWAYS start by reading knowledge/INDEX.yaml directly - follow any instructions within. Discover ALL relevant rules,
gates, invariants, expectations relevant to your tasks and make sure they are satisfied at all times.

# Coding guidelines

## Project preparation

```uv sync --all-groups```

## Tech to use

- Python 3.14
- astral uv
- basedpyright strict mode
- ruff for linting and formatting
- pytest
- litestar for HTTP endpoints
- nexus as a framework for validator (no bittensor dependency)
- pylon for subtensor communication

Read nexus and pylon source from .venv when you need to research them.

NEVER use `pip`, NEVER use `python` directly. `uv` has all the tools you need:

- `uv add ...` to add dependencies
- `uv run ...` to run code
- `uv run python ...` to run python

## QA gates

All must pass. Run in order.

```sh
uv run ruff check --fix && uv run ruff format
uv run basedpyright
uv run pytest -q --tb=line -r f
```

## Code style

- All imports at top of file. No inline imports.
- Short, concise code. Avoid deep nesting.
- Well-typed. Prefer typed structures over dicts.
- Domain types over bare str/int/float. Use NewType or typed wrappers for semantic values.
- datetime.timedelta for durations, not raw seconds.
- No hasattr/getattr on well-typed objects.
- No dead code.
- No assertions in production -- raise specific exceptions.
- Restructure over workaround.

## Comments

- Never restate what code does.
- Do explain non-obvious logic and gotchas.

## Documentation

- Keep README.md, AGENTS.md, docstrings in sync with code.
- Document public classes, functions, modules.
