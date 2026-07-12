# 🧠 Satoshi Scanner

> A [**Sephilabs**](https://github.com/sephiman) project · Licensed under [AGPL-3.0](LICENSE)

An educational Bitcoin tool that demonstrates how Bitcoin private keys, public keys, and legacy addresses (`1...`) are generated. It continuously scans randomly generated addresses and checks whether they hold any BTC. On a hit it sends a Telegram alert.

---

## 🔍 What does it do?

- Generates random private keys (secure entropy via `coincurve` / libsecp256k1).
- Derives the corresponding public key and legacy Bitcoin address.
- Checks the balance against one of two backends (see [Check modes](#-check-modes)).
- On a non-zero balance: logs to the console and sends a Telegram alert with the address, balance, public key, and private key.

---

## 🧭 Check modes

Set `CHECK_MODE` in your `.env`:

| Mode         | How it works                                                                                                                                                                | Pros                                                | Cons                                                       |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|------------------------------------------------------------|
| `live`       | Calls `https://blockstream.info/api/address/{addr}` for each generated address.                                                                                             | No setup, always up-to-date.                        | Bound to public-API rate limits (~1 req/sec).              |
| `database`   | Looks up the address in a local Postgres table of funded addresses. Only on a hit, it verifies via Blockstream to fetch the actual balance.                                 | Millions of addresses/sec, no rate-limit risk.      | Requires Postgres and a ~1.7 GB nightly dump load (once).  |

`live` is the default (no DB needed).

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
```

| Variable                | Description                                                                  | Default                  |
|-------------------------|------------------------------------------------------------------------------|--------------------------|
| `TELEGRAM_TOKEN`        | Telegram bot token                                                           | —                        |
| `TELEGRAM_CHAT_ID`      | Chat ID to receive alerts                                                    | —                        |
| `CHECK_MODE`            | `live` or `database`                                                         | `live`                   |
| `SCAN_INTERVAL`         | Seconds between address generations                                          | `1.0`                    |
| `LOG_LEVEL`             | Python logging level (`DEBUG`, `INFO`, `WARNING`, …)                         | `INFO`                   |
| `POSTGRES_HOST`         | Postgres host (only used in `database` mode)                                 | `postgresdb`             |
| `POSTGRES_PORT`         | Postgres port                                                                | `5432`                   |
| `POSTGRES_USER`         | Postgres user                                                                | —                        |
| `POSTGRES_PASSWORD`     | Postgres password                                                            | —                        |
| `POSTGRES_DB`           | Postgres database name                                                       | —                        |
| `FUNDED_ADDRESSES_URL`  | Override for the dump URL                                                    | loyce.club LATEST dump   |
| `METRICS_PORT`          | Port exposing Prometheus `/metrics`                                          | `8000`                   |

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

### 3. Create the schema

The scanner creates the table automatically at startup, but if you want to provision it ahead of time:

```sql
\c satoshi_scanner

CREATE TABLE IF NOT EXISTS funded_addresses (
    address TEXT PRIMARY KEY
);
```

That's the whole schema — one column, primary key on `address`, B-tree index gives O(log n) lookups.

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

If you want to refresh the dataset later, manually truncate the table and restart the scanner:

```sql
TRUNCATE funded_addresses;
```

### 6. Lookup behaviour

Every generated address is checked against `funded_addresses` with a single primary-key lookup (sub-millisecond). Only on a hit does the scanner fall back to Blockstream to fetch the current balance — so DB membership is treated as a pre-filter, not as proof that the wallet still has funds today.

> Reminder: even at 1 M addresses/sec, hitting a funded private key remains astronomically improbable. The 2¹⁶⁰ keyspace doesn't care how fast you go.

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
| `satoshi_addresses_generated_total`       | Counter   | Bitcoin addresses generated and scanned.                                                      |
| `satoshi_addresses_checked_total`         | Counter   | Address checks, labelled by `mode` (`live`/`database`) and `result` (`zero`/`hit`).           |
| `satoshi_wallets_found_total`             | Counter   | Wallets with non-zero balance found. Expected to stay at 0.                                   |
| `satoshi_scan_errors_total`               | Counter   | Scan iterations that raised an unexpected error and were skipped (the loop keeps running).    |
| `satoshi_last_check_timestamp`            | Gauge     | Unix timestamp of the last completed check (use `time() - …` for staleness).                  |
| `satoshi_blockstream_request_seconds`     | Histogram | Latency of Blockstream API calls.                                                             |
| `satoshi_blockstream_requests_total`      | Counter   | Blockstream calls by `outcome`: `success` / `rate_limited` / `http_error` / `network_error` / `skipped_cooldown`. |
| `satoshi_blockstream_cooldown_active`     | Gauge     | `1` while the 429 cooldown is in effect, `0` otherwise.                                       |
| `satoshi_blockstream_backoff_seconds`     | Gauge     | Current cooldown window (doubles on 429, resets on success).                                  |
| `satoshi_db_lookups_total`                | Counter   | `funded_addresses` lookups by `result` (`hit`/`miss`).                                        |
| `satoshi_db_lookup_seconds`               | Histogram | Latency of `funded_addresses` lookups.                                                        |
| `satoshi_db_funded_addresses_rows`        | Gauge     | Estimated row count of `funded_addresses` (sampled at startup and after dump load).           |
| `satoshi_telegram_sent_total`             | Counter   | Telegram alerts successfully sent.                                                            |
| `satoshi_telegram_send_errors_total`      | Counter   | Telegram `sendMessage` errors.                                                                |
| `satoshi_scan_info{mode}`                 | Gauge     | Always `1`; carries the scanner's check-mode as a label.                                      |

Standard `process_*` metrics (RSS memory, CPU seconds, FDs, GC) are exposed automatically by `prometheus_client`.

---

## 🧪 Development

The runtime targets **Python 3.13** (the Docker base image). coincurve does not yet
publish wheels for 3.14, so stick to 3.13 for a local virtualenv.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the checks:

```bash
ruff check .                     # lint
pytest -m "not integration"      # fast unit tests
pytest                           # full suite (integration tests need Docker)
```

The integration tests spin up a throwaway Postgres via
[testcontainers](https://testcontainers.com/); they're skipped automatically when
Docker isn't reachable. CI (`.github/workflows/ci.yml`) runs lint, the full test
suite, and a Docker build on every push and pull request.

---

## 🛑 Disclaimer

📌 This project is for **educational purposes only** and does not attempt to brute-force real keys. Accessing wallets that do not belong to you may be illegal.

---

## 📜 License

Copyright © 2024–2026 Sephilabs.

Satoshi Scanner is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General Public License v3.0** as published by the Free Software Foundation. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [`LICENSE`](LICENSE) file for the full text.

Because this is an AGPL-licensed network application, if you run a modified version and let users interact with it over a network, you must also offer them the corresponding source code.
