# Cat Inpainting Subnet

Bittensor subnet where users submit images and miners inpaint realistic cats into them.
The original image must be pixel-identical outside the inpainted region.

Built from the [ChiX template](https://github.com/...) for Bittensor subnet development.

## Measurement axis

Quality of cat inpainting into user-submitted images without altering the original content.

## Pattern

Compute auction with quality scoring (same family as 404-GEN SN17).

## Mechanism

```
User ──image──► Validator ──image──► Miner (runs inpainting model)
                                         │
                    ◄──image+cat──────────┘
                    │
                    ├─ Pixel diff: background unchanged?  (deterministic)
                    ├─ VLM via OpenRouter: cat present + quality?  (API call)
                    ├─ Latency
                    │
                    └─► EMA-smoothed score → weights
```

Miners choose where to place the cat. Validators discover the modified region via pixel diff.

## Miner interface

- Endpoint: `POST /inpaint`
- Input: PNG image (lossless, no compression artifacts)
- Output: PNG image with a single realistic cat inpainted
- Auth: Epistula signed headers
- Discovery: endpoint URL committed to chain

Miners host their own GPU infrastructure running inpainting models (Stable Diffusion
inpainting, FLUX inpainting, or similar open-source models).

## Scoring

All criteria are public and transparent. Knowing the rubric does not help miners game it —
you still need to run a good inpainting model.

| Dimension              | Weight | Method                                                        |
|------------------------|--------|---------------------------------------------------------------|
| Background preservation| 40%    | Pixel-exact comparison outside modified region (deterministic) |
| Cat presence           | 25%    | VLM assessment via OpenRouter                                 |
| Inpainting quality     | 25%    | VLM assessment via OpenRouter                                 |
| Speed                  | 10%    | Response latency, normalized across miners                    |

### Background preservation (40%)

Validator computes pixel diff between original and result. Thresholds to find the modified
region. All pixels outside that region must be identical to the original. PNG format is
mandatory to avoid lossy compression artifacts polluting this check.

Score: ratio of exactly-preserved pixels (expected to be very high — small cat region
relative to full image).

### Cat presence (25%)

VLM call: "Does this image contain a realistic cat that was not present in the original
image? Respond with a confidence score 0-1."

Compared with the original to confirm the cat is new, not a pre-existing element.

### Inpainting quality (25%)

VLM call: "Rate the seamlessness of the image edit on a scale of 0-1. Consider: edge
naturalness, lighting consistency, perspective correctness, shadow coherence, and whether
the cat looks like it belongs in the scene."

### Speed (10%)

Latency from request to response. Normalized: `1.0 - (latency / max_latency)`.

### Aggregation

- Per-dimension scores combined with weights above into composite score.
- EMA smoothing (alpha ~0.1) for stable reputation over time.
- Weight conversion: softmax over composite scores.

## Image sources

- **Organic traffic:** Real user submissions via public API (the product).
- **Synthetic probes:** Validator periodically sends stock/AI-generated photos for testing.
  Diverse scenes, lighting, scales. Prevents overfitting to narrow image types.

## Attack analysis

| Attack                         | Defense                                                                 |
|--------------------------------|-------------------------------------------------------------------------|
| Return image unchanged         | Cat presence score = 0                                                  |
| Paste a crude cat sticker      | Inpainting quality score tanks (edge artifacts, lighting mismatch)      |
| Alter the background           | Pixel diff catches any changed pixel outside cat region (deterministic) |
| Copy another miner's output    | Stochastic generation differs; EMA rewards consistency                  |
| Validator leaks test images    | No secrets to leak — public criteria, still need good model to score    |

## Integrations

### OpenRouter (initial VLM provider)

Used by validators for cat presence and inpainting quality scoring.

- API: `https://openrouter.ai/api/v1/chat/completions`
- Auth: API key (`OPENROUTER_API_KEY`)
- Model: vision-capable model (e.g. `google/gemini-2.5-flash`)
- Usage: two structured prompts per evaluation (cat presence + quality)
- Cost: paid per token, borne by validators
- Multimodal: send both original and result images as base64 in the message

### Chutes (future VLM provider)

Decentralized alternative to OpenRouter, native to Bittensor ecosystem.

- API: `https://llm.chutes.ai/v1`
- Auth: Epistula headers (validator hotkey signature) for free access
- Validator free access: hotkey-based, no API key cost
- Templates: diffusion (image models), vllm (vision-language models)
- Migration path: swap OpenRouter client for Chutes client, same prompt format

### Hippius (SN75 — decentralized storage)

For storing evaluation datasets, user-submitted images, and result provenance.

- Store submitted images with blockchain-anchored timestamps
- Prove temporal ordering of submissions (prevents backdating)
- Miner artifact storage (committed bucket URLs to chain)
- S3-compatible API: `s3.hippius.com`
- Provenance: timestamp data to prove when images were stored

### Epistula protocol

Authentication for all miner-validator communication.

- Headers: `X-Epistula-Timestamp`, `X-Epistula-Signature`, `X-Epistula-Hotkey`
- Message format: `{nonce}.{sha256(body)}`
- Signature: `wallet.hotkey.sign(message)`
- Validators verify miner identity; miners verify validator identity

### Pylon (subtensor communication)

For chain operations: registration, commitments, metagraph queries.

- Miner endpoint commitment: `set_commitment(wallet, netuid, endpoint_url)`
- Validator reads endpoints: `get_all_commitments(netuid)`
- Rate limit: 1 commitment per 100 blocks (~20 minutes)
- Miners commit endpoint URL once, not per-request data

## Design invariants

- Validator-only development: only `validator.py`, never miner code
- No secret eval sets — all scoring criteria are public
- No similarity detection reliance
- Compute on miners (GPU inpainting), validators are cheap (pixel math + API call)
- PNG format mandatory (lossless, enables exact pixel comparison)
- Miner chooses cat placement (creative freedom, natural results)
- Open source preference for inpainting models
