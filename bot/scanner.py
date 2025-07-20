import requests


def check_balance_blockstream(addr):
    try:
        r = requests.get(f"https://blockstream.info/api/address/{addr}", timeout=10)
        data = r.json()
        funded = data.get("chain_stats", {}).get("funded_txo_sum", 0)
        spent = data.get("chain_stats", {}).get("spent_txo_sum", 0)
        balance = (funded - spent) / 100_000_000  # en BTC
        return balance
    except Exception as e:
        print(f"[!] Error consultando {addr}: {e}")
        return 0.0
