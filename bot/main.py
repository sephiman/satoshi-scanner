import time

from generator import generate_random_wallet
from scanner import check_balance_blockstream
from telegram import send_to_telegram

print("🚀 Starting BTC address scanner...")
while True:
    priv, pub, addr = generate_random_wallet()
    balance = check_balance_blockstream(addr)

    print(f"Scanned Address: {addr}")
    print(f"Balance: {balance} BTC")
    print(f"Private Key: {priv}")
    print(f"Public Key: {pub}")
    print("-" * 60)

    if balance > 0:
        print("🎯 Wallet with balance found!")
        msg = (
            f"🎯 *Wallet Found!*\n"
            f"*Address:* `{addr}`\n"
            f"[🔍 View on Blockstream](https://blockstream.info/address/{addr})\n"
            f"*Balance:* `{balance} BTC`\n"
            f"*Public Key:* `{pub}`\n"
            f"*Private Key:* `{priv}`"
        )
        send_to_telegram(msg)

    time.sleep(1)
