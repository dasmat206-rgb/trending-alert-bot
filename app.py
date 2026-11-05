import requests
from flask import Flask, request

app = Flask(__name__)

# Aapke credentials
TELEGRAM_BOT_TOKEN = "8010299634:AAFZKag72T7vZugraRnLaddV_GEFhR6Wsjo"
TELEGRAM_CHAT_ID = "840994347"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Error sending message:", e)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True) or {}
    
    setup_name = data.get("setup", "Core Setup")
    level = data.get("level", "Predefined Level")
    alert_text = data.get("message", "Alert Triggered!")
    
    formatted_msg = (
        f"🚨 *ALGO SIGNAL TRIGGERED*\n\n"
        f"🎯 *Setup:* {setup_name}\n"
        f"📍 *Level:* {level}\n"
        f"📊 *D    send_telegram_alert(formatted_ms    return {
