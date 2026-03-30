# Cat Inpainting Subnet

Bittensor subnet where users submit images and miners inpaint realistic cats into them.
The original image must be pixel-identical outside the inpainted region.

Built with [ChiX](https://github.com/...) (Chi's brain, Nexus's backbone).

## How it works

1. Validator sends a PNG image to a miner's `POST /inpaint` endpoint
2. Miner runs an inpainting model, adds a realistic cat, returns the result
3. Validator scores the result on four dimensions:
   - **Background preservation (40%)** -- pixel-exact comparison outside the modified region
   - **Cat presence (25%)** -- VLM assessment via OpenRouter
   - **Inpainting quality (25%)** -- VLM assessment of seamlessness
   - **Speed (10%)** -- response latency
4. EMA-smoothed scores become on-chain weights via Yuma Consensus

## Miner interface

```
POST /inpaint
Content-Type: application/json

{"image_b64": "<base64 PNG>"}

Response: {"image_b64": "<base64 PNG with cat>"}
```

- PNG format mandatory (lossless, enables exact pixel comparison)
- Miner chooses where to place the cat
- Auth: Epistula signed headers

## Running the validator

```sh
uv sync --all-groups

# Required environment variables
export NETUID=<your subnet netuid>
export OPENROUTER_API_KEY=<your key>
export CALLBACK_BASE_URL=http://<your-public-ip>:9100

# Pylon (subtensor proxy) must be running
export VALIDATOR_PYLON_SERVICE_ADDRESS=http://localhost:8000
export VALIDATOR_PYLON_OPEN_ACCESS_TOKEN=<token>
export VALIDATOR_PYLON_IDENTITY_NAME=<identity>
export VALIDATOR_PYLON_IDENTITY_TOKEN=<token>

uv run python validator.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `NETUID` | (required) | Subnet UID |
| `OPENROUTER_API_KEY` | (required) | OpenRouter API key for VLM scoring |
| `CALLBACK_PORT` | `9100` | Port for miner callback responses |
| `CALLBACK_BASE_URL` | `http://localhost:9100` | Public URL miners use for callbacks |
| `OPENROUTER_MODEL` | `google/gemini-2.5-flash` | VLM model for scoring |
| `TASK_INTERVAL_SECONDS` | `30.0` | Interval between synthetic test tasks |
| `MAX_LATENCY_SECONDS` | `120.0` | Maximum acceptable response time |

## Development

```sh
uv sync --all-groups
uv run ruff check --fix && uv run ruff format
uv run basedpyright
uv run pytest -q --tb=line -r f
```
