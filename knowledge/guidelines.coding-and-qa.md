# Coding guidelines

## Tech to use

- Python 3.14
- astral uv
- basedpyright strict mode
- ruff for linting and formatting
- pytest
- nexus as a framework for validator (no bittensor dependency)
- pylon for subtensor communication

Read nexus and pylon source from .venv when you need to research them - after having installed them first.

## QA gates

All must pass. Run in order.

```sh
uv run ruff check --fix && uv run ruff format
uv run basedpyright
uv run pytest -q --tb=line -r f
```

Never loosen any basedpyright rules – globally or locally.

## Code style

- All imports at top of file. No inline imports
- Short, concise code. Avoid deep nesting
- Prefer well-typed code:
    - prefer typed structures (dataclass, BaseModel, NamedTuple) over raw dicts, lists, tuples
- Avoid primitive types, especially:
    - use NewType or typed wrappers for semantic values
    - use DateTime, Date, Time, timedelta for date/time related values
- Never use hasattr/getattr on typed objects
- No dead code - clean up proactively
- No assertions in production - raise specific exceptions
- No workarounds - fix, restructure and refactor instead
- No overly defensive code

## Comments

- Never restate what code does
- Do explain non-obvious logic and gotchas
- Create and update docstrings for public classes, functions, modules

## Ownership

You own the code and are responsible for it, whether you wrote it or not. Seemingly unrelated issues are yours
to resolve:

- simple things – immediately
- unknowns and others – after the task at hand