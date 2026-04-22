"""Cat-inpainting subnet validator.

What we're measuring: the quality of photo inpainting that adds exactly one
natural-looking cat to a user-supplied image while preserving everything else.
See ``./subnet_design.md`` for the full design, trust analysis, and deferred items.

User API
--------

``POST /inpaint``
    request body : ``{"image_b64": "<base64-encoded JPEG or PNG>"}``
    response body: ``{"image_b64": "<base64-encoded image with a new cat>"}``

This endpoint is the integration contract for a future standalone gateway.
For MVP a test client hits it directly.

Miner interface (Nexus async HTTP)
----------------------------------

The validator POSTs to the miner's advertised axon at path ``/inpaint`` with::

    {
      "request_id": "<uuid>",
      "callback_url": "http://<validator_ip>:<callback_port>/inpaint-callback",
      "input": {"image_b64": "<base64>"}
    }

The miner POSTs to ``callback_url``::

    {"request_id": "<uuid>", "output": {"image_b64": "<base64>"}}
    or on failure:
    {"request_id": "<uuid>", "error": "<message>"}

Scoring
-------

Per-pair VLM judgment, public prompt, public model::

    cat_added    : gate — must be True for the pair to contribute quality
    naturalness  : [0.0, 1.0]
    preservation : [0.0, 1.0]

Per-hotkey rolling aggregates computed at weighing time::

    reliability  = gate_passes / total_attempts
    mean_quality = mean(naturalness_weight * naturalness
                        + preservation_weight * preservation)
    weight       = mean_quality * reliability ** reliability_exponent
"""
# pyright: basic

from __future__ import annotations

import base64
import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Annotated, Any, NewType, cast, override

from dotenv import load_dotenv
from nexus.actors import (
    AsyncHttpNeuronCommunicator,
    EpochBeatNode,
    RestEntryPoint,
    RoundRobinNeuronRouter,
    miners_only,
)
from nexus.actors.executor_communicator.embedded_executor_communicator import EmbeddedExecutorCommunicator
from nexus.actors.neuron_router import NoopRouter
from nexus.actors.payload_creator import NoopPayloadCreator
from nexus.actors.retry_strategy import RetryStrategy
from nexus.actors.task_input_output_creator import (
    BatchedTaskInputOutput,
    TaskInputOutput,
    TaskInputOutputCreator,
)
from nexus.actors.task_result_sampler import EveryTaskResultSampler
from nexus.actors.weight_setter import WeightsCalculationBundle, WeightSetterNode
from nexus.core.dsl.nodes import Node, NodeSinks, NodeSources, Sink, SinkName
from nexus.core.runtime.actor import Actor, ActorBuilder
from nexus.core.runtime.actor_patterns import ConsumerActor
from nexus.core.runtime.context_store import Context, ContextStore
from nexus.core.runtime.events import PipeToBus
from nexus.core.runtime.nexus_task import NexusTask
from nexus.core.runtime.nexus_task_types import NexusTaskName
from nexus.core.runtime.task_result_store import SingleTaskResult
from nexus.nexus_validator import NexusValidator
from nexus.utils import openrouter_client
from nexus.utils.exceptions import NexusException
from nexus.utils.types import BlockCount, Hotkey, NetUid, Port, Weight
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("validator")

DEFAULT_REST_PORT = Port(8081)
DEFAULT_MINER_CALLBACK_PORT = Port(9091)

DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "google/gemini-3-flash-preview"

DEFAULT_VALIDATION_OPENROUTER_TIMEOUT_SECONDS = 120.0
DEFAULT_VALIDATION_OPENROUTER_TEMPERATURE = 0.0

# Public, deterministic scoring prompt. Ships in the repo; anyone can re-score
# from logged (input, output) pairs. Knowing the criteria does not help a miner
# cheat — the criteria *are* the task.
DEFAULT_VALIDATION_PROMPT = (
    "You are judging how well an image was modified.\n"
    "For each pair, the FIRST image is the ORIGINAL and the SECOND is the MODIFIED version.\n"
    "The task performed on the original was: add exactly one new cat to the scene, "
    "in a natural, photographic way, while leaving the rest of the image unchanged.\n"
    "\n"
    "Score each pair on three axes:\n"
    "- cat_added (boolean): true only if the modified image contains at least one MORE "
    "cat than the original. Preexisting cats must still be present; a new cat must have "
    "been added. If the count did not strictly increase, set cat_added=false.\n"
    "- naturalness (float in [0.0, 1.0]): how naturally the added cat blends in. "
    "1.0 means it looks like a real cat photographed in that scene; 0.0 means it "
    "looks obviously composited, pasted, cartoonish, or poorly inpainted.\n"
    "- preservation (float in [0.0, 1.0]): how unchanged the rest of the image is. "
    "1.0 means outside the added cat the image is effectively identical to the original; "
    "0.0 means substantial global changes (re-rendered, colors shifted, other objects "
    "added/removed, resolution changes).\n"
    "\n"
    "Return ONLY valid JSON matching this schema: "
    '{"scores_by_task_result_id": {"<task_result_id>": '
    '{"cat_added": boolean, "naturalness": number, "preservation": number}}}. '
    "No markdown, no code fences, no commentary, no extra keys."
)


class ValidatorSettings(BaseSettings):
    """Validator configuration. Loaded from ``.env`` and process environment.

    Environment variable names are the field name prefixed with ``VALIDATOR_``
    and upper-cased (e.g. ``openrouter_api_key`` → ``VALIDATOR_OPENROUTER_API_KEY``).
    """

    model_config = SettingsConfigDict(env_prefix="VALIDATOR_", env_file=".env", extra="ignore")

    # --- chain / pylon ---
    netuid: NetUid
    external_ip: str  # advertised to miners as callback host

    # --- user-facing ingress ---
    rest_entry_point_port: Port = DEFAULT_REST_PORT

    # --- miner communication ---
    miner_callback_port: Port = DEFAULT_MINER_CALLBACK_PORT
    miner_target_path: str = "/inpaint"
    miner_callback_path: str = "/inpaint-callback"
    miner_send_timeout_seconds: float = 10.0
    miner_total_timeout_seconds: float = 120.0
    miner_max_in_flight: int = 16

    # --- OpenRouter VLM judge ---
    openrouter_api_key: str
    openrouter_url: str = DEFAULT_OPENROUTER_URL
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    validation_openrouter_temperature: float = DEFAULT_VALIDATION_OPENROUTER_TEMPERATURE
    validation_openrouter_timeout_seconds: float = DEFAULT_VALIDATION_OPENROUTER_TIMEOUT_SECONDS
    validation_prompt: str = DEFAULT_VALIDATION_PROMPT

    # --- scoring (all tunable starting points; see subnet_design.md) ---
    naturalness_weight: float = 0.5
    preservation_weight: float = 0.5
    reliability_exponent: float = 2.5

    # --- epoch / weight setting ---
    epoch_beat_delay_blocks: BlockCount = BlockCount(20)


# ---------------------------------------------------------------------------
# Subnet models
# ---------------------------------------------------------------------------

ImageB64 = NewType("ImageB64", str)


class CatImage(BaseModel):
    """Base64-encoded photo (JPEG or PNG). Used for every image payload in the
    pipeline: user input, miner input, miner output, user output."""

    image_b64: ImageB64


class ValidationScore(BaseModel):
    """Per-pair VLM judgment."""

    cat_added: bool
    naturalness: Annotated[float, Field(ge=0.0, le=1.0)]
    preservation: Annotated[float, Field(ge=0.0, le=1.0)]


class _ScoresByTaskResultId(BaseModel):
    """VLM response envelope."""

    scores_by_task_result_id: dict[str, ValidationScore]


# Type aliases for the Nexus task parametrization. The user, miner input, and
# miner output all carry the same shape (a base64 image); labeling each role
# keeps the NexusTask signatures readable at the wiring call sites.
MiningInput = CatImage
MiningExecutorPayload = CatImage
MiningExecutorOutput = CatImage

# Validation task consumes batches of stored mining task results and emits
# per-pair VLM scores in the same batch shape.
StoredMiningResult = SingleTaskResult[CatImage, CatImage, CatImage]
ValidationInput = tuple[StoredMiningResult, ...]
ValidationExecutorPayload = BatchedTaskInputOutput[CatImage, CatImage, CatImage]
ValidationExecutorOutput = BatchedTaskInputOutput[CatImage, ValidationScore, ValidationScore]


# ---------------------------------------------------------------------------
# VLM judge
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _data_uri_from_b64(image_b64: ImageB64) -> str:
    """Wrap a base64 image as a ``data:`` URI with a best-guess MIME type.

    Used only for the VLM judge call; the bytes themselves are never re-encoded.
    Falls back to ``image/png`` when the first few bytes are unrecognized — most
    VLMs tolerate a mislabeled MIME type.
    """
    try:
        head = base64.b64decode(image_b64[:16], validate=False)
    except ValueError:
        # binascii.Error is a subclass of ValueError
        head = b""
    if head.startswith(_PNG_MAGIC):
        mime = "image/png"
    elif head.startswith(_JPEG_MAGIC):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    return f"data:{mime};base64,{image_b64}"


def _build_vlm_messages(
    *,
    pairs: tuple[TaskInputOutput[CatImage, CatImage, CatImage], ...],
    prompt: str,
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (f"{prompt}\n\nThe task_result_ids to score are: {[str(p.task_result_id) for p in pairs]}"),
        },
    ]
    for pair in pairs:
        content.extend(
            (
                {"type": "text", "text": f"task_result_id={pair.task_result_id} original_image"},
                {"type": "image_url", "image_url": {"url": _data_uri_from_b64(pair.task_input.image_b64)}},
                {"type": "text", "text": f"task_result_id={pair.task_result_id} modified_image"},
                {"type": "image_url", "image_url": {"url": _data_uri_from_b64(pair.task_public_output.image_b64)}},
            )
        )
    return [{"role": "user", "content": content}]


def validate(
    batch: ValidationExecutorPayload,
    *,
    settings: ValidatorSettings,
) -> ValidationExecutorOutput:
    """Ask the VLM judge to score a batch of (original, modified) image pairs.

    Raises:
        KeyError: If the VLM response omits a score for a pair. Treated as an
            executor failure by the embedded communicator; the mining task
            result stays in the store as an "unscored success" and earns no
            quality contribution at weighing time.
    """
    pairs = batch.task_input_outputs
    if len(pairs) == 0:
        return BatchedTaskInputOutput(task_input_outputs=())

    log.info("Asking VLM judge to score %d image pair(s)", len(pairs))
    scored = openrouter_client.query(
        messages=_build_vlm_messages(pairs=pairs, prompt=settings.validation_prompt),
        settings=settings,
        response_model=_ScoresByTaskResultId,
    )
    scores = scored.scores_by_task_result_id

    log.info(
        "Judge scores:\n%s",
        "\n".join(
            f"task_result_id={p.task_result_id} "
            f"cat_added={scores[str(p.task_result_id)].cat_added} "
            f"naturalness={scores[str(p.task_result_id)].naturalness:.2f} "
            f"preservation={scores[str(p.task_result_id)].preservation:.2f}"
            for p in pairs
        ),
    )

    return BatchedTaskInputOutput(
        task_input_outputs=tuple(
            TaskInputOutput(
                task_result_id=p.task_result_id,
                task_input=p.task_input,
                task_output=scores[str(p.task_result_id)],
                task_public_output=scores[str(p.task_result_id)],
            )
            for p in pairs
        )
    )


# ---------------------------------------------------------------------------
# Weighing
# ---------------------------------------------------------------------------


@dataclass
class _HotkeyAccumulator:
    attempts: int = 0
    gate_passes: int = 0
    quality_sum: float = 0.0
    unscored_successes: int = 0


def weighing_func(
    mining_task_name: NexusTaskName,
    validation_task_name: NexusTaskName,
    settings: ValidatorSettings,
    bundle: WeightsCalculationBundle,
) -> Mapping[Hotkey, Weight]:
    """Aggregate stored task results into per-hotkey weights.

    Mining tasks from the previous epoch are matched to validation scores
    (which can trail by a few blocks, so we scan both the previous and current
    epoch). Unscored successes count as attempts but contribute no quality.
    """
    current_epoch = bundle.epoch
    try:
        previous_epoch = current_epoch.previous()
    except ValueError:
        log.info("No previous epoch yet (epoch=%s) — emitting empty weights", current_epoch)
        return {}

    store = bundle.tasks_result_store
    mining_results = store.get_tasks_for_epoch(mining_task_name, previous_epoch)
    validation_results = store.get_tasks_for_epoch(validation_task_name, previous_epoch) + store.get_tasks_for_epoch(
        validation_task_name, current_epoch
    )

    log.info(
        "Weighing epoch=%s: mining_results=%d validation_results=%d",
        current_epoch,
        len(mining_results),
        len(validation_results),
    )

    scores_by_mining_id: dict[str, ValidationScore] = {}
    for validation_result in validation_results:
        if validation_result.is_failure:
            continue
        validation_output = cast(ValidationExecutorOutput, validation_result.executor_output)
        for item in validation_output.task_input_outputs:
            scores_by_mining_id[str(item.task_result_id)] = item.task_output

    accumulators: dict[Hotkey, _HotkeyAccumulator] = defaultdict(_HotkeyAccumulator)
    for mining_result in mining_results:
        hotkey = Hotkey(mining_result.target.hotkey)
        stats = accumulators[hotkey]
        stats.attempts += 1

        if mining_result.is_failure:
            continue

        score = scores_by_mining_id.get(str(mining_result.id))
        if score is None:
            stats.unscored_successes += 1
            continue

        if not score.cat_added:
            continue

        stats.gate_passes += 1
        stats.quality_sum += (
            settings.naturalness_weight * score.naturalness + settings.preservation_weight * score.preservation
        )

    weights: dict[Hotkey, Weight] = {}
    for hotkey in sorted(accumulators.keys(), key=str):
        stats = accumulators[hotkey]
        if stats.attempts == 0:
            continue
        reliability = stats.gate_passes / stats.attempts
        mean_quality = (stats.quality_sum / stats.gate_passes) if stats.gate_passes > 0 else 0.0
        final = mean_quality * (reliability**settings.reliability_exponent)
        weights[hotkey] = Weight(final)
        log.info(
            "hotkey=%s attempts=%d gate_passes=%d unscored=%d mean_quality=%.3f reliability=%.3f weight=%.4f",
            hotkey,
            stats.attempts,
            stats.gate_passes,
            stats.unscored_successes,
            mean_quality,
            reliability,
            final,
        )

    if len(weights) == 0:
        log.info("Computed weights: <empty> (no mining traffic in scored epoch)")
    return weights


# ---------------------------------------------------------------------------
# Error logging sink
# ---------------------------------------------------------------------------


class ErrorLoggerNode(Node, ActorBuilder):
    """Sink node that logs any incoming ``NexusException`` at ERROR level.

    Every error-emitting actor source in the subnet graph can be wired here
    to keep error signals visible even when there is no user-facing path for
    them (validation failures, weight-setting failures, etc.).
    """

    sink: Sink[NexusException]

    def __init__(self, _id: str) -> None:
        super().__init__(_id)
        self.sink = Sink[NexusException](f"{self.id}-sink", owner_node=self)

    @override
    def sinks(self) -> NodeSinks:
        return NodeSinks(sinks={SinkName("errors"): self.sink})

    @override
    def sources(self) -> NodeSources:
        return NodeSources(sources={})

    @override
    def build_actor(self, *, pipe_to_bus: PipeToBus, context_store: ContextStore) -> Actor:
        return ErrorLoggerActor(spec=self, pipe_to_bus=pipe_to_bus, context_store=context_store)


class ErrorLoggerActor(ConsumerActor[NexusException]):
    _log: logging.Logger

    def __init__(
        self,
        *,
        spec: ErrorLoggerNode,
        pipe_to_bus: PipeToBus,
        context_store: ContextStore,
    ) -> None:
        super().__init__(spec=spec.sink, pipe_to_bus=pipe_to_bus, context_store=context_store)
        self._log = logging.getLogger(f"validator.errors.{spec.id}")

    @override
    def _consume(self, ctx: Context, payload: NexusException) -> None:
        self._log.error("error on ctx=%s: %s", ctx.id, payload, exc_info=payload)


# ---------------------------------------------------------------------------
# Validator wiring
# ---------------------------------------------------------------------------

MINING_TASK_NAME = NexusTaskName("inpaint-cat")
VALIDATION_TASK_NAME = NexusTaskName("judge-inpainting")


class Validator(NexusValidator):
    """Cat-inpainting validator graph.

    Three concerns wired in one graph:

    1. **User ingress.** ``RestEntryPoint`` receives user images, the mining
       task forwards to one miner (uniform-random via ``RoundRobinNeuronRouter``
       with per-context shuffle), the miner response is returned to the user
       as-is (no pre-return validation).
    2. **Scoring.** Every successful mining result is sampled, wrapped as a
       batch, and judged by a VLM via an ``EmbeddedExecutorCommunicator``.
    3. **Weight setting.** Epoch beats trigger ``WeightSetterNode`` which
       aggregates the task result store via ``weighing_func``.

    Error sources from mining, validation, and weight setting are wired to a
    logging sink so failures are visible even when there is no user-facing
    path (validation, weight setting).
    """

    settings: ValidatorSettings

    def __init__(self, settings: ValidatorSettings) -> None:
        super().__init__(settings)
        self.settings = settings

        self.entry = RestEntryPoint[CatImage](
            _id="cat-inpainting-user-requests",
            path="/inpaint",
            port=settings.rest_entry_point_port,
            user_data_model=CatImage,
        )

        self.mining_task = NexusTask[
            MiningInput,
            MiningExecutorPayload,
            MiningExecutorOutput,
            MiningExecutorOutput,
        ](
            name=MINING_TASK_NAME,
            # max_attempts=1 matches the design's "1 request → 1 miner" rule.
            retry=RetryStrategy[MiningInput](
                "mining-retry",
                max_attempts=1,
                delay=timedelta(seconds=1.0),
            ),
            payload_creator=NoopPayloadCreator[MiningInput]("mining-payload-passthrough"),
            router=RoundRobinNeuronRouter[MiningExecutorPayload](
                "mining-router",
                netuid=settings.netuid,
                neuron_filter=miners_only,
            ),
            executor_communicator=AsyncHttpNeuronCommunicator[CatImage, CatImage](
                "mining-miner-communicator",
                target_path=settings.miner_target_path,
                callback_port=settings.miner_callback_port,
                callback_path=settings.miner_callback_path,
                callback_base_url=f"http://{settings.external_ip}:{int(settings.miner_callback_port)}",
                send_timeout=timedelta(seconds=settings.miner_send_timeout_seconds),
                total_processing_timeout=timedelta(seconds=settings.miner_total_timeout_seconds),
                max_in_flight=settings.miner_max_in_flight,
                input_model=CatImage,
                output_model=CatImage,
            ),
            executor_result_converter=NoopPayloadCreator[MiningExecutorOutput](
                "mining-result-passthrough",
            ),
        )

        # Single result per context; validation happens one pair at a time.
        # Batching multiple pairs per VLM call is a straightforward optimization
        # once we have sustained traffic — swap this sampler for a windowed one.
        self.mining_result_sampler = EveryTaskResultSampler[CatImage, CatImage, CatImage](
            "mining-result-sampler",
        )

        self.validation_task = NexusTask[
            ValidationInput,
            ValidationExecutorPayload,
            ValidationExecutorOutput,
            ValidationExecutorOutput,
        ](
            name=VALIDATION_TASK_NAME,
            # VLM judgment is a single-shot: retrying the same call for the same
            # inputs doesn't add signal. A VLM failure leaves the mining result
            # as an "unscored success" in the store.
            retry=RetryStrategy[ValidationInput](
                "validation-retry",
                max_attempts=1,
                delay=timedelta(seconds=1.0),
            ),
            payload_creator=TaskInputOutputCreator[CatImage, CatImage, CatImage](
                "validation-payload-builder",
            ),
            router=NoopRouter[ValidationExecutorPayload]("validation-router"),
            executor_communicator=EmbeddedExecutorCommunicator[
                ValidationExecutorPayload,
                ValidationExecutorOutput,
            ](
                "validation-embedded",
                input_model=BatchedTaskInputOutput[CatImage, CatImage, CatImage],
                output_model=BatchedTaskInputOutput[CatImage, ValidationScore, ValidationScore],
                executor_func=partial(validate, settings=settings),
            ),
            executor_result_converter=NoopPayloadCreator[ValidationExecutorOutput](
                "validation-result-passthrough",
            ),
        )

        self.epoch_beat = EpochBeatNode(
            "epoch-beat",
            netuid=settings.netuid,
            delay=settings.epoch_beat_delay_blocks,
        )

        self.weight_setter = WeightSetterNode(
            "weight-setter",
            weighing_func=partial(
                weighing_func,
                MINING_TASK_NAME,
                VALIDATION_TASK_NAME,
                settings,
            ),
        )

        self.error_logger = ErrorLoggerNode("error-logger")

        # --- user traffic ---
        self.connect(self.entry.source, self.mining_task.input)
        self.connect(self.mining_task.executor_output, self.entry.sink)
        self.connect(self.mining_task.error, self.entry.sink)

        # --- scoring ---
        self.connect(self.mining_task.task_result, self.mining_result_sampler.task_results)
        self.connect(self.mining_result_sampler.sampled_batch, self.validation_task.input)

        # --- weight setting ---
        self.connect(self.epoch_beat.source, self.weight_setter.sink)

        # --- error surfacing ---
        # Mining errors already go to the user via entry.sink; also log them so
        # failures are visible in stdout even when no one is reading the 500.
        # Validation and weight-setting errors have no user-facing path.
        self.connect(self.mining_task.error, self.error_logger.sink)
        self.connect(self.validation_task.error, self.error_logger.sink)
        self.connect(self.weight_setter.error, self.error_logger.sink)


def main() -> None:
    # Pylon-side Nexus actors read configuration directly from the process
    # environment, so .env must be loaded before NexusValidator.run() wires
    # up the runtime.
    load_dotenv()
    Validator.run(settings_class=ValidatorSettings)


if __name__ == "__main__":
    main()
