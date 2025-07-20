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

| Variable           | Description                  |
|--------------------|------------------------------|
| `TELEGRAM_TOKEN`   | Your Telegram bot token      |
| `TELEGRAM_CHAT_ID` | Chat ID to receive alerts    |

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

## 🛑 Disclaimer
📌 This project is for **educational purposes only** and does not attempt to brute-force real keys.
This tool is not intended for misuse. Accessing wallets that do not belong to you may be illegal.