# Stub Miners

**scope:** good miners only — adversary profiles added later based on subnet design anti-gaming measures

## No Local Compute
Miner stubs should not perform heavy work locally. Delegate to external services where possible (e.g. inference via OpenRouter, requires API key).

## Naming
- **MINER_NAME:** short, descriptive of the profile behavior
- **instance name:** {MINER_NAME}-{index} — index always appended, even for single instance
- **file:** localnet/miners/miner-{profile}.py
- **example:** localnet/miners/miner-honest.py

## Structure
- one file per profile
- standalone script with PEP 723 inline deps
- suggested deps: litestar, httpx, click

## Multi-Instance
- **mechanism:** click option `-n`, default 1
- **effect:** spawns N instances from same profile on random ports
- **wallet:** created automatically, named {MINER_NAME}-{index} per instance
- **funding:** self-funds from Alice (//Alice) on first run

## CLI Args
Miner stubs may accept additional CLI args via click (e.g. API keys, model names).
