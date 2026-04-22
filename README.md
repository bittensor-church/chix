# Cat-inpainting subnet

A Bittensor subnet where miners add a natural-looking cat to user-submitted
photos. Users drop an image in, get the same image back with one more cat in it.

The design — what is measured, how miners are scored, what trust assumptions hold
— lives in [`subnet_design.md`](./subnet_design.md). The validator is a single
`validator.py` built on [Nexus](https://github.com/bittensor-church/bittensor-pylon).

Originally based on the Nexus subnet template.

## Validator

### Configuration

```sh
cp .env.example .env
# fill in VALIDATOR_EXTERNAL_IP and VALIDATOR_OPENROUTER_API_KEY
```

Required environment (`.env` or process env):

| Variable | Description |
|---|---|
| `NETUID` | Subnet UID (localnet bootstrap assigns netuid 2) |
| `VALIDATOR_NETUID` | Same value; read by the validator settings |
| `VALIDATOR_EXTERNAL_IP` | Externally reachable IP of this host. Advertised to miners as the async callback target |
| `VALIDATOR_OPENROUTER_API_KEY` | OpenRouter API key used by the VLM judge |
| `VALIDATOR_PYLON_SERVICE_ADDRESS` | Pylon sidecar URL (default: `http://localhost:8000`) |
| `VALIDATOR_PYLON_OPEN_ACCESS_TOKEN` | Pylon open-access token |
| `VALIDATOR_PYLON_IDENTITY_NAME` | Pylon identity name for this validator |
| `VALIDATOR_PYLON_IDENTITY_TOKEN` | Pylon identity token |

Optional (all have sensible defaults — see `ValidatorSettings` in `validator.py`):

- `VALIDATOR_REST_ENTRY_POINT_PORT` (default `8081`) — user-facing ingress
- `VALIDATOR_MINER_CALLBACK_PORT` (default `9091`) — miner callback listener
- `VALIDATOR_OPENROUTER_MODEL` (default `google/gemini-3-flash-preview`)
- `VALIDATOR_NATURALNESS_WEIGHT`, `VALIDATOR_PRESERVATION_WEIGHT`,
  `VALIDATOR_RELIABILITY_EXPONENT` — scoring coefficients (tunable)

### Running

```sh
uv run python validator.py
```

The validator exposes `POST /inpaint` on `VALIDATOR_REST_ENTRY_POINT_PORT`.
Request body: `{"image_b64": "<base64 jpeg or png>"}`. Response body: same shape,
with a new cat in the image.

Both `/inpaint` and the miner callback server bind to `0.0.0.0` by default.

### How it works (short)

1. The user posts an image to `/inpaint`.
2. The validator picks one registered miner at random (no fanout, no retries)
   and forwards the image via Nexus's async HTTP protocol.
3. The miner returns its inpainted image; the validator returns it to the user
   as-is (no pre-return validation — reliability scoring is the correction path).
4. In parallel, every successful mining result is sent to the VLM judge
   (OpenRouter, Gemini 3 Flash) for `cat_added` / `naturalness` / `preservation`
   scoring.
5. At each epoch boundary, per-miner weights are computed from stored task
   results: `mean_quality * reliability ^ reliability_exponent`.

Full design and trust analysis: [`subnet_design.md`](./subnet_design.md).

## Development

### Prerequisites

- Python 3.14
- [uv](https://github.com/astral-sh/uv)

### Setup

```sh
uv sync --all-groups --all-extras
```

### QA gates

All three must pass. Run in order:

```sh
uv run ruff check --fix && uv run ruff format
uv run basedpyright
uv run pytest -q --tb=line -r f
```

See [`knowledge/guidelines.coding-and-qa.md`](./knowledge/guidelines.coding-and-qa.md).

## Localnet

See [`localnet/README.md`](./localnet/README.md) for the full end-to-end local
development flow (local subtensor + pylon + bootstrap + miner fixtures).
