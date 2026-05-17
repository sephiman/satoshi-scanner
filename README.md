# 🧠 Satoshi Scanner

An educational Bitcoin tool that demonstrates how Bitcoin private keys, public keys, and legacy addresses (`1...`) are generated. It continuously scans randomly generated addresses and checks if they hold any BTC. If a wallet with funds is found, it sends a detailed Telegram alert.

---

## 🔍 What does it do?

- Generates random private keys (using secure entropy)  
- Derives the corresponding public key and legacy Bitcoin address  
- Checks the balance of the address using Blockstream's API  
- If the address has any BTC:
  - Logs the result to the console
  - Sends a Telegram alert with the address, balance, public key, and private key

---

## ⚙️ Configuration

The bot uses the following environment variables:

| Variable           | Description                                                  | Default |
|--------------------|--------------------------------------------------------------|---------|
| `TELEGRAM_TOKEN`   | Your Telegram bot token                                      | —       |
| `TELEGRAM_CHAT_ID` | Chat ID to receive alerts                                    | —       |
| `SCAN_INTERVAL`    | Seconds between address generations (free-API friendly)      | `1.0`   |
| `LOG_LEVEL`        | Python logging level (`DEBUG`, `INFO`, `WARNING`, ...)       | `INFO`  |

Example `.env`:

```env
TELEGRAM_TOKEN=123456:ABCDEF...
TELEGRAM_CHAT_ID=12345678
```

---

## 🐳 Run with Docker Compose

1. Make sure you have a `.env` file with your credentials:

```env
TELEGRAM_TOKEN=123456:ABCDEF...
TELEGRAM_CHAT_ID=12345678
```

2. Then build and start the scanner:

```bash
docker-compose up --build
```

---

---

## 🚀 Future improvement: local bloom-filter scanning

The current loop is bounded by Blockstream's free API rate limit (~1 request/sec). The "right" architecture is to do balance checks **locally** against a known set of funded addresses, eliminating the HTTP call entirely.

**Approach:**

1. Download the nightly dump of all Bitcoin addresses with non-zero balance from [addresses.loyce.club](http://addresses.loyce.club/) (~500 MB compressed, ~1.7 GB uncompressed, ~50 million addresses).
2. Build a bloom filter at startup (FPR ≈ 1e-6 → ~180 MB RAM, sub-microsecond lookups). Optionally persist to disk and mmap it for instant restarts.
3. Generated addresses are checked against the filter first. Only on a (rare) hit, fall back to Blockstream to confirm and fetch the balance.
4. Refresh the dump weekly via cron (staleness is fine — funded addresses don't disappear).

**Impact:**

| Metric           | Current (API-bound) | With bloom filter (CPU-bound) |
|------------------|---------------------|-------------------------------|
| Throughput       | ~1 addr/sec         | >1,000,000 addr/sec           |
| RAM              | ~30 MB              | ~210 MB                       |
| Rate-limit risk  | Constant            | None (1 API call per ~1e6)    |

Suggested new env vars when implementing:

| Variable                  | Description                                  |
|---------------------------|----------------------------------------------|
| `FUNDED_ADDRESSES_FILE`   | Path to the address list (txt or txt.gz)     |
| `BLOOM_FILE`              | Optional path to persisted bloom filter      |
| `BLOOM_FPR`               | Target false-positive rate (default `1e-6`)  |

Candidate libraries: `pybloom-live` (pure Python, simple), `rbloom` (Rust-backed, fast and supports mmap-load), or roll one with `bitarray` + `mmh3`.

> Note: even at 1 M addr/sec, finding a real funded private key remains astronomically improbable. The 2¹⁶⁰ keyspace doesn't care how fast you go.

---

## 🛑 Disclaimer
📌 This project is for **educational purposes only** and does not attempt to brute-force real keys.
This tool is not intended for misuse. Accessing wallets that do not belong to you may be illegal.