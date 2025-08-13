import requests

BOT_TOKEN = "8367254953:AAESxN8LQFNDkjFxUIRUJ5vxoP-dU5sjqe4"
CHAT_ID = "@FPL_EDITS"
MESSAGE = "Hello! This is my Premier League bot ⚽"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": MESSAGE
}

requests.post(url, data=payload)
print("Message sent!")
