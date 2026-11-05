from flask import Flask, request
import requests

app = Flask(__name__)

# Aapke credentials
TELEGRAM_BOT_TOKEN = "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo"
TELEGRAM_CHAT_ID = "8489984347"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
        # TradingView se custom message read karna
        alert_text = data.get("message", "Alert Triggered!")
        setup_name = data.get("setup", "Core Setup")
        send_telegram_alert(formatted_msg)
        return {"status": "success"}, 200
    return {"status": "bad request"}, 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
