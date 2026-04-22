# Localnet

A full local subnet — subtensor chain, pylon, validator, and at least one
miner — for developing and verifying the cat-inpainting subnet end to end.

## Prerequisites

- Docker + Docker Compose (tested with Compose v2)
- [uv](https://github.com/astral-sh/uv)
- An OpenRouter API key with access to `google/gemini-3-flash-preview`
  (validator VLM judge) and `bytedance-seed/seedream-4.5` (miner fixture
  inpainting backend)

## Startup order

Bring everything up in order. Each step is idempotent.

```sh
# 1. Infrastructure: subtensor (port 9944) and pylon (port 8000)
docker compose up -d

# 2. Configure env for the validator (and reused by the miner fixture)
cp .env.example .env
# edit .env and set VALIDATOR_OPENROUTER_API_KEY

# 3. One-time chain setup: owner + validator wallets, subnet netuid 2,
#    tempo=360, commit-reveal disabled, admin-freeze-window disabled,
#    validator registered and staked.
uv run localnet/bootstrap.py

# 4. Start at least one miner — self-funds from Alice and self-registers.
uv run localnet/miners/miner-honest.py

# 5. Pylon caches the metagraph; restart it so the validator sees the
#    freshly registered miner. (See "Gotchas" below.)
docker compose restart pylon

# 6. Start the validator.
uv run python validator.py
```

Keep the validator and miners in separate terminals (or background them with
``nohup``). The validator exposes ``POST /inpaint`` on port 8081.

## Exercising the subnet

Send an image to the validator's ingress endpoint. The round trip (user →
validator → miner → OpenRouter Seedream → callback → VLM scoring) typically
takes 15–30 seconds per request.

```sh
# Prepare a base64 request body from a local image.
python3 -c "import json,base64; \
  print(json.dumps({'image_b64': base64.b64encode(open('photo.jpg','rb').read()).decode()}))" \
  > /tmp/inpaint_body.json

# Send the request.
curl -sS -m 180 -X POST http://localhost:8081/inpaint \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/inpaint_body.json \
  -o /tmp/inpaint_response.json \
  -w "HTTP %{http_code}\n"

# Decode the returned image.
python3 -c "import json,base64; \
  open('/tmp/inpaint_output.jpg','wb').write( \
    base64.b64decode(json.load(open('/tmp/inpaint_response.json'))['image_b64']))"
```

At the next epoch boundary (tempo=360 blocks, ~1–2 min on localnet) the
validator runs the VLM judge over scored pairs, computes per-miner weights,
and submits them to pylon. Confirm on-chain weights directly, bypassing
nexus and pylon:

```sh
uv run --with bittensor python -c "
import bittensor as bt
sub = bt.Subtensor(network='ws://127.0.0.1:9944')
mg = sub.metagraph(netuid=2, lite=False)
print(f'block={sub.get_current_block()} neurons={len(mg.neurons)}')
for n in mg.neurons:
    print(f'  uid={n.uid} hotkey={n.hotkey[:16]}... vp={n.validator_permit} '
          f'axon={n.axon_info.ip}:{n.axon_info.port} incentive={float(n.incentive):.4f}')
print('weights matrix W[validator_uid][miner_uid]:')
print(mg.W)
"
```

## Miner fixtures

Fixtures are local-only scripts that simulate miners so the validator can be
exercised end-to-end. They self-fund from Alice and self-register on
startup.

Available profiles:

- **`miner-honest.py`** — calls OpenRouter's Seedream 4.5 to actually add a
  cat. Delegates the heavy work to OpenRouter per the miner-fixtures
  guidance. Reads `MINER_OPENROUTER_API_KEY` from env, falling back to
  `VALIDATOR_OPENROUTER_API_KEY` so the same `.env` works for both.

Run one instance:

```sh
uv run localnet/miners/miner-honest.py
```

Run several in parallel (each with its own wallet):

```sh
uv run localnet/miners/miner-honest.py -n 3
```

### Creating a new profile

Copy the template and customize `MINER_NAME`, `TARGET_PATH`, and the
request-handling logic:

```sh
cp localnet/miners/miner.template.py localnet/miners/miner-<profile>.py
```

Keep fixtures minimal — they exist to make the validator testable, not to
demonstrate a mining strategy. Delegate anything heavy (model inference,
storage) to external services.

## Gotchas

- **Pylon caches the metagraph.** After a miner registers or an axon is
  updated, the validator will not see the change until pylon is restarted
  (``docker compose restart pylon``).
- **Axon IP 127.0.0.1 is silently rejected** by subtensor. The fixture
  template uses 127.0.0.2 — keep that convention for any new profile.
- **Tempo and commit-reveal** are both locked on mainnet/testnet. Bootstrap
  sets tempo=360 and disables commit-reveal via sudo for localnet.
- **Netuid 1 is reserved** and unusable. Bootstrap registers netuid 2; the
  `.env` must match.
- **Alice transactions can collide** under concurrent load. Bootstrap and
  the miner fixture both retry.
- **First epoch with no traffic** — the validator still fires the weight
  setter at the first epoch boundary, but has no scored data yet. Pylon
  rejects the empty weights submission with a pydantic validation error;
  the validator logs this as an error and keeps going. The next epoch
  after real traffic clears the condition.
- **127.0.0.53 DNS stub can be flaky** in some container environments,
  which breaks the miner's OpenRouter calls. If you see ``Temporary
  failure in name resolution`` in the miner log, point ``/etc/resolv.conf``
  at a public resolver (e.g. ``nameserver 1.1.1.1``).

## Reset

Full reset — clears chain state and all wallets. Re-run bootstrap afterwards.

```sh
docker compose down && rm -rf localnet/wallets/*/
docker compose up -d
```

Chain-only restart (keeps wallets, but any registered neurons are lost):

```sh
docker compose restart subtensor
```
