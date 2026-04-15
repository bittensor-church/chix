# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bittensor",
#     "bittensor-wallet",
#     "litestar[standard]",
#     "httpx",
#     "click",
# ]
# ///
"""
Localnet miner fixture template.

Models a miner accepting work from a validator via an HTTP POST request.,
then POSTing the result back to the validator via a callback URL.

Usage: uv run localnet/miners/miner-<profile>.py [-n NUM_INSTANCES]
"""

from __future__ import annotations

import multiprocessing
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
from litestar import Litestar, post
from pydantic import BaseModel

MINER_NAME = "honest"
PORT_RANGE = (10000, 65000)

# Must match the validator's AsyncHttpNeuronCommunicator target_path
TARGET_PATH = "/task"

WALLETS_DIR = Path(__file__).parent.parent / "wallets"
SUBTENSOR_NETWORK = "ws://127.0.0.1:9944"
NETUID = 2
FUND_AMOUNT_TAO = 1000.0


# ---------------------------------------------------------------------------
# Async callback protocol (matches nexus envelope types)
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
# CUSTOMIZE THIS: subnet-specific request handling
# ---------------------------------------------------------------------------


def handle_request(input_data: dict[str, Any]) -> dict[str, Any]:
    """Transform validator input into miner output.

    Override this with your subnet's logic:
    - If the task is cheap: implement it for real
    - If the task needs external APIs: proxy to a real service
    - If the task needs heavy compute: return plausible mock data

    The input_data dict contains the serialized InputModel from the validator.
    Return a dict matching the validator's expected OutputModel.
    """
    return input_data


# ---------------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------------


@post(TARGET_PATH)
async def handle_task(data: RequestEnvelope) -> None:
    """Receive a task from the validator, process it, POST result back."""
    print(f"[miner] Received request {data.request_id}")

    try:
        output = handle_request(data.input)
        response = ResponseEnvelope(request_id=data.request_id, output=output)
    except Exception as exc:
        response = ResponseEnvelope(request_id=data.request_id, error=str(exc))

    async with httpx.AsyncClient() as client:
        try:
            await client.post(str(data.callback_url), json=response.model_dump())
            print(f"[miner] Responded to {data.request_id}")
        except Exception as exc:
            print(f"[miner] Failed to callback for {data.request_id}: {exc}")


# ---------------------------------------------------------------------------
# Self-registration and serving
# ---------------------------------------------------------------------------


def connect_subtensor() -> bt.Subtensor:
    for attempt in range(20):
        try:
            subtensor = bt.Subtensor(network=SUBTENSOR_NETWORK)
            subtensor.get_current_block()
            return subtensor
        except Exception:
            print(f"[miner] Waiting for subtensor... ({attempt + 1}/20)")
            time.sleep(2)
    print("[miner] Could not connect to subtensor")
    sys.exit(1)


def get_alice_wallet() -> Wallet:
    """Create a wallet backed by Alice's well-known devnet keypair."""
    alice_kp = Keypair.create_from_uri("//Alice")
    wallet = Wallet(name="alice", path=str(WALLETS_DIR))
    wallet.set_coldkey(keypair=alice_kp, encrypt=False, overwrite=True)
    wallet.set_coldkeypub(keypair=alice_kp, overwrite=True)
    wallet.set_hotkey(keypair=alice_kp, encrypt=False, overwrite=True)
    return wallet


def find_free_port() -> int:
    """Find a free port by trying random ports in the range."""
    lo, hi = PORT_RANGE
    while True:
        port = random.randint(lo, hi)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port


def setup_and_serve(instance_name: str) -> None:
    """Idempotent setup then serve. Runs in its own process."""
    port = find_free_port()
    print(f"[{instance_name}] Starting on port {port}...")
    subtensor = connect_subtensor()

    wallet = Wallet(name=instance_name, path=str(WALLETS_DIR))
    wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)

    # Fund from Alice if needed (retry — concurrent transfers from Alice get temporarily banned)
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

    # Register on subnet (retry — same nonce contention can happen here)
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

    print(f"[{instance_name}] Setting axon info: 127.0.0.1:{port}")
    subtensor.serve_axon(
        netuid=NETUID,
        axon=bt.Axon(wallet=wallet, port=port, ip="127.0.0.2", external_ip="127.0.0.2"),
    )

    print(f"[{instance_name}] Serving on 0.0.0.0:{port}{TARGET_PATH}")
    app = Litestar(route_handlers=[handle_task])
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("-n", "count", default=1, help="Number of instances to spawn.")
def main(count: int) -> None:
    if count == 1:
        setup_and_serve(f"{MINER_NAME}-1")
        return

    processes: list[multiprocessing.Process] = []
    for i in range(count):
        instance_name = f"{MINER_NAME}-{i + 1}"
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
