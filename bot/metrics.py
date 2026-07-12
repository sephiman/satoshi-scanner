"""
Prometheus metrics for satoshi-scanner.

A homelab Prometheus scrapes containers labeled `prometheus.scrape=true`
on `prometheus.port=8000` (the prometheus_client default endpoint /metrics).
See https://github.com/sephiman/homelab/tree/main/monitoring for the
scrape config + the matching Grafana dashboard.
"""
import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram

import config

KEYS_GENERATED_TOTAL = Counter(
    "satoshi_keys_generated_total",
    "Private keys generated.",
)

ADDRESSES_GENERATED_TOTAL = Counter(
    "satoshi_addresses_generated_total",
    "Bitcoin addresses generated and scanned (several per key).",
)

ADDRESSES_CHECKED_TOTAL = Counter(
    "satoshi_addresses_checked_total",
    "Address balance checks, broken down by mode and outcome.",
    ["mode", "result"],
)

WALLETS_FOUND_TOTAL = Counter(
    "satoshi_wallets_found_total",
    "Wallets with a non-zero balance discovered.",
)

FOUND_PERSIST_ERRORS_TOTAL = Counter(
    "satoshi_found_persist_errors_total",
    "Failures writing a found wallet to the on-disk record.",
)

SCAN_ERRORS_TOTAL = Counter(
    "satoshi_scan_errors_total",
    "Scan iterations that raised an unexpected error and were skipped.",
)

LAST_CHECK_TIMESTAMP = Gauge(
    "satoshi_last_check_timestamp",
    "Unix timestamp of the last completed address check.",
)

BLOCKSTREAM_REQUEST_SECONDS = Histogram(
    "satoshi_blockstream_request_seconds",
    "Latency of Blockstream API calls.",
)

BLOCKSTREAM_REQUESTS_TOTAL = Counter(
    "satoshi_blockstream_requests_total",
    "Blockstream API calls, by outcome.",
    ["outcome"],  # success | rate_limited | http_error | network_error | skipped_cooldown
)

BLOCKSTREAM_COOLDOWN_ACTIVE = Gauge(
    "satoshi_blockstream_cooldown_active",
    "1 if the scanner is currently in a Blockstream rate-limit cooldown window, else 0.",
)

BLOCKSTREAM_BACKOFF_SECONDS = Gauge(
    "satoshi_blockstream_backoff_seconds",
    "Current Blockstream cooldown backoff window (grows on 429, resets on success).",
)

DB_LOOKUPS_TOTAL = Counter(
    "satoshi_db_lookups_total",
    "Lookups against the funded_addresses table.",
    ["result"],  # hit | miss
)

DB_LOOKUP_SECONDS = Histogram(
    "satoshi_db_lookup_seconds",
    "Latency of funded_addresses lookups (one observation per batch).",
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

DB_FUNDED_ADDRESSES_ROWS = Gauge(
    "satoshi_db_funded_addresses_rows",
    "Row count of the funded_addresses table (sampled at startup and after dump load).",
)

DUMP_LOADED_TIMESTAMP = Gauge(
    "satoshi_dump_loaded_timestamp",
    "Unix timestamp of the last funded-address dump load.",
)

TELEGRAM_SENT_TOTAL = Counter(
    "satoshi_telegram_sent_total",
    "Telegram messages successfully sent.",
)

TELEGRAM_SEND_ERRORS_TOTAL = Counter(
    "satoshi_telegram_send_errors_total",
    "Telegram sendMessage errors (including retried attempts).",
)

SCAN_INFO = Gauge(
    "satoshi_scan_info",
    "Static info about the running scanner (value is always 1).",
    ["mode"],
)
SCAN_INFO.labels(mode=config.CHECK_MODE).set(1)


@contextmanager
def time_blockstream_call() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        BLOCKSTREAM_REQUEST_SECONDS.observe(time.perf_counter() - start)


@contextmanager
def time_db_lookup() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        DB_LOOKUP_SECONDS.observe(time.perf_counter() - start)
