# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bittensor",
#     "bittensor-wallet",
#     "litestar[standard]",
#     "httpx",
#     "click",
#     "python-dotenv",
# ]
# ///
"""Honest cat-inpainting miner fixture.

Receives a task from the validator (a base64-encoded photo), calls OpenRouter's
Seedream 4.5 to add a natural-looking cat, and POSTs the result back to the
validator's callback URL.

Self-funds from Alice and self-registers on the local subnet on first run.

Env (loaded from .env if present):
    MINER_OPENROUTER_API_KEY    — preferred; falls back to VALIDATOR_OPENROUTER_API_KEY
    MINER_OPENROUTER_MODEL      — defaults to ``bytedance-seed/seedream-4.5``

Usage: uv run localnet/miners/miner-honest.py [-n NUM_INSTANCES]
"""

from __future__ import annotations

import asyncio
import base64
import multiprocessing
import os
import random
import socket
import sys
import time
from pathlib import Path
from typing import Any

import bittensor as bt
import click
import httpx
import uvicorn
from bittensor.utils.balance import Balance
from bittensor_wallet import Keypair, Wallet
from dotenv import load_dotenv
from litestar import Litestar, post
from pydantic import BaseModel

load_dotenv()

MINER_NAME = "honest"
PORT_RANGE = (10000, 65000)
# Must match ``VALIDATOR_MINER_TARGET_PATH`` on the validator side.
TARGET_PATH = "/inpaint"

WALLETS_DIR = Path(__file__).parent.parent / "wallets"
SUBTENSOR_NETWORK = "ws://127.0.0.1:9944"
NETUID = 2
FUND_AMOUNT_TAO = 1000.0

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("MINER_OPENROUTER_MODEL", "bytedance-seed/seedream-4.5")
OPENROUTER_PROMPT = (
    "Add exactly one natural-looking cat to this photo. Place it somewhere plausible "
    "for the scene and match the existing lighting. Do not change anything else in the image."
)
OPENROUTER_TIMEOUT_SECONDS = 240.0

# Populated once per process at startup.
OPENROUTER_API_KEY: str | None = None


# ---------------------------------------------------------------------------
# Nexus async HTTP protocol envelopes (match nexus.actors.executor_communicator
# async_http_protocol.AsyncHttpNeuronRequestEnvelope / ResponseEnvelope).
# ---------------------------------------------------------------------------


class RequestEnvelope(BaseModel):
    request_id: str
    callback_url: str
    input: dict[str, Any]


class ResponseEnvelope(BaseModel):
    request_id: str
    output: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# OpenRouter-backed inpainting
# ---------------------------------------------------------------------------


def _data_uri(image_b64: str) -> str:
    try:
        head = base64.b64decode(image_b64[:16], validate=False)
    except ValueError:
        head = b""
    if head.startswith(b"\x89PNG"):
        return f"data:image/png;base64,{image_b64}"
    return f"data:image/jpeg;base64,{image_b64}"


def _b64_from_data_uri(data_uri: str) -> str:
    _, _, payload = data_uri.partition(",")
    return payload


async def inpaint_cat(*, image_b64: str, api_key: str) -> str:
    """Ask OpenRouter to add a cat. Returns the modified image as a base64 string
    (without the ``data:`` URI prefix).

    Raises:
        httpx.HTTPStatusError: On non-2xx from OpenRouter.
        RuntimeError: If the response does not contain an image.
    """
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": OPENROUTER_PROMPT},
                    {"type": "image_url", "image_url": {"url": _data_uri(image_b64)}},
                ],
            }
        ],
        "modalities": ["image"],
    }
    async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT_SECONDS) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    message = data["choices"][0]["message"]
    images = message.get("images") or []
    if len(images) == 0:
        raise RuntimeError(
            f"OpenRouter response contained no images; message keys={list(message.keys())}, "
            f"content={str(message.get('content'))[:200]!r}"
        )
    return _b64_from_data_uri(images[0]["image_url"]["url"])


# ---------------------------------------------------------------------------
# HTTP endpoint: receive task, ack, process + callback asynchronously
# ---------------------------------------------------------------------------


@post(TARGET_PATH)
async def handle_task(data: RequestEnvelope) -> None:
    """Ack the validator immediately and schedule the real work as a background task.

    The validator's send-timeout is short (10s by default). Doing inpainting
    inline would time out the outbound POST before we even start the callback.
    """
    print(f"[{MINER_NAME}] received request {data.request_id}")
    _ = asyncio.create_task(_process_and_callback(data))


async def _process_and_callback(data: RequestEnvelope) -> None:
    if OPENROUTER_API_KEY is None:
        # Can't recover — caller will retry or we'll be scored as unreliable.
        print(f"[{MINER_NAME}] no OpenRouter API key configured; dropping {data.request_id}")
        return

    try:
        image_b64 = data.input["image_b64"]
        output_b64 = await inpaint_cat(image_b64=image_b64, api_key=OPENROUTER_API_KEY)
        envelope = ResponseEnvelope(request_id=data.request_id, output={"image_b64": output_b64})
        print(f"[{MINER_NAME}] completed {data.request_id} (output b64 len={len(output_b64)})")
    except Exception as exc:
        envelope = ResponseEnvelope(request_id=data.request_id, error=f"{type(exc).__name__}: {exc}")
        print(f"[{MINER_NAME}] failed {data.request_id}: {exc!r}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.post(str(data.callback_url), json=envelope.model_dump())
        except Exception as exc:
            print(f"[{MINER_NAME}] callback POST failed for {data.request_id}: {exc!r}")


# ---------------------------------------------------------------------------
# Self-registration and serving (standard template plumbing)
# ---------------------------------------------------------------------------


def connect_subtensor() -> bt.Subtensor:
    for attempt in range(20):
        try:
            subtensor = bt.Subtensor(network=SUBTENSOR_NETWORK)
            subtensor.get_current_block()
            return subtensor
        except Exception:
            print(f"[{MINER_NAME}] Waiting for subtensor... ({attempt + 1}/20)")
            time.sleep(2)
    print(f"[{MINER_NAME}] Could not connect to subtensor")
    sys.exit(1)


def get_alice_wallet() -> Wallet:
    alice_kp = Keypair.create_from_uri("//Alice")
    wallet = Wallet(name="alice", path=str(WALLETS_DIR))
    wallet.set_coldkey(keypair=alice_kp, encrypt=False, overwrite=True)
    wallet.set_coldkeypub(keypair=alice_kp, overwrite=True)
    wallet.set_hotkey(keypair=alice_kp, encrypt=False, overwrite=True)
    return wallet


def find_free_port() -> int:
    lo, hi = PORT_RANGE
    while True:
        port = random.randint(lo, hi)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port


def setup_and_serve(instance_name: str) -> None:
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = os.environ.get("MINER_OPENROUTER_API_KEY") or os.environ.get("VALIDATOR_OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        print(
            f"[{instance_name}] MINER_OPENROUTER_API_KEY (or VALIDATOR_OPENROUTER_API_KEY) "
            f"must be set — miner cannot call OpenRouter."
        )
        sys.exit(1)

    port = find_free_port()
    print(f"[{instance_name}] Starting on port {port} with model={OPENROUTER_MODEL}...")
    subtensor = connect_subtensor()

    wallet = Wallet(name=instance_name, path=str(WALLETS_DIR))
    wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)

    # Fund from Alice if low; Alice transactions can temporarily collide under load.
    balance = subtensor.get_balance(wallet.coldkey.ss58_address)
    if balance < Balance.from_tao(10.0):
        alice = get_alice_wallet()
        for attempt in range(5):
            print(f"[{instance_name}] Funding from Alice... (attempt {attempt + 1}/5)")
            response = subtensor.transfer(
                wallet=alice,
                destination_ss58=wallet.coldkey.ss58_address,
                amount=Balance.from_tao(FUND_AMOUNT_TAO),
                wait_for_inclusion=True,
                wait_for_finalization=True,
                mev_protection=False,
            )
            if response.success:
                break
            print(f"[{instance_name}] Funding failed: {response.message}, retrying...")
            time.sleep(3 + attempt * 2)
        else:
            print(f"[{instance_name}] Funding failed after 5 attempts")
            sys.exit(1)

    if not subtensor.is_hotkey_registered(wallet.hotkey.ss58_address, NETUID):
        for attempt in range(5):
            print(f"[{instance_name}] Registering on subnet {NETUID}... (attempt {attempt + 1}/5)")
            response = subtensor.burned_register(
                wallet=wallet,
                netuid=NETUID,
                wait_for_inclusion=True,
                wait_for_finalization=True,
                mev_protection=False,
            )
            if response.success:
                break
            print(f"[{instance_name}] Registration failed: {response.message}, retrying...")
            time.sleep(3 + attempt * 2)
        else:
            print(f"[{instance_name}] Registration failed after 5 attempts")
            sys.exit(1)
    else:
        print(f"[{instance_name}] Already registered")

    # 127.0.0.1 is silently rejected by subtensor; 127.0.0.2 is the localnet convention.
    print(f"[{instance_name}] Setting axon info: 127.0.0.2:{port}")
    subtensor.serve_axon(
        netuid=NETUID,
        axon=bt.Axon(wallet=wallet, port=port, ip="127.0.0.2", external_ip="127.0.0.2"),
    )

    print(f"[{instance_name}] Serving on 0.0.0.0:{port}{TARGET_PATH}")
    app = Litestar(route_handlers=[handle_task])
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


@click.command()
@click.option("-n", "count", default=1, help="Number of miner instances to spawn.")
def main(count: int) -> None:
    if count == 1:
        setup_and_serve(f"{MINER_NAME}-1")
        return

    processes: list[multiprocessing.Process] = []
    for index in range(count):
        instance_name = f"{MINER_NAME}-{index + 1}"
        proc = multiprocessing.Process(target=setup_and_serve, args=(instance_name,))
        proc.start()
        processes.append(proc)

    try:
        for proc in processes:
            proc.join()
    except KeyboardInterrupt:
        for proc in processes:
            proc.terminate()


if __name__ == "__main__":
    main()
