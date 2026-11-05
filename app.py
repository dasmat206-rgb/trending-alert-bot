import os
import time
import threading
from datetime import datetime
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8489984347")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "1112800567")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Track dispatched alerts to avoid duplicate spam on same candle
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
    """Fetches intraday 5-minute historical OHLC data from Dhan."""
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        return None

    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    
    # Nifty 50 Index (SecId: 13, Exchange: IDX_I)
    payload = {
        "securityId": "13",
        "exchangeSegment": "IDX_I",
        "instrument": "INDEX",
        "interval": "5"
    }

    try:
        res = requests.post("https://api.dhan.co/v2/charts/intraday", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("data", {})
    except Exception as err:
        print(f"Dhan Fetch Error: {err}")
    return None

def analyze_market_setups():
    """Scans for SFP, FVG, FRVP POC, and Volume Absorption."""
    while True:
        try:
            # Check market hours (IST 09:15 to 15:30)
            now = datetime.utcnow()
            # Dhan live candle check loop
            candle_data = fetch_dhan_intraday_candles()

            if candle_data and "close" in candle_data and len(candle_data["close"]) >= 5:
                closes = candle_data["close"]
                highs = candle_data["high"]
                lows = candle_data["low"]
                opens = candle_data["open"]
                volumes = candle_data.get("volume", [100] * len(closes))

                i = len(closes) - 1  # Latest closed candle
                candle_id = f"{i}_{highs[i]}_{lows[i]}"

                if candle_id not in sent_alerts:
                    # 1. SETUP: Liquidity Sweep + SFP (Swing Failure Pattern)
                    prev_swing_high = max(highs[max(0, i-6):i])
                    prev_swing_low = min(lows[max(0, i-6):i])

                    # Bearish SFP: Swept High, closed below
                    if highs[i] > prev_swing_high and closes[i] < prev_swing_high:
                        msg = (
                            "🚨 <b>SETUP 1: BEARISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>SELL / SHORT</b>\n"
                            f"📌 <b>Swept High:</b> {prev_swing_high}\n"
                            f"💲 <b>Trigger Close:</b> {closes[i]}\n"
                            f"🛑 <b>Stop Loss:</b> {highs[i] + 5}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # Bullish SFP: Swept Low, closed above
                    elif lows[i] < prev_swing_low and closes[i] > prev_swing_low:
                        msg = (
                            "🚨 <b>SETUP 1: BULLISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>BUY / LONG</b>\n"
                            f"📌 <b>Swept Low:</b> {prev_swing_low}\n"
                            f"💲 <b>Trigger Close:</b> {closes[i]}\n"
                            f"🛑 <b>Stop Loss:</b> {lows[i] - 5}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # 2. SETUP: Fair Value Gap (FVG)
                    # Bullish FVG: Low of candle i > High of candle i-2
                    if lows[i] > highs[i-2] and closes[i-1] > opens[i-1]:
                        msg = (
                            "🚨 <b>SETUP 2: BULLISH FVG FORMED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "📌 <b>Strategy:</b> Imbalance / FVG Zone\n"
                            f"🎯 <b>FVG Range:</b> {highs[i-2]} - {lows[i]}\n"
                            "💡 <i>Wait for mitigation/retest for entry.</i>\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # 3. SETUP: FRVP POC Test (Volume-Weighted Mode)
                    max_vol_idx = volumes.index(max(volumes[-10:]))
                    poc_price = (highs[max_vol_idx] + lows[max_vol_idx]) / 2.0

                    if abs(closes[i] - poc_price) <= 5:
                        msg = (
                            "🚨 <b>SETUP 3: FRVP POC LEVEL TEST</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            f"📌 <b>High Volume Node (POC):</b> {poc_price:.2f}\n"
                            f"💲 <b>Current Price:</b> {closes[i]}\n"
                            "🎯 <b>Action:</b> Look for Bounce / Value Area Reaction\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # 4. SETUP: CVD / Volume Absorption
                    avg_vol = sum(volumes[-10:]) / 10.0
                    body_size = abs(closes[i] - opens[i])
                    # High volume with narrow candle body = absorption
                    if volumes[i] > (1.8 * avg_vol) and body_size < 8:
                        msg = (
                            "🚨 <b>SETUP 4: CVD ABSORPTION DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "📌 <b>Signal:</b> High Volume Absorption / Divergence\n"
                            f"💲 <b>Level:</b> {closes[i]}\n"
                            "⚠️ <b>Observation:</b> Institutional orders absorbing movement.\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

        except Exception as e:
            print(f"Scanner Logic Error: {e}")

        # Dhan rate limits respect karne ke liye 60-second wait
        time.sleep(60)

# Start real-time scanner thread
scanner_thread = threading.Thread(target=analyze_market_setups, daemon=True)
scanner_thread.start()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"bot": "active", "scanners": "4_setups_running"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
