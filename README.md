# 🧠 Satoshi Scanner

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

## 🛑 Disclaimer

📌 This project is for **educational purposes only** and does not attempt to brute-force real keys. Accessing wallets that do not belong to you may be illegal.
