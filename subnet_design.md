# Subnet Design: Cat Inpainting

## What we're measuring

Quality of photo inpainting that adds exactly one natural-looking cat to a
user-supplied image while preserving everything else.

## Mechanism pattern

**Compute auction with multi-dimensional quality scoring** (the 404-GEN / SN17
shape). Miners host GPU inference for an inpainting model; validators route
user requests to miners and judge outputs with a VLM.

Not `adversarial_red_blue`: there is only one side of the task (generation);
detection is not part of the commodity. Not `capacity_market`: we care about
per-request output quality, not raw uptime or billed compute.

## Roles

### Miner

Public HTTP service. Endpoint committed to chain via standard Bittensor
commitment mechanism.

- `POST /inpaint` — request body: raw image bytes. Response body: raw image
  bytes of the inpainted result. No prompt, no mask, no auxiliary inputs.
- `GET /health` — readiness probe.

Miners are free to use any inpainting approach (open-source diffusion model,
proprietary pipeline, hosted API wrapper). Open-source is encouraged per
subnet invariants but the output is directly testable, so anonymous endpoints
are permitted.

### Validator

Single `validator.py`, built on Nexus. Runs one loop that does two jobs:

1. **Serves user traffic.** Exposes `POST /inpaint` as the integration
   contract for a future standalone gateway service. For MVP this endpoint is
   used directly by test clients; a dedicated frontend gateway is a later
   integration and is out of scope.
2. **Scores miners.** Every served request produces a `(input, output,
   miner_uid, success)` record that feeds asynchronous VLM-based scoring.

## End-to-end flow (MVP)

1. Client `POST`s an image to validator's `/inpaint`.
2. Validator selects one miner **uniformly at random** over registered UIDs
   and forwards the image. Routing is intentionally dumb; smarter routing is
   deferred (see "Deferred").
3. Validator returns the miner's response to the client as-is. **No
   pre-return validation.** If the miner returns broken or untransformed
   bytes, the client sees it; reliability scoring is the correction
   mechanism.
4. Validator records the request/response pair for async scoring.
5. Scoring loop: for each logged pair, VLM judge produces per-dimension
   scores. Per-miner rolling aggregates feed weight setting.

## Scoring

VLM judge: **OpenRouter `google/gemini-3-flash-preview`** with a fixed,
public prompt that returns structured JSON. Model and prompt are committed
to the repository so anyone can re-score from logs.

### Per-sample dimensions

1. **`cat_added`** — gate. VLM counts cats in the input and in the output;
   the gate passes iff `output_count > input_count`. Any preexisting cats
   must survive (count strictly increases, it does not reset).
2. **`naturalness`** — graded in `[0, 1]`. "Does the new cat look like a
   photograph, or does it look composited, pasted, or inpainted?"
3. **`preservation`** — graded in `[0, 1]`. "Aside from the added cat, is the
   rest of the image unchanged? Penalize global color shifts, re-rendering,
   resolution changes, added/removed objects."

Latency is **not** scored. We cannot know a priori what "good latency" is for
an arbitrary user-submitted image, and penalizing slow responses
discriminates against harder jobs.

### Per-miner rolling aggregates

- `reliability` — fraction of requests the miner served with a valid image
  that passed the `cat_added` gate, over a rolling window.
- Mean `naturalness` and mean `preservation` over the window, computed only
  over requests that passed the gate.

### Composite score and weights

Starting-point formula (all coefficients tunable):

```
quality   = cat_added_gate * (0.5 * naturalness + 0.5 * preservation)
final     = quality * reliability ** 2.5
weights   = softmax(final / temperature)
```

The `reliability ** 2.5` exponent follows the credibility pattern from
`incentive.primitives.yaml` — exponential penalty for miners that frequently
fail to produce valid outputs. No validator-side EMA over scores or weights
(per `validator.rules.yaml`); if signal is noisy, aggregate more samples per
epoch instead.

## Trust analysis

Running the gauntlet from `validator.rules.yaml` and `trust.assumptions.yaml`:

- **Validator controls ground truth?** No. Judge model, prompt, and parsing
  are public and deterministic. Anyone can re-run scoring on logged pairs.
  Knowing the criteria does not help a miner cheat because the criteria
  *are* the task.
- **Secret eval sets?** None. All traffic is organic user traffic; no
  validator-curated hidden test set exists.
- **Similarity-detection reliance?** None. Passthrough attacks (miner returns
  the input unmodified) are caught by the `cat_added` gate, not by
  similarity.
- **Heavy compute on validator?** No. Inpainting runs on miner GPUs. The
  validator makes one VLM API call per scored pair — light by comparison,
  and can be rehomed to Chutes later.
- **Sybil — N miners give N× reward?** No. Reward is quality-weighted per
  request. A single operator running N identical miners splits the same
  quality-weighted share of traffic; UID slot pressure plus registration
  cost provides the actual sybil deterrent (`sybil.realities.yaml`).
- **Copy attacks across miners?** Validator does not echo one miner's output
  to another, so there is no direct cross-miner copy channel. Network-level
  scraping of another miner's endpoint is possible but does not improve a
  copier's score relative to the original.

## Known MVP limitations

All flagged explicitly, accepted as tradeoffs for shipping quickly:

- **VLM judge is weak on `preservation`.** Subtle re-rendering, small color
  shifts, or low-level artifacts outside the cat region will not be reliably
  caught. The correct long-term fix is CV pipelines (SSIM / LPIPS on the
  unchanged region; a cat detector to localize the change; pixel-space diff
  masking). The scoring design leaves a clean seam — add or replace
  dimensions without changing the miner contract.
- **VLM judge is a single point of compromise.** Partially mitigated by
  publishing the judge model and prompt and making scoring reproducible from
  logs. A future version can ensemble 2–3 judges.
- **No signal without traffic.** Scoring depends entirely on organic user
  requests. If no one uses the frontend, no one gets scored. Synthetic
  challenges are the planned remedy (see "Deferred").
- **No pre-return validation.** A bad miner can return garbage to a real
  user. This is deliberate for MVP — pre-return quality gating adds latency
  and validator-controlled judgment to the hot path. Reliability scoring
  plus future smarter routing is the correction mechanism.
- **Uniform-random routing wastes user traffic on bad miners.** Acceptable
  for MVP; deferred routing work addresses it.

## Deferred (explicitly not in MVP)

- **Standalone gateway service.** Validator's `/inpaint` endpoint defines
  the integration contract. A dedicated frontend + gateway service plugs in
  later without changing the miner contract.
- **Smarter routing.** "Better scores → more work." Routing and scoring
  converge on the same miners: incentive-weighted selection, possibly with
  exploration budget for new UIDs.
- **Miner fanout.** Send one request to K miners, pick the best response
  (possibly via lightweight diff or VLM pre-check) before returning. Better
  UX, higher validator cost.
- **Synthetic challenges.** Validator-driven image stream from a public
  photo dataset to keep scoring signal alive when organic traffic is low.
  Same miner API, same scoring pipeline.
- **CV-based preservation scoring.** SSIM / LPIPS on regions outside the
  inpainted bounding box, cat-localization via a small detection model,
  pixel-level diff analysis.
- **Chutes-hosted VLM judge.** Swap OpenRouter Gemini for a Chutes-hosted
  alternative once costs or latency justify it.
- **VLM ensemble.** Multiple judge models with majority or averaged scoring
  to reduce single-model bias.

## Validator interface summary

```
POST /inpaint
  request:  image bytes (jpeg or png)
  response: image bytes (same format preferred)
  errors:   502 if selected miner fails; 503 if no miners registered
```

## Miner interface summary (spec for miners to implement)

```
POST /inpaint
  request:  image bytes (jpeg or png)
  response: image bytes containing the original image with one additional
            natural-looking cat; all non-cat regions should be unchanged
GET /health
  response: 200 when ready to serve
```
