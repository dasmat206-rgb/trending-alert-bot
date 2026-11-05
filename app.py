import os
import time
import threading
from datetime import datetime, date
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8489984347")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "1112800567")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

sent_alerts = set()

def send_telegram_msg(message: str):
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

def fetch_dhan_intraday_candles():
    """Fetches intraday historical candles with Dhan v2 schema."""
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        return None, "Missing credentials"

    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    
    # NIFTY 50 Index
    today_str = date.today().strftime("%Y-%m-%d")
    payload = {
        "securityId": "13",
        "exchangeSegment": "IDX_I",
        "instrument": "INDEX",
        "interval": "5",
        "fromDate": f"{today_str} 09:15:00",
        "toDate": f"{today_str} 15:30:00"
    }

    try:
        res = requests.post("https://api.dhan.co/v2/charts/intraday", json=payload, headers=headers, timeout=10)
        res_json = res.json()
        if res.status_code == 200:
            # Dhan returns candles under "data" or root keys
            return res_json.get("data", res_json), None
        else:
            return None, res_json
    except Exception as err:
        return None, str(err)

def analyze_market_setups():
    while True:
        try:
            candle_data, err = fetch_dhan_intraday_candles()

            if candle_data and "close" in candle_data and len(candle_data["close"]) >= 8:
                closes = candle_data["close"]
                highs = candle_data["high"]
                lows = candle_data["low"]
                opens = candle_data["open"]
                volumes = candle_data.get("volume", [100] * len(closes))

                i = len(closes) - 1
                candle_id = f"{i}_{highs[i]}_{lows[i]}"

                if candle_id not in sent_alerts:
                    # 1. SETUP: SFP
                    prev_swing_high = max(highs[max(0, i-6):i])
                    prev_swing_low = min(lows[max(0, i-6):i])

                    if highs[i] > prev_swing_high and closes[i] < prev_swing_high:
                        send_telegram_msg(
                            "🚨 <b>SETUP 1: BEARISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>SELL / SHORT</b>\n"
                            f"📌 <b>Swept Level:</b> {prev_swing_high:.2f}\n"
                            f"💲 <b>Trigger Close:</b> {closes[i]:.2f}\n"
                            f"🛑 <b>Exact SL:</b> {highs[i] + 4.00:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        sent_alerts.add(candle_id)

                    elif lows[i] < prev_swing_low and closes[i] > prev_swing_low:
                        send_telegram_msg(
                            "🚨 <b>SETUP 1: BULLISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>BUY / LONG</b>\n"
                            f"📌 <b>Swept Level:</b> {prev_swing_low:.2f}\n"
                            f"💲 <b>Trigger Close:</b> {closes[i]:.2f}\n"
                            f"🛑 <b>Exact SL:</b> {lows[i] - 4.00:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        sent_alerts.add(candle_id)

                    # 2. SETUP: OB + FVG
                    if lows[i] > highs[i-2] and closes[i-1] > opens[i-1]:
                        ob_low = min(lows[i-2], opens[i-2])
                        ob_high = max(highs[i-2], closes[i-2])
                        send_telegram_msg(
                            "🚨 <b>SETUP 2: BULLISH OB + FVG ZONE</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>BUY / DEMAND</b>\n"
                            f"📦 <b>Order Block (OB):</b> {ob_low:.2f} - {ob_high:.2f}\n"
                            f"🎯 <b>FVG Gap:</b> {highs[i-2]:.2f} - {lows[i]:.2f}\n"
                            f"🛑 <b>Exact SL:</b> {ob_low - 5.00:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        sent_alerts.add(candle_id)

        except Exception as e:
            print(f"Scanner Logic Error: {e}")

        time.sleep(60)

scanner_thread = threading.Thread(target=analyze_market_setups, daemon=True)
scanner_thread.start()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"bot": "active"}), 200

# TEST AAJ KA REAL CHART DATA
@app.route("/test-today-data", methods=["GET"])
def test_today_data():
    data, err_detail = fetch_dhan_intraday_candles()
    
    # Debug: Agar Dhan API ne direct error bheja toh exact reason screen par dikhega
    if not data or "close" not in data or len(data.get("close", [])) == 0:
        return jsonify({
            "status": "failed",
            "dhan_response": err_detail,
            "solution": "Dhan historical charts requires live session or valid date filter"
        }), 400

    closes = data["close"]
    highs = data["high"]
    lows = data["low"]
    opens = data["open"]
    total_candles = len(closes)

    last_idx = total_candles - 1
    recent_high = max(highs[max(0, last_idx-6):last_idx])
    recent_low = min(lows[max(0, last_idx-6):last_idx])
    ob_low = min(lows[last_idx-2], opens[last_idx-2])
    ob_high = max(highs[last_idx-2], closes[last_idx-2])

    msg = (
        "📈 <b>AAJ KA REAL CHART SCAN TEST</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Instrument:</b> NIFTY 50 (5m Data)\n"
        f"🕒 <b>Total Candles Today:</b> {total_candles}\n"
        f"💲 <b>Market Close Level:</b> {closes[last_idx]:.2f}\n"
        f"📌 <b>Recent Swing High:</b> {recent_high:.2f}\n"
        f"📌 <b>Recent Swing Low:</b> {recent_low:.2f}\n"
        f"📦 <b>Nearest OB Zone:</b> {ob_low:.2f} - {ob_high:.2f}\n"
        f"🛑 <b>Calculated SL:</b> {ob_low - 5.00:.2f}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    send_telegram_msg(msg)
    return jsonify({
        "status": "success",
        "candles_analyzed": total_candles,
        "last_close": closes[last_idx]
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
