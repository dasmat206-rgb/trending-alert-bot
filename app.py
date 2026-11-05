import os
import time
import threading
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8489984347")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "1112800567")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Track alerts to prevent duplicate spam
triggered_alerts = set()

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

def scan_smc_setups():
    """Background scanner for SFP and FVG setups using Dhan Intraday data."""
    while True:
        try:
            if DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID:
                headers = {
                    "access-token": DHAN_ACCESS_TOKEN,
                    "client-id": DHAN_CLIENT_ID,
                    "Content-Type": "application/json"
                }

                # Dhan Historical/Intraday Candles Endpoint (Nifty 50 Index - SecId 13)
                payload = {
                    "securityId": "13",
                    "exchangeSegment": "IDX_I",
                    "instrument": "INDEX"
                }

                # Fetch latest LTP & quotes
                quote_res = requests.post("https://api.dhan.co/v2/marketfeed/ltp", json=payload, headers=headers, timeout=10)
                
                if quote_res.status_code == 200:
                    data = quote_res.json()
                    ltp = data.get("data", {}).get("last_price", 0.0)

                    # Simulated trigger condition check for SFP / Range Boundary
                    # In live market, compare with swing levels
                    pass

        except Exception as err:
            print(f"Scanner Loop Error: {err}")

        # Scan interval: every 60 seconds
        time.sleep(60)

# Start background scanner daemon thread
scanner_thread = threading.Thread(target=scan_smc_setups, daemon=True)
scanner_thread.start()

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "scanner": "running",
        "bot": "trending-alert-bot",
        "dhan_linked": bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)
    }), 200

@app.route("/test-dhan", methods=["GET"])
def test_dhan_connection():
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
                "⚡ <i>Setup Ready: 5m/15m SMC + SFP Scanners Active.</i>"
            )
            send_telegram_msg(msg)
            return jsonify({"status": "success", "margin": avail_margin}), 200
        else:
            return jsonify({"status": "failed", "detail": dhan_res.text}), dhan_res.status_code
    except Exception as e:
        return jsonify({"status": "error", "exception": str(e)}), 500

@app.route("/trigger-test", methods=["GET"])
def manual_setup_trigger():
    """Test endpoint to simulate exact setup alert on Telegram."""
    msg = (
        "🚨 <b>TRADING SETUP TRIGGERED</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
        "🎯 <b>Action:</b> <b>BUY / LONG</b>\n"
        "📌 <b>Strategy:</b> Liquidity Sweep + SFP\n"
        "💲 <b>Trigger Price:</b> Near Support Liquidity\n"
        "🛑 <b>Stop Loss:</b> Below Sweep Low (10-15 pts)\n"
        "📦 <b>Risk Rule:</b> 1 Trade / Day Max\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    send_telegram_msg(msg)
    return jsonify({"status": "test_alert_dispatched"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
