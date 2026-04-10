# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bittensor",
#     "bittensor-wallet",
# ]
# ///
"""
Localnet bootstrap script.

Sets up the local subnet infrastructure:
- Transfers TAO from Alice (pre-funded devnet account) to owner and validator wallets
- Creates and activates subnet (netuid 2, since netuid 1 is owned by zero-key)
- Registers and stakes validator neuron

Prerequisites: subtensor must be running (docker compose up).

Usage: uv run localnet/bootstrap.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import bittensor as bt
from bittensor.utils.balance import Balance
from bittensor_wallet import Keypair, Wallet

WALLETS_DIR = Path(__file__).parent / "wallets"
SUBTENSOR_NETWORK = "ws://127.0.0.1:9944"
# netuid 1 is pre-owned by zero-key in the devnet image — nobody has its private key
EXPECTED_NETUID = 2
VALIDATOR_STAKE_TAO = 1000.0
FUND_AMOUNT_TAO = 10_000.0


def wait_for_subtensor(network: str, retries: int = 30, delay: float = 2.0) -> bt.Subtensor:
    """Wait for the local subtensor to become reachable."""
    for attempt in range(retries):
        try:
            sub = bt.Subtensor(network=network)
            block = sub.get_current_block()
            print(f"Connected to subtensor at block {block}")
            return sub
        except Exception:
            print(f"Waiting for subtensor... (attempt {attempt + 1}/{retries})")
            time.sleep(delay)
    print("Failed to connect to subtensor. Is docker compose running?")
    sys.exit(1)


def get_alice_wallet() -> Wallet:
    """Create a wallet backed by Alice's well-known devnet keypair."""
    alice_kp = Keypair.create_from_uri("//Alice")
    wallet = Wallet(name="alice", path=str(WALLETS_DIR))
    wallet.set_coldkey(keypair=alice_kp, encrypt=False, overwrite=True)
    wallet.set_coldkeypub(keypair=alice_kp, overwrite=True)
    wallet.set_hotkey(keypair=alice_kp, encrypt=False, overwrite=True)
    return wallet


def get_or_create_wallet(name: str) -> Wallet:
    """Create a wallet if it doesn't exist, using localnet wallets directory."""
    wallet = Wallet(name=name, path=str(WALLETS_DIR))
    wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)
    return wallet


def fund_wallet(subtensor: bt.Subtensor, alice: Wallet, target: Wallet) -> None:
    """Transfer TAO from Alice to a target wallet if balance is low."""
    balance = subtensor.get_balance(target.coldkey.ss58_address)
    if balance > Balance.from_tao(100.0):
        print(f"  {target.name} already funded (balance: {balance})")
        return
    print(f"  Funding {target.name} with {FUND_AMOUNT_TAO} TAO from Alice...")
    response = subtensor.transfer(
        wallet=alice,
        destination_ss58=target.coldkey.ss58_address,
        amount=Balance.from_tao(FUND_AMOUNT_TAO),
        wait_for_inclusion=True,
        wait_for_finalization=True,
        mev_protection=False,
    )
    if not response.success:
        print(f"  Transfer failed: {response.message}")
        sys.exit(1)
    print(f"  {target.name} funded")


def create_and_activate_subnet(subtensor: bt.Subtensor, owner: Wallet) -> int:
    """Create a new subnet and activate it. Returns the netuid."""
    if subtensor.subnet_exists(netuid=EXPECTED_NETUID):
        print(f"Subnet {EXPECTED_NETUID} already exists")
        return EXPECTED_NETUID

    print("Creating subnet...")
    response = subtensor.register_subnet(
        wallet=owner,
        wait_for_inclusion=True,
        wait_for_finalization=True,
        mev_protection=False,
    )
    if not response.success:
        print(f"Subnet registration failed: {response.message}")
        sys.exit(1)

    subnets = subtensor.all_subnets()
    owned = [s for s in subnets if s.owner_coldkey == owner.coldkey.ss58_address]
    netuid = max(owned, key=lambda s: s.network_registered_at).netuid
    print(f"Subnet created with netuid {netuid}")

    # Activate the subnet — must wait for start_call delay
    current_block = subtensor.get_current_block()
    delay_blocks = subtensor.get_start_call_delay().value
    target_block = current_block + delay_blocks + 1
    print(f"Waiting {delay_blocks} blocks to activate subnet (current: {current_block}, target: {target_block})...")
    subtensor.wait_for_block(target_block)

    print("Activating subnet...")
    response = subtensor.start_call(
        wallet=owner,
        netuid=netuid,
        wait_for_inclusion=True,
        wait_for_finalization=True,
        mev_protection=False,
    )
    if not response.success:
        print(f"Subnet activation failed: {response.message}")
        sys.exit(1)
    print(f"Subnet {netuid} activated")
    return netuid


def register_neuron(subtensor: bt.Subtensor, wallet: Wallet, netuid: int) -> None:
    """Register a neuron if not already registered."""
    if subtensor.is_hotkey_registered(wallet.hotkey.ss58_address, netuid):
        print(f"  {wallet.name} already registered on subnet {netuid}")
        return
    print(f"  Registering {wallet.name} on subnet {netuid}...")
    response = subtensor.burned_register(
        wallet=wallet,
        netuid=netuid,
        wait_for_inclusion=True,
        wait_for_finalization=True,
        mev_protection=False,
    )
    if not response.success:
        print(f"  Registration failed: {response.message}")
        sys.exit(1)
    print(f"  {wallet.name} registered")


def stake_validator(subtensor: bt.Subtensor, wallet: Wallet, netuid: int) -> None:
    """Add stake to the validator."""
    print(f"  Staking {VALIDATOR_STAKE_TAO} TAO for {wallet.name}...")
    response = subtensor.add_stake(
        wallet=wallet,
        netuid=netuid,
        hotkey_ss58=wallet.hotkey.ss58_address,
        amount=Balance.from_tao(VALIDATOR_STAKE_TAO),
        wait_for_inclusion=True,
        wait_for_finalization=True,
        mev_protection=False,
    )
    if not response.success:
        print(f"  Staking failed: {response.message}")
        sys.exit(1)
    print(f"  {wallet.name} staked")


def main() -> None:
    subtensor = wait_for_subtensor(SUBTENSOR_NETWORK)
    alice = get_alice_wallet()

    alice_balance = subtensor.get_balance(alice.coldkey.ss58_address)
    print(f"Alice balance: {alice_balance}")

    # Owner: creates and owns the subnet
    print("\n--- Setting up owner wallet ---")
    owner = get_or_create_wallet("owner")
    fund_wallet(subtensor, alice, owner)

    print("\n--- Creating subnet ---")
    netuid = create_and_activate_subnet(subtensor, owner)

    # Validator: registers and stakes
    print("\n--- Setting up validator ---")
    validator = get_or_create_wallet("validator")
    fund_wallet(subtensor, alice, validator)
    register_neuron(subtensor, validator, netuid)
    stake_validator(subtensor, validator, netuid)

    print("\n--- Bootstrap complete ---")
    print(f"Subnet:    {netuid}")
    print(f"Owner:     {owner.coldkey.ss58_address}")
    print(f"Validator: {validator.hotkey.ss58_address}")
    print("\nNext: start a miner with `uv run localnet/miners/<profile>.py`")


if __name__ == "__main__":
    main()
