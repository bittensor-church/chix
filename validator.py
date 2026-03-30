"""Cat Inpainting Subnet Validator.

Measurement: quality of cat inpainting into user-submitted images without altering the original content.

Miner endpoint:
    POST /inpaint
    Request:  {"image_b64": "<base64 PNG>"}
    Response: {"image_b64": "<base64 PNG with cat>"}

Scoring:
    - Background preservation (40%): pixel-exact comparison outside modified region
    - Cat presence (25%): VLM assessment via OpenRouter
    - Inpainting quality (25%): VLM assessment via OpenRouter
    - Speed (10%): response latency, normalized across miners
"""

import base64
import io
import logging
import random
from collections.abc import Generator, Mapping
from datetime import timedelta
from threading import Event as ThreadingEvent
from typing import NewType

import httpx
from nexus.actors import AsyncHttpNeuronCommunicator, EpochBeatNode, RestEntryPoint, RoundRobinNeuronRouter, miners_only
from nexus.actors.payload_creator import NoopPayloadCreator
from nexus.actors.retry_strategy import RetryStrategy
from nexus.actors.weight_setter import WeightsCalculationBundle, WeightSetterNode
from nexus.core.dsl.nodes import Producer
from nexus.core.runtime.actor import Actor, ActorBuilder
from nexus.core.runtime.actor_patterns import ProducerActor
from nexus.core.runtime.context_store import ContextStore
from nexus.core.runtime.events import PipeToBus
from nexus.core.runtime.nexus_task import NexusTask
from nexus.core.runtime.nexus_task_types import NexusTaskName
from nexus.nexus_validator import NexusValidator
from nexus.utils.exceptions import NexusException
from nexus.utils.types import Hotkey, NetUid, Port, Weight
from PIL import Image, ImageChops
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

Score = NewType("Score", float)

# ---------------------------------------------------------------------------
# Scoring weights & constants
# ---------------------------------------------------------------------------

WEIGHT_BACKGROUND = 0.4
WEIGHT_CAT_PRESENCE = 0.25
WEIGHT_INPAINTING_QUALITY = 0.25
WEIGHT_SPEED = 0.1
EMA_ALPHA = 0.1

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class InpaintingRequest(BaseModel):
    """Image payload sent to miners."""

    image_b64: str


class InpaintingResponse(BaseModel):
    """Image payload returned by miners."""

    image_b64: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Validator configuration loaded from environment variables."""

    netuid: int
    callback_port: int = 9100
    callback_base_url: str = "http://localhost:9100"
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash"
    task_interval_seconds: float = 30.0
    max_latency_seconds: float = 120.0
    organic_port: int = 9101


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------


def decode_png_b64(b64_data: str) -> Image.Image:
    """Decode a base64-encoded PNG into an RGB PIL Image."""
    return Image.open(io.BytesIO(base64.b64decode(b64_data))).convert("RGB")


def encode_png_b64(img: Image.Image) -> str:
    """Encode a PIL Image as a base64 PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def generate_synthetic_image() -> Image.Image:
    """Create a randomised gradient image for synthetic testing."""
    base = Image.linear_gradient("L")
    channels = tuple(base.rotate(random.randint(0, 359)) for _ in range(3))
    return Image.merge("RGB", channels).resize((512, 512), Image.Resampling.BILINEAR)  # pyright: ignore[reportUnknownMemberType]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_background_preservation(original_b64: str, result_b64: str) -> Score:
    """Compare pixels to verify the background is unchanged.

    Uses the max per-channel difference per pixel. A pixel is "preserved"
    when its max channel delta is at most 5.
    """
    original = decode_png_b64(original_b64)
    result = decode_png_b64(result_b64)
    if original.size != result.size:
        return Score(0.0)

    diff = ImageChops.difference(original, result)
    r, g, b = diff.split()
    # Per-pixel max channel difference
    max_diff = ImageChops.lighter(ImageChops.lighter(r, g), b)

    threshold = 5
    hist = max_diff.histogram()
    preserved = sum(hist[: threshold + 1])
    total = original.size[0] * original.size[1]
    ratio = preserved / total

    # Cat region should not exceed ~30% of the image
    if ratio < 0.70:
        return Score(0.0)
    return Score(min(1.0, (ratio - 0.70) / 0.30))


def query_vlm_scores(
    original_b64: str,
    result_b64: str,
    api_key: str,
    model: str,
) -> tuple[Score, Score]:
    """Ask a VLM to rate cat presence and inpainting quality (both 0-1)."""
    prompt = (
        "You are evaluating an image editing task. The first image is the original. "
        "The second image should be the same image with a realistic cat added via inpainting. "
        "Rate two aspects on a scale of 0.0 to 1.0:\n"
        "1. CAT_PRESENCE: Is there a clearly visible, realistic cat not in the original? "
        "(0 = no cat, 1 = clearly visible realistic cat)\n"
        "2. INPAINTING_QUALITY: How seamless is the edit? Consider edge blending, lighting, "
        "perspective, shadows. (0 = obvious paste, 1 = perfectly natural)\n\n"
        "Respond ONLY with two lines:\nCAT_PRESENCE: <score>\nINPAINTING_QUALITY: <score>"
    )

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{original_b64}"}},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{result_b64}"}},
                    ],
                }
            ],
            "max_tokens": 100,
            "temperature": 0.0,
        },
        timeout=30.0,
    )
    response.raise_for_status()

    text: str = response.json()["choices"][0]["message"]["content"]
    cat_score = 0.0
    quality_score = 0.0
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("CAT_PRESENCE:"):
            cat_score = _clamp_float(stripped.split(":", 1)[1])
        elif stripped.startswith("INPAINTING_QUALITY:"):
            quality_score = _clamp_float(stripped.split(":", 1)[1])

    return Score(cat_score), Score(quality_score)


def _clamp_float(raw: str) -> float:
    try:
        return max(0.0, min(1.0, float(raw.strip())))
    except ValueError:
        return 0.0


def score_speed(latency_seconds: float, max_latency: float) -> Score:
    """Linear speed score: 1.0 at instant, 0.0 at max_latency."""
    if latency_seconds >= max_latency:
        return Score(0.0)
    return Score(1.0 - latency_seconds / max_latency)


def composite_score(
    background: Score,
    cat_presence: Score,
    quality: Score,
    speed: Score,
) -> Score:
    """Weighted combination of scoring dimensions."""
    return Score(
        background * WEIGHT_BACKGROUND
        + cat_presence * WEIGHT_CAT_PRESENCE
        + quality * WEIGHT_INPAINTING_QUALITY
        + speed * WEIGHT_SPEED
    )


# ---------------------------------------------------------------------------
# Task producer — emits synthetic inpainting requests on a timer
# ---------------------------------------------------------------------------


class TaskProducerNode(Producer[InpaintingRequest], ActorBuilder):
    """Generates synthetic test images on a fixed interval."""

    interval: timedelta

    def __init__(self, _id: str, *, interval: timedelta) -> None:
        super().__init__(_id)
        self.interval = interval

    def build_actor(self, *, pipe_to_bus: PipeToBus, context_store: ContextStore) -> Actor:
        return TaskProducerActor(spec=self, pipe_to_bus=pipe_to_bus, context_store=context_store)


class TaskProducerActor(ProducerActor[InpaintingRequest]):
    """Background thread that yields InpaintingRequest payloads."""

    _stop_event: ThreadingEvent
    _interval: timedelta

    def __init__(self, spec: TaskProducerNode, pipe_to_bus: PipeToBus, context_store: ContextStore) -> None:
        super().__init__(spec=spec, pipe_to_bus=pipe_to_bus, context_store=context_store)
        self._stop_event = ThreadingEvent()
        self._interval = spec.interval

    def on_stop(self) -> None:
        self._stop_event.set()

    def _produce(self) -> Generator[InpaintingRequest]:
        while not self._stop_event.is_set():
            img = generate_synthetic_image()
            logger.info("Emitting synthetic inpainting request")
            yield InpaintingRequest(image_b64=encode_png_b64(img))
            self._stop_event.wait(timeout=self._interval.total_seconds())


# ---------------------------------------------------------------------------
# Weighing function — scores results and computes EMA weights
# ---------------------------------------------------------------------------


def create_weighing_func(task_name: NexusTaskName, settings: Settings) -> ...:  # noqa: DOC501
    """Build a closure that scores epoch results and tracks per-hotkey EMA weights.

    Called once at validator construction; the returned callable is invoked
    by the weight setter at every epoch boundary.
    """
    ema_scores: dict[Hotkey, float] = {}

    def weighing_func(bundle: WeightsCalculationBundle) -> Mapping[Hotkey, Weight]:
        results = bundle.tasks_result_store.get_tasks_for_epoch(task_name=task_name, epoch=bundle.epoch)

        hotkey_scores: dict[Hotkey, list[float]] = {}

        for result in results:
            if result.is_failure:
                continue

            hotkey = Hotkey(result.target.hotkey)
            payload: InpaintingRequest = result.executor_payload
            output_raw = result.executor_output
            if isinstance(output_raw, NexusException):
                continue
            output: InpaintingResponse = output_raw

            bg = score_background_preservation(payload.image_b64, output.image_b64)

            try:
                cat, quality = query_vlm_scores(
                    payload.image_b64,
                    output.image_b64,
                    settings.openrouter_api_key,
                    settings.openrouter_model,
                )
            except Exception:
                logger.warning("VLM scoring failed for hotkey %s", hotkey, exc_info=True)
                cat = Score(0.0)
                quality = Score(0.0)

            latency = (result.processing_finished - result.processing_started).total_seconds()
            spd = score_speed(latency, settings.max_latency_seconds)

            hotkey_scores.setdefault(hotkey, []).append(composite_score(bg, cat, quality, spd))

        # Per-hotkey average, then EMA update
        weights: dict[Hotkey, Weight] = {}
        for hotkey, scores in hotkey_scores.items():
            avg = sum(scores) / len(scores)
            prev = ema_scores.get(hotkey, avg)
            ema = EMA_ALPHA * avg + (1.0 - EMA_ALPHA) * prev
            ema_scores[hotkey] = ema
            weights[hotkey] = Weight(ema)

        # Decay scores for hotkeys absent this epoch
        for hotkey in list(ema_scores):
            if hotkey not in weights:
                decayed = ema_scores[hotkey] * (1.0 - EMA_ALPHA)
                ema_scores[hotkey] = decayed
                if decayed > 0.001:
                    weights[hotkey] = Weight(decayed)

        return weights

    return weighing_func


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

TASK_NAME = NexusTaskName("cat_inpainting")


class CatInpaintingValidator(NexusValidator):
    """Nexus validator for the cat inpainting subnet."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

        task: NexusTask[InpaintingRequest, InpaintingRequest, InpaintingResponse, InpaintingResponse] = NexusTask(
            name=TASK_NAME,
            retry=RetryStrategy[InpaintingRequest]("retry", max_attempts=3, delay=timedelta(seconds=10)),
            payload_creator=NoopPayloadCreator[InpaintingRequest]("payload_creator"),
            router=RoundRobinNeuronRouter[InpaintingRequest](
                "router",
                netuid=settings.netuid,
                neuron_filter=miners_only,
            ),
            executor_communicator=AsyncHttpNeuronCommunicator[InpaintingRequest, InpaintingResponse](
                "communicator",
                target_path="/inpaint",
                send_timeout=timedelta(seconds=30),
                total_processing_timeout=timedelta(seconds=int(settings.max_latency_seconds)),
                callback_port=Port(settings.callback_port),
                callback_path="/callback",
                callback_base_url=settings.callback_base_url,
                input_model=InpaintingRequest,
                output_model=InpaintingResponse,
            ),
            executor_result_converter=NoopPayloadCreator[InpaintingResponse]("result_converter"),
        )

        producer = TaskProducerNode(
            "task_producer",
            interval=timedelta(seconds=settings.task_interval_seconds),
        )

        organic_entry = RestEntryPoint[InpaintingRequest](
            _id="organic",
            path="/inpaint",
            port=settings.organic_port,
            user_data_model=InpaintingRequest,
        )

        epoch_beat = EpochBeatNode("epoch_beat", netuid=NetUid(settings.netuid))

        weight_setter = WeightSetterNode(
            "weight_setter",
            weighing_func=create_weighing_func(TASK_NAME, settings),
        )

        self.connect(producer.source, task.input)
        self.connect(organic_entry.source, task.input)
        self.connect(task.executor_output, organic_entry.sink)
        self.connect(epoch_beat.source, weight_setter.sink)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    CatInpaintingValidator.run(settings_class=Settings)
