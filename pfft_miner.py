#!/usr/bin/env python3
"""
PFFT Miner Bot - Pow Free Fair Token (CPU)
Ethereum Mainnet | Contract: 0xEFAd2Eab7172dDEbE5Ce7a41f5Ddf8fCcE4Ca0CB

Multi-process CPU miner: each worker scans a strided slice of the nonce space,
so hashrate scales (close to) linearly with WORKERS.

Usage:
  cp .env.example .env   # set PRIVATE_KEY + optional tuning vars
  python3 pfft_miner.py

All tuning is via .env / environment variables -- see .env.example for the
full list (WORKERS, GAS_LIMIT, MAX_FEE_GWEI, ...).
"""

import os
import sys
import time
import struct
import signal
import multiprocessing as mp
from pathlib import Path

# ---------------------------------------------------------------------------
# .env loader (no external dependency)
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"WARN: invalid int for {name}={raw!r}, using default {default}")
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"WARN: invalid float for {name}={raw!r}, using default {default}")
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


# ---------------------------------------------------------------------------
# Config (all overridable via .env)
# ---------------------------------------------------------------------------
CONTRACT             = os.environ.get("CONTRACT", "0xEFAd2Eab7172dDEbE5Ce7a41f5Ddf8fCcE4Ca0CB")
CHAIN_ID             = _env_int("CHAIN_ID", 1)
RPC                  = os.environ.get("ETH_RPC", "https://ethereum-rpc.publicnode.com")
PRIVATE_KEY          = os.environ.get("PRIVATE_KEY", "")

_CPU                 = mp.cpu_count() or 1
WORKERS              = max(1, _env_int("WORKERS", max(1, _CPU - 1)))  # leave 1 core for OS by default
GAS_LIMIT            = _env_int("GAS_LIMIT", 200_000)
PAUSE_BETWEEN_ROUNDS = _env_int("PAUSE_BETWEEN_ROUNDS", 5)
REPORT_INTERVAL_SEC  = _env_float("REPORT_INTERVAL_SEC", 5.0)
RPC_TIMEOUT          = _env_int("RPC_TIMEOUT", 30)
TX_TIMEOUT           = _env_int("TX_TIMEOUT", 180)
MIN_ETH_BALANCE      = _env_float("MIN_ETH_BALANCE", 0.00005)

# Gas strategy:
#   MAX_FEE_GWEI > 0   -> EIP-1559 (recommended on mainnet) using maxFeePerGas/maxPriorityFeePerGas
#   MAX_FEE_GWEI == 0  -> legacy gasPrice = w3.eth.gas_price (auto)
MAX_FEE_GWEI         = _env_float("MAX_FEE_GWEI", 0.0)
MAX_PRIORITY_FEE_GWEI = _env_float("MAX_PRIORITY_FEE_GWEI", 1.0)

VERBOSE              = _env_bool("VERBOSE", False)


# ---------------------------------------------------------------------------
# Keccak256 (pycryptodome C extension; releases GIL)
# ---------------------------------------------------------------------------
try:
    from Crypto.Hash import keccak as _keccak_mod
except ImportError:
    print("Missing dependency. Install with:")
    print("  pip install -r requirements.txt")
    print("  (or: pip install pycryptodome web3)")
    sys.exit(1)


def keccak256(data: bytes) -> bytes:
    return _keccak_mod.new(digest_bits=256, data=data).digest()


# ---------------------------------------------------------------------------
# Multi-process PoW solver
# ---------------------------------------------------------------------------
def _pow_worker(
    worker_id: int,
    num_workers: int,
    challenge: bytes,
    target_bytes: bytes,
    found_event,
    result_q,
    attempts_counter,
):
    """
    Each worker scans nonces: worker_id, worker_id+N, worker_id+2N, ...
    Reports total attempted hashes into a shared atomic counter.
    """
    from Crypto.Hash import keccak as _km  # re-import in child process

    target_int = int.from_bytes(target_bytes, "big")
    buf = bytearray(challenge) + bytearray(32)
    nonce = worker_id
    local_attempts = 0
    FLUSH_EVERY = 1 << 14  # 16384 hashes between counter flushes

    while not found_event.is_set():
        # Pack nonce into last 32 bytes as big-endian uint256
        struct.pack_into(">QQQQ", buf, 32, 0, 0, 0, nonce)
        h = _km.new(digest_bits=256, data=bytes(buf)).digest()
        if int.from_bytes(h, "big") <= target_int:
            try:
                result_q.put((worker_id, nonce, h), timeout=5)
            finally:
                found_event.set()
            break

        nonce += num_workers
        local_attempts += 1
        if local_attempts >= FLUSH_EVERY:
            with attempts_counter.get_lock():
                attempts_counter.value += local_attempts
            local_attempts = 0

    # final flush
    if local_attempts:
        with attempts_counter.get_lock():
            attempts_counter.value += local_attempts


def solve_pow_parallel(
    challenge: bytes,
    target: int,
    num_workers: int,
    report_interval: float = 5.0,
):
    """Spawn N workers, return (nonce, hash) of the first solver."""
    target_bytes = target.to_bytes(32, "big")
    ctx = mp.get_context("spawn")
    found = ctx.Event()
    result_q = ctx.Queue()
    attempts_counter = ctx.Value("Q", 0)  # unsigned long long

    workers = []
    for wid in range(num_workers):
        p = ctx.Process(
            target=_pow_worker,
            args=(wid, num_workers, challenge, target_bytes, found, result_q, attempts_counter),
            daemon=True,
        )
        p.start()
        workers.append(p)

    start = time.time()
    last_report = start
    last_attempts = 0

    try:
        while not found.is_set():
            now = time.time()
            if now - last_report >= report_interval:
                with attempts_counter.get_lock():
                    cur = attempts_counter.value
                elapsed = now - start
                rate = cur / elapsed if elapsed > 0 else 0
                window_rate = (cur - last_attempts) / (now - last_report)
                last_report = now
                last_attempts = cur
                print(
                    f"  mining: {cur:>15,} H | "
                    f"avg {rate:>10,.0f} H/s | "
                    f"now {window_rate:>10,.0f} H/s | "
                    f"x{num_workers} | "
                    f"{elapsed:>5.0f}s",
                    end="\r",
                    flush=True,
                )
            time.sleep(0.1)

        # We have a result
        try:
            wid, nonce, h = result_q.get(timeout=10)
        except Exception:
            print("\n  WARN: solver flagged 'found' but no result delivered; retrying")
            return None, None

        elapsed = time.time() - start
        with attempts_counter.get_lock():
            total = attempts_counter.value
        rate = total / elapsed if elapsed > 0 else 0
        print(
            f"\n  FOUND nonce={nonce} (worker {wid}) | "
            f"{total:,} H | {elapsed:.1f}s | {rate:,.0f} H/s avg"
        )
        return nonce, h
    finally:
        found.set()
        for p in workers:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()


# ---------------------------------------------------------------------------
# Contract interaction
# ---------------------------------------------------------------------------
def load_contract(w3):
    abi = [
        {"inputs": [], "name": "currentPowHexZeros",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "totalMinted",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "MAX_SUPPLY",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "requested", "type": "uint256"}],
         "name": "calculateActualMint",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "user", "type": "address"}],
         "name": "currentPowChallenge",
         "outputs": [{"name": "", "type": "bytes32"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "user", "type": "address"},
                    {"name": "powNonce", "type": "uint256"}],
         "name": "isValidPow",
         "outputs": [{"name": "", "type": "bool"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "powNonce", "type": "uint256"}],
         "name": "freeMint",
         "outputs": [],
         "stateMutability": "nonpayable", "type": "function"},
        {"inputs": [{"name": "user", "type": "address"}],
         "name": "mintedByAddress",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
        {"inputs": [{"name": "account", "type": "address"}],
         "name": "balanceOf",
         "outputs": [{"name": "", "type": "uint256"}],
         "stateMutability": "view", "type": "function"},
    ]
    return w3.eth.contract(address=w3.to_checksum_address(CONTRACT), abi=abi)


def get_status(w3, contract, wallet_addr):
    hex_zeros = contract.functions.currentPowHexZeros().call()
    total_minted = contract.functions.totalMinted().call()
    max_supply = contract.functions.MAX_SUPPLY().call()
    next_mint = contract.functions.calculateActualMint(w3.to_wei(1000, "ether")).call()
    wallet_minted = contract.functions.mintedByAddress(wallet_addr).call()
    wallet_bal = contract.functions.balanceOf(wallet_addr).call()
    target = (2 ** 256 - 1) >> (hex_zeros * 4)
    progress = (total_minted * 100.0 / max_supply) if max_supply else 0
    return {
        "hex_zeros": hex_zeros,
        "difficulty_bits": hex_zeros * 4,
        "total_minted": total_minted,
        "max_supply": max_supply,
        "next_mint": next_mint,
        "wallet_minted": wallet_minted,
        "wallet_bal": wallet_bal,
        "target": target,
        "progress": progress,
    }


def get_challenge(contract, wallet_addr):
    c = contract.functions.currentPowChallenge(wallet_addr).call()
    return c if isinstance(c, bytes) else c.to_bytes(32, "big")


def _build_gas(w3, tx):
    """Apply gas strategy: EIP-1559 if MAX_FEE_GWEI > 0, else legacy."""
    if MAX_FEE_GWEI > 0:
        tx["maxFeePerGas"] = int(MAX_FEE_GWEI * 1e9)
        tx["maxPriorityFeePerGas"] = int(MAX_PRIORITY_FEE_GWEI * 1e9)
        tx.pop("gasPrice", None)
    else:
        tx["gasPrice"] = w3.eth.gas_price
        tx.pop("maxFeePerGas", None)
        tx.pop("maxPriorityFeePerGas", None)
    return tx


def submit_mint(w3, wallet, contract, nonce: int) -> bool:
    try:
        fn = contract.functions.freeMint(nonce)
        tx = fn.build_transaction({
            "from": wallet.address,
            "nonce": w3.eth.get_transaction_count(wallet.address),
            "chainId": CHAIN_ID,
            "gas": GAS_LIMIT,
        })
        tx = _build_gas(w3, tx)

        if VERBOSE:
            print(f"  TX gas: {tx.get('gasPrice') or (tx.get('maxFeePerGas'), tx.get('maxPriorityFeePerGas'))}")

        signed = wallet.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
        tx_hash = w3.eth.send_raw_transaction(raw)
        print(f"  TX: https://etherscan.io/tx/0x{tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=TX_TIMEOUT)
        if receipt.status == 1:
            print(f"  MINT OK | block {receipt.blockNumber} | gas {receipt.gasUsed}")
            return True
        print(f"  REVERTED | gas {receipt.gasUsed}")
        return False
    except Exception as e:
        print(f"  TX error: {e}")
        return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
running = True


def handle_signal(sig, frame):
    global running
    print("\n  Stopping miner (signal received)...")
    running = False


def main():
    from web3 import Web3
    from eth_account import Account

    print("=" * 64)
    print("  PFFT Miner Bot - CPU multi-process")
    print(f"  Contract:        {CONTRACT}")
    print(f"  RPC:             {RPC}")
    print(f"  Workers:         {WORKERS} (cpus detected: {_CPU})")
    print(f"  Gas limit:       {GAS_LIMIT}")
    if MAX_FEE_GWEI > 0:
        print(f"  Gas strategy:    EIP-1559 maxFee={MAX_FEE_GWEI} gwei tip={MAX_PRIORITY_FEE_GWEI} gwei")
    else:
        print(f"  Gas strategy:    auto (legacy gasPrice from node)")
    print(f"  Round cooldown:  {PAUSE_BETWEEN_ROUNDS}s")
    print("=" * 64)

    w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": RPC_TIMEOUT}))
    if not w3.is_connected():
        print("ERROR: cannot connect to RPC")
        sys.exit(1)
    print(f"Connected | block #{w3.eth.block_number}")

    pk = PRIVATE_KEY.strip()
    if not pk or pk == "your_private_key_here":
        print("ERROR: PRIVATE_KEY not set. Copy .env.example -> .env and set it.")
        sys.exit(1)
    if not pk.startswith("0x"):
        pk = "0x" + pk
    wallet = Account.from_key(pk)
    print(f"Wallet: {wallet.address}")

    eth_bal = w3.eth.get_balance(wallet.address) / 1e18
    print(f"ETH balance: {eth_bal:.6f}")
    if eth_bal < MIN_ETH_BALANCE:
        print(f"WARN: low ETH (< {MIN_ETH_BALANCE}). Need ETH for gas.")

    contract = load_contract(w3)
    s = get_status(w3, contract, wallet.address)
    print(f"\nContract status:")
    print(f"  Supply:     {s['total_minted']/1e18:>12,.0f} / {s['max_supply']/1e18:,.0f} PFFT ({s['progress']:.1f}%)")
    print(f"  Next mint:  ~{s['next_mint']/1e18:,.2f} PFFT")
    print(f"  Difficulty: {s['hex_zeros']} hex zeros ({s['difficulty_bits']}-bit)")
    print(f"  Wallet:     {s['wallet_minted']/1e18:,.2f} / 10,000 PFFT minted | bal {s['wallet_bal']/1e18:,.2f}")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    round_num = 0
    total_minted_count = 0
    total_pfft_earned = 0.0
    global_start = time.time()

    while running:
        round_num += 1
        print(f"\n{'-' * 64}")
        print(f"  Round #{round_num}")
        print(f"{'-' * 64}")

        try:
            s = get_status(w3, contract, wallet.address)
            print(f"  Supply: {s['total_minted']/1e18:,.0f} ({s['progress']:.1f}%) | "
                  f"Next: ~{s['next_mint']/1e18:,.2f} PFFT | "
                  f"Diff: {s['difficulty_bits']}-bit")

            if s["total_minted"] >= s["max_supply"]:
                print("  Max supply reached!")
                break
            if s["wallet_minted"] >= 10_000 * 1e18:
                print("  Wallet cap (10,000 PFFT) reached!")
                break
        except Exception as e:
            print(f"  Status error: {e}, retrying in 15s...")
            time.sleep(15)
            continue

        challenge = get_challenge(contract, wallet.address)

        print(f"  Mining ({s['difficulty_bits']}-bit, {WORKERS} workers)...")
        nonce, _h = solve_pow_parallel(
            challenge, s["target"], WORKERS, REPORT_INTERVAL_SEC,
        )

        if nonce is None:
            print("  Solver returned no result, retrying...")
            continue

        # Verify on-chain before paying gas
        try:
            ok = contract.functions.isValidPow(wallet.address, nonce).call()
            if not ok:
                print("  Nonce invalid on-chain (supply moved?), re-mining...")
                continue
        except Exception as e:
            print(f"  Verify error: {e} - submitting anyway")

        if submit_mint(w3, wallet, contract, nonce):
            total_minted_count += 1
            earned = s["next_mint"] / 1e18
            total_pfft_earned += earned
            print(f"  +{earned:,.2f} PFFT | session total: {total_pfft_earned:,.2f} PFFT in {total_minted_count} mints")
            try:
                bal = contract.functions.balanceOf(wallet.address).call()
                print(f"  PFFT balance: {bal/1e18:,.2f}")
            except Exception:
                pass

        elapsed = time.time() - global_start
        print(f"  Session: {total_minted_count} mints | {total_pfft_earned:,.2f} PFFT | {elapsed/60:.1f} min")

        if running:
            print(f"  Cooldown {PAUSE_BETWEEN_ROUNDS}s...")
            time.sleep(PAUSE_BETWEEN_ROUNDS)

    print(f"\n{'=' * 64}")
    print(f"  Session summary")
    print(f"  Mints:     {total_minted_count}")
    print(f"  PFFT:      {total_pfft_earned:,.2f}")
    print(f"  Runtime:   {(time.time() - global_start)/60:.1f} min")
    print(f"{'=' * 64}")


if __name__ == "__main__":
    # spawn is required on macOS and safer on Linux (no fd inheritance surprises)
    try:
        mp.set_start_method("spawn", force=False)
    except RuntimeError:
        pass
    main()
