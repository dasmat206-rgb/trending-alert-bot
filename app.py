import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Credentials configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8489984347")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "1112800567")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

def send_telegram_msg(message: str):
    """Sends HTML formatted message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "bot": "trending-alert-bot",
        "dhan_linked": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)
    }), 200

@app.route("/test-dhan", methods=["GET"])
def test_dhan_connection():
    """Validates Dhan Token and sends alert to Telegram."""
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        return jsonify({"status": "error", "message": "Dhan credentials missing"}), 400

    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }

    try:
        dhan_res = requests.get("https://api.dhan.co/v2/fundlimit", headers=headers, timeout=10)
        if dhan_res.status_code == 200:
            fund_data = dhan_res.json()
            avail_margin = fund_data.get("availMargin", 0.0)

            msg = (
                "🟢 <b>Dhan API Connected Successfully!</b>\n\n"
                f"👤 <b>Client ID:</b> <code>{DHAN_CLIENT_ID}</code>\n"
                f"💰 <b>Available Margin:</b> ₹{avail_margin:,.2f}\n"
                "⚡ <i>Setup Ready: FRVP + CVD Alerts Listening.</i>"
            )
            send_telegram_msg(msg)
            return jsonify({"status": "success", "margin": avail_margin}), 200
        else:
            return jsonify({"status": "failed", "detail": dhan_res.text}), dhan_res.status_code
    except Exception as e:
        return jsonify({"status": "error", "exception": str(e)}), 500

@app.route("/alert", methods=["POST"])
def receive_alert():
    """Receives trading setups and pushes to Telegram."""
    data = request.get_json(silent=True) or {}

    symbol = data.get("symbol", "NIFTY")
    setup = data.get("setup", "FRVP + CVD Absorption")
    price = data.get("price", "Market")
    sl = data.get("sl", "10 pts")
    action = data.get("action", "BUY / LONG")

    formatted_alert = (
        f"🚨 <b>TRADING SETUP TRIGGERED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Instrument:</b> {symbol}\n"
        f"🎯 <b>Action:</b> <b>{action}</b>\n"
        f"📌 <b>Strategy:</b> {setup}\n"
        f"💲 <b>Trigger Price:</b> {price}\n"
        f"🛑 <b>Stop Loss:</b> {sl}\n"
        f"📦 <b>Position Sizing:</b> 1 Lot (Risk Rules Applied)\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    send_telegram_msg(formatted_alert)
    return jsonify({"status": "alert_dispatched"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
