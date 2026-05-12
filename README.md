# PFFT Miner Bot ⛏️

Automated miner for **Pow Free Fair Token (PFFT)** on Ethereum mainnet.

## Contract

`0xEFAd2Eab7172dDEbE5Ce7a41f5Ddf8fCcE4Ca0CB`

- Max supply: 21,000,000 PFFT
- Per-wallet cap: 10,000 PFFT
- Free mint (0 ETH) — requires Proof-of-Work solve
- PoW difficulty increases as supply grows (24→40 bit)

## Available miners

| Script | Mode | Best for |
|--------|------|----------|
| `pfft_miner.py` | CPU | Any VPS / local machine |
| `pfft_gpu_miner.py` | NVIDIA CUDA GPU | GPU VPS with NVIDIA driver + CUDA |

## How it works

1. Reads current PoW challenge from contract
2. Brute-forces a valid nonce (keccak256 hash must be below difficulty target)
3. Verifies nonce with `isValidPow(wallet, nonce)`
4. Submits `freeMint(powNonce)` transaction (only costs gas)
5. Repeats until wallet cap (10,000 PFFT) or max supply reached

---

# Full Fresh VPS Tutorial (Ubuntu 22.04 / 24.04)

Use this section if your VPS is brand new and has nothing installed yet.

## 1. Login to VPS

```bash
ssh root@YOUR_VPS_IP
```

If you are not root, add `sudo` before apt/systemctl commands.

## 2. Update system

```bash
apt update && apt upgrade -y
apt install -y git curl wget nano tmux htop ca-certificates build-essential pkg-config
```

## 3. Install Python + venv tools

```bash
apt install -y python3 python3-pip python3-venv python3-dev
python3 --version
pip3 --version
```

Recommended: use a virtual environment so dependencies do not mess with system Python.

## 4. Clone repo

```bash
cd /root
git clone https://github.com/deniginsb/pfft-miner.git
cd pfft-miner
```

If repo already exists:

```bash
cd /root/pfft-miner
git pull origin main
```

## 5. Create Python virtual environment

```bash
cd /root/pfft-miner
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

After this, your shell should show `(venv)`.

## 6. Create `.env`

```bash
cp .env.example .env
nano .env
```

Fill it like this:

```bash
PRIVATE_KEY=your_private_key_here
ETH_RPC=https://ethereum-rpc.publicnode.com
```

Recommended: use your own RPC for better stability, for example Alchemy/Infura/QuickNode.

Save nano:

- Press `CTRL + O`
- Press `Enter`
- Press `CTRL + X`

Secure the env file:

```bash
chmod 600 .env
```

Important: wallet needs ETH for gas. Free mint costs 0 ETH, but transaction gas still needs ETH.

---

# CPU Miner Setup

Use this for normal VPS or if GPU setup is not ready.

The CPU miner is **multi-process** — it spawns one worker per CPU core so
hashrate scales (close to) linearly with cores. All tuning lives in `.env`
(see `.env.example` for the full list: `WORKERS`, `GAS_LIMIT`,
`MAX_FEE_GWEI`, …).

> For a step-by-step setup walkthrough in **Bahasa Indonesia** including
> tuning tips, see [CPU_LOCAL_SETUP.md](CPU_LOCAL_SETUP.md).

## One-shot installer (Linux / macOS / WSL)

```bash
cd pfft-miner
bash setup_cpu.sh                  # creates venv, installs deps, copies .env
nano .env                          # set PRIVATE_KEY and ETH_RPC
./run_cpu.sh                       # foreground
./run_cpu.sh --tmux                # detachable tmux session
```

## Manual install

```bash
cd /root/pfft-miner
source venv/bin/activate
python -m pip install -r requirements-cpu.txt
```

## Run CPU miner

```bash
cd /root/pfft-miner
source venv/bin/activate
python3 pfft_miner.py
```

## Run CPU miner inside tmux

This keeps miner running after you close SSH.

```bash
tmux new -s pfft-cpu
cd /root/pfft-miner
source venv/bin/activate
python3 pfft_miner.py
```

Detach tmux:

```bash
CTRL + B, then press D
```

Open tmux again:

```bash
tmux attach -t pfft-cpu
```

---

# NVIDIA GPU Miner Setup

Use this only on VPS with NVIDIA GPU.

PyCUDA can take a long time to install because it compiles native CUDA code. On a fresh VPS it can take 5–30 minutes.

## 1. Check if GPU is detected

```bash
nvidia-smi
```

If `nvidia-smi` works, skip to CUDA check.

If command not found or driver missing, install NVIDIA driver.

## 2. Install NVIDIA driver

Ubuntu usually provides recommended drivers.

```bash
apt install -y ubuntu-drivers-common
ubuntu-drivers devices
ubuntu-drivers autoinstall
reboot
```

After reboot, login again and check:

```bash
nvidia-smi
```

Expected: it shows GPU name, driver version, CUDA version.

## 3. Install CUDA toolkit / nvcc

PyCUDA build usually needs `nvcc`.

Check first:

```bash
which nvcc
nvcc --version
```

If `nvcc` is missing, install CUDA toolkit:

```bash
apt update
apt install -y nvidia-cuda-toolkit
```

Then check again:

```bash
which nvcc
nvcc --version
```

If `apt install nvidia-cuda-toolkit` is not available on your image, install CUDA from NVIDIA repo:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt update
apt install -y cuda-toolkit
```

For Ubuntu 24.04, replace `ubuntu2204` with `ubuntu2404` in the URL if needed.

## 4. Export CUDA paths if nvcc exists but PyCUDA cannot find it

```bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

Optional, make it permanent:

```bash
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

## 5. Install GPU dependencies

```bash
cd /root/pfft-miner
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

`requirements.txt` includes:

```txt
web3>=6.0.0
pycryptodome>=3.20.0
pycuda>=2024.1
```

If PyCUDA install looks stuck at:

```txt
Installing build dependencies ... /
```

That is normal. Wait 5–30 minutes. It is compiling.

## 6. Run GPU miner

```bash
cd /root/pfft-miner
source venv/bin/activate
python3 pfft_gpu_miner.py
```

## 7. Run GPU miner inside tmux

```bash
tmux new -s pfft-gpu
cd /root/pfft-miner
source venv/bin/activate
python3 pfft_gpu_miner.py
```

Detach:

```bash
CTRL + B, then press D
```

Attach again:

```bash
tmux attach -t pfft-gpu
```

## 8. GPU tuning

GPU miner starts from a random nonce every round. This is important because the
contract can reject reused nonces; if the miner starts from 0 every round it may
find the same valid nonce again and waste gas on a reverted duplicate mint.

Default:

```bash
GPU_BLOCKS=65535
GPU_THREADS=256
GPU_BATCHES_PER_STATUS=32
```

Run with custom tuning:

```bash
GPU_BLOCKS=65535 GPU_THREADS=256 python3 pfft_gpu_miner.py
```

If GPU is weak or crashes, lower it:

```bash
GPU_BLOCKS=32768 GPU_THREADS=128 python3 pfft_gpu_miner.py
```

If GPU is strong, try:

```bash
GPU_BLOCKS=65535 GPU_THREADS=512 python3 pfft_gpu_miner.py
```

---

# Run as systemd service

## CPU systemd service

A CPU service file is included.

```bash
cd /root/pfft-miner
sudo cp pfft-miner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pfft-miner
sudo journalctl -u pfft-miner -f
```

## GPU systemd service

Create a separate GPU service:

```bash
nano /etc/systemd/system/pfft-gpu-miner.service
```

Paste this:

```ini
[Unit]
Description=PFFT GPU Miner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/pfft-miner
Environment=PATH=/root/pfft-miner/venv/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=LD_LIBRARY_PATH=/usr/local/cuda/lib64
ExecStart=/root/pfft-miner/venv/bin/python /root/pfft-miner/pfft_gpu_miner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start it:

```bash
systemctl daemon-reload
systemctl enable --now pfft-gpu-miner
journalctl -u pfft-gpu-miner -f
```

Stop/restart:

```bash
systemctl stop pfft-gpu-miner
systemctl restart pfft-gpu-miner
```

---

# Troubleshooting

## PyCUDA install is very slow

Normal. PyCUDA compiles C++/CUDA extension from source. Wait 5–30 minutes.

## PyCUDA install fails: `nvcc not found`

```bash
which nvcc
nvcc --version
apt install -y nvidia-cuda-toolkit
```

Then retry:

```bash
source /root/pfft-miner/venv/bin/activate
python -m pip install pycuda
```

## PyCUDA install fails: Python.h missing

```bash
apt install -y python3-dev build-essential
source /root/pfft-miner/venv/bin/activate
python -m pip install pycuda
```

## GPU script says no CUDA GPU

Check:

```bash
nvidia-smi
lsmod | grep nvidia
```

If missing, reinstall driver and reboot:

```bash
ubuntu-drivers autoinstall
reboot
```

## Miner cannot connect to RPC

Use better RPC in `.env`:

```bash
ETH_RPC=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
```

Then restart miner.

## Transaction failed / insufficient funds

Wallet needs ETH for gas. Send small ETH to miner wallet.

Recommended minimum:

```txt
0.0001 ETH or more
```

## Check logs if using systemd

CPU:

```bash
journalctl -u pfft-miner -f
```

GPU:

```bash
journalctl -u pfft-gpu-miner -f
```

---

# Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIVATE_KEY` | required | Mining wallet private key |
| `ETH_RPC` | `https://ethereum-rpc.publicnode.com` | Ethereum RPC endpoint |
| `GAS_LIMIT` | `200000` | Transaction gas limit |
| `PAUSE_BETWEEN_ROUNDS` | `5` CPU / `3` GPU | Cooldown between mints |
| `GPU_BLOCKS` | `65535` | CUDA grid blocks per kernel launch |
| `GPU_THREADS` | `256` | CUDA threads per block |
| `GPU_BATCHES_PER_STATUS` | `32` | Kernel batches before status print |

---

# Current stats (May 2026)

| Metric | Value |
|--------|-------|
| Supply | ~6.5M / 21M (31%) |
| Difficulty | 28-bit (7 hex zeros) |
| CPU hashrate | ~175k H/s (Python + pycryptodome) |
| GPU hashrate | Depends on NVIDIA model |
| CPU time per mint | ~25 min at 28-bit |
| PFFT per mint | ~284 |
| Gas per mint | ~0.00002 ETH |

---

# Security

- `.env` contains your private key — **NEVER commit it**
- `.env` is gitignored
- Use a dedicated mining wallet with only enough ETH for gas
- Do not run with your main wallet private key
- Use `chmod 600 .env`

---

# Files

| File | Description |
|------|-------------|
| `pfft_miner.py` | CPU miner script |
| `pfft_gpu_miner.py` | NVIDIA CUDA GPU miner script |
| `requirements.txt` | Python dependencies for CPU + GPU miner |
| `.env.example` | Config template |
| `pfft-miner.service` | CPU systemd unit file |
