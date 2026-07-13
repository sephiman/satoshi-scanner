# 🧠 Satoshi Scanner

> A [**Sephilabs**](https://github.com/sephiman) project · Licensed under [AGPL-3.0](LICENSE)

An educational Bitcoin tool that demonstrates how Bitcoin private keys, public keys, and addresses are generated. It continuously scans randomly generated keys and checks whether any of their addresses hold BTC. On a hit it records the wallet to disk and sends a Telegram alert.

---

## 🔍 What does it do?

- Generates random private keys (secure entropy via `coincurve` / libsecp256k1).
- Derives **several address forms per key** — one private key maps to multiple addresses depending on public-key encoding and script type:

  | Type          | Looks like | Derivation                                    |
  |---------------|------------|-----------------------------------------------|
  | `p2pkh_u`     | `1...`     | legacy, uncompressed public key               |
  | `p2pkh_c`     | `1...`     | legacy, compressed public key                 |
  | `p2sh_p2wpkh` | `3...`     | nested segwit (BIP49)                         |
  | `p2wpkh`      | `bc1q...`  | native segwit (BIP84)                         |
  | `p2tr`        | `bc1p...`  | taproot key-path (BIP86, BIP341 tweak)        |

- Checks every derived address against one of two backends (see [Check modes](#-check-modes)).
- On a non-zero balance: appends the wallet (key, address, balance) to an on-disk JSONL record **before** alerting, then sends a Telegram alert with retries.

---

## 🧭 Check modes

Set `CHECK_MODE` in your `.env`:

| Mode         | How it works                                                                                                                                                  | Pros                                                | Cons                                                       |
|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|------------------------------------------------------------|
| `live`       | Calls `https://blockstream.info/api/address/{addr}` for each derived address (one key per iteration).                                                        | No setup, always up-to-date.                        | Bound to public-API rate limits (~1 req/sec).              |
| `database`   | Generates `BATCH_SIZE` keys per iteration and checks **all** their addresses against a local Postgres table in a single query. Only on a hit does it verify via Blockstream. | Thousands of addresses per query, no rate-limit risk. | Requires Postgres and a ~1.7 GB nightly dump load (once).  |

`live` is the default (no DB needed).

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
```

| Variable                | Description                                                                        | Default                              |
|-------------------------|------------------------------------------------------------------------------------|--------------------------------------|
| `TELEGRAM_TOKEN`        | Telegram bot token                                                                 | —                                    |
| `TELEGRAM_CHAT_ID`      | Chat ID to receive alerts                                                          | —                                    |
| `CHECK_MODE`            | `live` or `database`                                                               | `live`                               |
| `SCAN_INTERVAL`         | Seconds between scan iterations                                                    | `1.0`                                |
| `ADDRESS_TYPES`         | Comma-separated address forms to derive per key (see table above)                  | all five                             |
| `BATCH_SIZE`            | Keys generated per iteration in `database` mode (`live` always uses 1)             | `1000`                               |
| `FOUND_WALLETS_FILE`    | JSONL file where found wallets are appended before alerting                        | `data/found_wallets.jsonl`           |
| `LOG_LEVEL`             | Python logging level (`DEBUG`, `INFO`, `WARNING`, …)                               | `INFO`                               |
| `POSTGRES_HOST`         | Postgres host (only used in `database` mode)                                       | `postgresdb`                         |
| `POSTGRES_PORT`         | Postgres port                                                                      | `5432`                               |
| `POSTGRES_USER`         | Postgres user                                                                      | —                                    |
| `POSTGRES_PASSWORD`     | Postgres password                                                                  | —                                    |
| `POSTGRES_DB`           | Postgres database name                                                             | —                                    |
| `FUNDED_ADDRESSES_URL`  | Override for the dump URL                                                          | loyce.club LATEST dump               |
| `DUMP_MAX_AGE_DAYS`     | Re-download the dump when older than this many days (`0` disables)                 | `0`                                  |
| `METRICS_PORT`          | Port exposing Prometheus `/metrics`                                                | `8000`                               |

> ⚠️ In `live` mode each address type costs one Blockstream call per key, so with all five types enabled you make 5 calls per iteration. Trim `ADDRESS_TYPES` or raise `SCAN_INTERVAL` if you hit rate limits (the scanner backs off automatically on 429s).

---

## 🐳 Run with Docker Compose

The scanner joins the shared `all_dockers` external network so it can reach the homelab Postgres container by hostname `postgresdb`. Create it once per host if you haven't already:

```bash
docker network create all_dockers
```

Then:

```bash
docker compose up --build -d
docker compose logs -f scanner
```

The container runs as a non-root user, answers Docker health checks via the metrics endpoint, and shuts down gracefully on `docker stop`. Found wallets are kept on the `scanner_data` named volume. CPU usage is hard-capped at **0.5 cores** (`cpus:` in `docker-compose.yml`) so the scanner can never hog the host — raise it temporarily if the initial dump load feels slow.

---

## 💾 Found wallets

A hit is the one event this service exists for, so it is persisted before anything else can fail: each found wallet is appended as one JSON line (timestamp, address, type, balance, private/public keys) to `FOUND_WALLETS_FILE` on the `scanner_data` volume, and only then alerted via Telegram (with up to 5 retries and exponential backoff). Inspect the record with:

```bash
docker exec satoshi-scanner cat data/found_wallets.jsonl
```

---

## 🗄️ Database mode setup

### 1. Have Postgres running

The scanner expects a Postgres instance on the `all_dockers` network. The companion stack at `IdeaProjects/homelab/postgres` provides Postgres 17 + pgAdmin and exposes the hostname `postgresdb` on the shared network. Bring it up first.

### 2. Provision database and credentials

Create a dedicated database and user for the scanner. From the host (using `psql` inside the postgres container):

```bash
docker exec -it postgresdb psql -U <admin-user> -d postgres
```

Inside the `psql` prompt:

```sql
CREATE USER scanner WITH PASSWORD 'changeme';
CREATE DATABASE satoshi_scanner OWNER scanner;
GRANT ALL PRIVILEGES ON DATABASE satoshi_scanner TO scanner;
```

> You can also reuse an existing user/database — just point the env vars at them. A dedicated user is recommended because the table grows to a few GB.

### 3. Schema

The scanner creates its schema automatically at startup:

```sql
CREATE TABLE IF NOT EXISTS funded_addresses (
    address TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS scanner_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

`funded_addresses` is the lookup set (B-tree primary key, O(log n) membership); `scanner_meta` tracks when the dump was last loaded.

### 4. Set scanner env vars

In the scanner's `.env`:

```env
CHECK_MODE=database
POSTGRES_HOST=postgresdb
POSTGRES_PORT=5432
POSTGRES_USER=scanner
POSTGRES_PASSWORD=changeme
POSTGRES_DB=satoshi_scanner
```

### 5. First start

On first start the scanner:

1. Connects to Postgres and ensures the schema exists.
2. Checks whether `funded_addresses` is empty.
3. **If empty:** streams the latest dump from `addresses.loyce.club` (~500 MB gzipped, ~50 M addresses) and bulk-loads it via Postgres `COPY`. Progress is logged every 1 M rows. Expect 5–15 minutes on a homelab DB.
4. **If non-empty:** skips the download entirely and starts scanning immediately.

### 6. Keeping the dataset fresh

Set `DUMP_MAX_AGE_DAYS` (e.g. `30`) and the scanner re-downloads the dump automatically once the loaded copy is older than that. The reload streams into a staging table and swaps it in atomically, so lookups keep working off the old data until the new set is fully loaded. With the default `0`, the dataset is loaded once and only refreshed manually:

```sql
TRUNCATE funded_addresses;
```

…then restart the scanner.

### 7. Lookup behaviour

Each iteration generates `BATCH_SIZE` keys, derives all configured address forms, and checks the whole batch with **one** indexed `ANY()` query. Only on a hit does the scanner fall back to Blockstream to fetch the current balance — DB membership is treated as a pre-filter, not as proof that the wallet still has funds today.

> Reminder: even at millions of addresses/sec, hitting a funded private key remains astronomically improbable. The 2¹⁶⁰ keyspace doesn't care how fast you go.

---

## 📊 Metrics & Grafana dashboard

The scanner exposes Prometheus metrics on `:8000/metrics`. The companion homelab stack ([`sephiman/homelab`](https://github.com/sephiman/homelab/tree/main/monitoring)) auto-discovers any container on the `all_dockers` network that carries these labels (already set in `docker-compose.yml`):

```yaml
labels:
  prometheus.scrape: "true"
  prometheus.port: "8000"
```

Once both stacks are running, Grafana loads the dashboard **Homelab → Satoshi Scanner** automatically (file: [`monitoring/grafana/dashboards/satoshi-scanner.json`](https://github.com/sephiman/homelab/blob/main/monitoring/grafana/dashboards/satoshi-scanner.json)).

### Exposed metrics

| Metric                                    | Type      | Description                                                                                   |
|-------------------------------------------|-----------|-----------------------------------------------------------------------------------------------|
| `satoshi_keys_generated_total`            | Counter   | Private keys generated.                                                                       |
| `satoshi_addresses_generated_total`       | Counter   | Addresses derived and scanned (several per key).                                              |
| `satoshi_addresses_checked_total`         | Counter   | Address checks, labelled by `mode` (`live`/`database`) and `result` (`zero`/`hit`).           |
| `satoshi_wallets_found_total`             | Counter   | Wallets with non-zero balance found. Expected to stay at 0.                                   |
| `satoshi_found_persist_errors_total`      | Counter   | Failures writing a found wallet to the on-disk record.                                        |
| `satoshi_scan_errors_total`               | Counter   | Scan iterations that raised an unexpected error and were skipped (the loop keeps running).    |
| `satoshi_last_check_timestamp`            | Gauge     | Unix timestamp of the last completed check (use `time() - …` for staleness).                  |
| `satoshi_blockstream_request_seconds`     | Histogram | Latency of Blockstream API calls.                                                             |
| `satoshi_blockstream_requests_total`      | Counter   | Blockstream calls by `outcome`: `success` / `rate_limited` / `http_error` / `network_error` / `skipped_cooldown`. |
| `satoshi_blockstream_cooldown_active`     | Gauge     | `1` while the 429 cooldown is in effect, `0` otherwise.                                       |
| `satoshi_blockstream_backoff_seconds`     | Gauge     | Current cooldown window (doubles on 429, resets on success).                                  |
| `satoshi_db_lookups_total`                | Counter   | `funded_addresses` lookups by `result` (`hit`/`miss`).                                        |
| `satoshi_db_lookup_seconds`               | Histogram | Latency of `funded_addresses` lookups (one observation per batch).                            |
| `satoshi_db_funded_addresses_rows`        | Gauge     | Estimated row count of `funded_addresses` (sampled at startup and after dump load).           |
| `satoshi_dump_loaded_timestamp`           | Gauge     | Unix timestamp of the last funded-address dump load.                                          |
| `satoshi_telegram_sent_total`             | Counter   | Telegram alerts successfully sent.                                                            |
| `satoshi_telegram_send_errors_total`      | Counter   | Telegram `sendMessage` errors (including retried attempts).                                   |
| `satoshi_scan_info{mode}`                 | Gauge     | Always `1`; carries the scanner's check-mode as a label.                                      |

Standard `process_*` metrics (RSS memory, CPU seconds, FDs, GC) are exposed automatically by `prometheus_client`.

---

## 🧪 Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`). The runtime targets **Python 3.13** (the Docker base image); coincurve does not yet publish wheels for 3.14.

```bash
uv sync            # creates .venv with runtime + dev dependencies
```

Run the checks:

```bash
uv run ruff check .                  # lint
uv run mypy                          # type-check
uv run pytest -m "not integration"   # fast unit tests
uv run pytest                        # full suite (integration tests need Docker)
```

The integration tests spin up a throwaway Postgres via [testcontainers](https://testcontainers.com/); they're skipped automatically when Docker isn't reachable.

CI (`.github/workflows/ci.yml`) runs lint, mypy, the full test suite with a coverage gate, a Docker build with a Trivy vulnerability scan, and publishes the image to GHCR on pushes to `main`. Dependabot keeps Python packages, GitHub Actions, and the Docker base image up to date.

---

## 🛑 Disclaimer

📌 This project is for **educational purposes only** and does not attempt to brute-force real keys. Accessing wallets that do not belong to you may be illegal.

---

## 📜 License

Copyright © 2024–2026 Sephilabs.

Satoshi Scanner is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General Public License v3.0** as published by the Free Software Foundation. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [`LICENSE`](LICENSE) file for the full text.

Because this is an AGPL-licensed network application, if you run a modified version and let users interact with it over a network, you must also offer them the corresponding source code.
