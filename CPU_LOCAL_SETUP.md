# PFFT CPU Miner — Setup Lokal (Bahasa Indonesia)

Panduan ini khusus untuk menjalankan miner **di mesin lokal kamu sendiri**
(laptop / PC / VPS pribadi) memakai **CPU saja**, tanpa GPU.

Versi `pfft_miner.py` yang ada di branch ini sudah:

- **Multi-process**: tiap CPU core punya worker sendiri (hashrate ~Nx vs versi single-thread asli).
- **Sepenuhnya bisa di-tune lewat `.env`** — tidak perlu edit kode lagi.
- **Mendukung EIP-1559** (gas yang lebih hemat & predictable di Ethereum mainnet).
- **Stride nonce search** — tidak ada dua worker yang mengecek nonce yang sama.

---

## 1. Prasyarat

- **Python 3.10+** (cek: `python3 --version`)
- **`pip` + `venv`** module
- **Wallet EVM dengan sedikit ETH** untuk bayar gas mint (free mint = 0 ETH, tapi gas tetap perlu).
  Saran: pakai wallet **baru** yang khusus untuk mining, jangan wallet utama.

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv build-essential
```

### macOS (Homebrew)
```bash
brew install python git
```

### Windows
Gunakan **WSL2** (Ubuntu) — lebih mudah. Atau install Python 3 dari python.org dan ikuti
langkah Windows yang setara (gunakan PowerShell, ganti `source venv/bin/activate`
dengan `venv\Scripts\Activate.ps1`).

---

## 2. Clone repo + setup

```bash
git clone https://github.com/deniginsb/pfft-miner.git
cd pfft-miner
# kalau pakai branch CPU yang ini:
# git fetch origin <NAMA_BRANCH> && git checkout <NAMA_BRANCH>

bash setup_cpu.sh
```

`setup_cpu.sh` akan:
- Bikin virtual env di `./venv`
- Install `web3` + `pycryptodome` (CPU saja, tanpa PyCUDA biar cepat)
- Copy `.env.example` → `.env` kalau belum ada
- Kasih tahu jumlah core CPU yang terdeteksi + saran nilai `WORKERS`

---

## 3. Isi `.env`

```bash
nano .env
```

Yang **wajib** diisi:

```bash
PRIVATE_KEY=0xabc...                       # private key wallet kamu (hex)
ETH_RPC=https://eth-mainnet.g.alchemy.com/v2/<API_KEY>   # pakai RPC kamu sendiri
```

**Penting tentang RPC**: jangan pakai RPC publik (`ethereum-rpc.publicnode.com`) terus-menerus —
dia rate-limit dan bakal bikin error `429 Too Many Requests`. Daftar **gratis** di:
- [Alchemy](https://www.alchemy.com/) — paling generous, 300M compute units/bulan
- [Infura](https://www.infura.io/) — 100k req/hari
- [QuickNode](https://www.quicknode.com/)
- [Ankr](https://www.ankr.com/rpc/)

Save di nano: `Ctrl+O`, `Enter`, `Ctrl+X`.

Lalu kunci permission file `.env`:
```bash
chmod 600 .env
```

---

## 4. Tuning Optimal (CPU)

Buka `.env`, uncomment baris yang ingin kamu ubah. Rekomendasi:

### a. Jumlah worker

Cek jumlah core CPU:
```bash
nproc                              # Linux/WSL
sysctl -n hw.ncpu                  # macOS
```

Lalu set:
```ini
# Mesin kamu juga dipakai buat hal lain (browsing dll):
WORKERS=<cores - 1>

# VPS / mesin dedikasi cuma untuk mining:
WORKERS=<cores>
```

Contoh: CPU 8 core → `WORKERS=7` (atau 8 kalau dedikasi).

**Hyper-threading**: kalau CPU kamu HT (mis. 8 core / 16 thread), coba dulu
`WORKERS=8` (physical cores) — biasanya hashrate cuma naik ~10-15% kalau pakai 16.

### b. Gas strategy (penting buat hemat ETH)

Default = pakai `gasPrice` rekomendasi node (legacy, kadang overpay).

Untuk **lebih hemat** dan TX cepat masuk block, pakai EIP-1559:

1. Cek base fee mainnet sekarang di https://etherscan.io/gastracker
2. Set:
   ```ini
   # Misal base fee 1.5 gwei, tip 1 gwei → cap aman = (1.5 * 2) + 1 ≈ 4 gwei
   MAX_FEE_GWEI=5
   MAX_PRIORITY_FEE_GWEI=1
   ```
3. Kalau base fee naik, miner masih akan bayar **base fee + tip aktual**, dengan cap di `MAX_FEE_GWEI`.

### c. Cooldown antar round

```ini
# Public RPC: minimal 5s biar tidak kena rate limit
PAUSE_BETWEEN_ROUNDS=5

# RPC dedikasi kamu sendiri (Alchemy/Infura paid): bisa 1 atau 0
PAUSE_BETWEEN_ROUNDS=1
```

---

## 5. Jalankan

### Mode foreground (terlihat di terminal)
```bash
./run_cpu.sh
```

### Mode tmux (tetap jalan setelah SSH ditutup — VPS)
```bash
sudo apt install -y tmux           # kalau belum
./run_cpu.sh --tmux
# Detach: Ctrl+B lalu D
# Attach lagi: tmux attach -t pfft-cpu
```

### Mode systemd (auto-restart, VPS)
Lihat file `pfft-miner.service` — edit `User=` dan `WorkingDirectory=` sesuai path kamu, lalu:
```bash
sudo cp pfft-miner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pfft-miner
journalctl -u pfft-miner -f
```

---

## 6. Apa yang akan kamu lihat

```
================================================================
  PFFT Miner Bot - CPU multi-process
  Contract:        0xEFAd2Eab7172dDEbE5Ce7a41f5Ddf8fCcE4Ca0CB
  RPC:             https://eth-mainnet.g.alchemy.com/v2/...
  Workers:         7 (cpus detected: 8)
  Gas limit:       200000
  Gas strategy:    EIP-1559 maxFee=5.0 gwei tip=1.0 gwei
  Round cooldown:  5s
================================================================
Connected | block #21438291
Wallet: 0x...
ETH balance: 0.012340

Contract status:
  Supply:          1,234,567 / 21,000,000 PFFT (5.9%)
  Next mint:  ~1,000.00 PFFT
  Difficulty: 6 hex zeros (24-bit)
  Wallet:     0.00 / 10,000 PFFT minted | bal 0.00

----------------------------------------------------------------
  Round #1
----------------------------------------------------------------
  Supply: 1,234,567 (5.9%) | Next: ~1,000.00 PFFT | Diff: 24-bit
  Mining (24-bit, 7 workers)...
  mining:      12,345,678 H | avg  3,123,456 H/s | now  3,200,123 H/s | x7 |   4s
  FOUND nonce=87654321 (worker 3) | 15,234,567 H | 4.9s | 3,108,074 H/s avg
  TX: https://etherscan.io/tx/0x...
  MINT OK | block 21438300 | gas 89234
  +1,000.00 PFFT | session total: 1,000.00 PFFT in 1 mints
  PFFT balance: 1,000.00
  Session: 1 mints | 1,000.00 PFFT | 0.1 min
  Cooldown 5s...
```

---

## 7. Troubleshooting

| Gejala | Solusi |
|---|---|
| `ImportError: No module named Crypto` | `source venv/bin/activate && pip install pycryptodome` |
| `Cannot connect to RPC` | RPC URL salah / down. Test: `curl -X POST $ETH_RPC -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' -H "Content-Type: application/json"` |
| `429 Too Many Requests` | Pakai RPC pribadi (Alchemy/Infura), naikkan `PAUSE_BETWEEN_ROUNDS`. |
| `Nonce invalid on-chain (supply moved?)` | Normal — challenge berubah saat ada minter lain. Miner otomatis re-mine. |
| `REVERTED \| gas <small>` | Gas habis / wallet cap tercapai / nonce stale. Cek `wallet_minted` di log. |
| TX stuck pending | Naikkan `MAX_PRIORITY_FEE_GWEI` (mis. dari 1 → 2 gwei). |
| Hashrate jauh di bawah expected | Cek `htop` — pastikan semua core busy. Kalau cuma 1 core, kemungkinan `WORKERS=1`. |

---

## 8. Estimasi Hashrate CPU (referensi kasar)

| CPU | Cores/Threads | Hashrate (per `WORKERS=cores`) |
|---|---|---|
| Intel i5-10400 | 6c/12t | ~3-4 MH/s |
| Intel i7-12700 | 12c/20t | ~7-9 MH/s |
| AMD Ryzen 5 5600X | 6c/12t | ~4-5 MH/s |
| AMD Ryzen 9 5950X | 16c/32t | ~12-15 MH/s |
| AMD EPYC 7763 | 64c/128t | ~40-60 MH/s |
| Apple M1/M2 | 8c | ~5-7 MH/s |

> Angka di atas adalah **estimasi**, real number tergantung freq, cache, dan
> versi pycryptodome. Lihat baris `avg ... H/s` di output miner buat nilai
> aktual kamu.

**Difficulty saat ini**: 24-bit (~16 juta hash per solve). Di mesin 5 MH/s,
1 mint ≈ 3 detik mining + gas tx. Kalau difficulty naik ke 40-bit (akhir
supply), butuh ~1 triliun hash per solve = berhari-hari per mint di CPU.
Pada titik itu, switch ke GPU (`pfft_gpu_miner.py`) atau berhenti.

---

## 9. Keamanan singkat

- `.env` sudah masuk `.gitignore`. **Jangan pernah commit** file `.env`.
- `chmod 600 .env` agar user lain di mesin tidak bisa baca.
- Pakai wallet **dedicated** untuk mining, bukan wallet utama kamu.
- Jangan pernah jalankan miner pihak ketiga yang **tidak kamu audit**. Buka
  `pfft_miner.py` dan baca sendiri — script ini tidak mengirim private key
  kemana-mana selain ke RPC kamu untuk sign tx lokal.
