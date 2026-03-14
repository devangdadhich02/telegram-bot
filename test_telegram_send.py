"""
One-time test: send a message to Telegram and print the API response.
Run this ON THE SERVER (where the bot runs) to verify token + chat_id.
Usage: python test_telegram_send.py
"""
import requests
import config

def main():
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    print("Using TELEGRAM_CHAT_ID:", repr(chat_id))
    print("Using TELEGRAM_BOT_TOKEN:", (token[:15] + "..." if token else "NOT SET"))
    if not token or not chat_id:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "Test from server – if you see this, Telegram config is correct.",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Telegram API status:", r.status_code)
        print("Telegram API body:", r.text[:500])
        if r.status_code == 200:
            data = r.json()
            ok = data.get("ok")
            result = data.get("result", {})
            dest_chat = result.get("chat", {})
            print("OK:", ok, "| Message sent to chat:", dest_chat.get("id"), dest_chat.get("type"), dest_chat.get("title", dest_chat.get("username", "")))
        else:
            print("FAILED – check token and chat_id. For private chat use Id from @userinfobot.")
    except Exception as e:
        print("Request error:", e)

if __name__ == "__main__":
    main()
