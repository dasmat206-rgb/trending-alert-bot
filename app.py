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
    while True:
        try:
            candle_data = fetch_dhan_intraday_candles()

            if candle_data and "close" in candle_data and len(candle_data["close"]) >= 8:
                closes = candle_data["close"]
                highs = candle_data["high"]
                lows = candle_data["low"]
                opens = candle_data["open"]
                volumes = candle_data.get("volume", [100] * len(closes))

                i = len(closes) - 1
                candle_id = f"{i}_{highs[i]}_{lows[i]}"

                if candle_id not in sent_alerts:
                    # 1. SETUP: Liquidity Sweep + SFP
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

                    # 3. SETUP: FRVP POC
                    recent_vol = volumes[-12:]
                    max_vol_idx = volumes.index(max(recent_vol))
                    poc_price = (highs[max_vol_idx] + lows[max_vol_idx]) / 2.0
                    val_level = min(lows[-12:]) + (poc_price - min(lows[-12:])) * 0.3
                    vah_level = max(highs[-12:]) - (max(highs[-12:]) - poc_price) * 0.3

                    if abs(closes[i] - poc_price) <= 6.0:
                        send_telegram_msg(
                            "🚨 <b>SETUP 3: FRVP POC LEVEL REACTION</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            f"📌 <b>Exact POC Level:</b> {poc_price:.2f}\n"
                            f"📐 <b>Value Area:</b> {val_level:.2f} - {vah_level:.2f}\n"
                            f"💲 <b>Current Level:</b> {closes[i]:.2f}\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        sent_alerts.add(candle_id)

                    # 4. SETUP: CVD Absorption
                    avg_vol = sum(volumes[-10:]) / 10.0
                    body_size = abs(closes[i] - opens[i])
                    if volumes[i] > (1.8 * avg_vol) and body_size < 8:
                        absorb_type = "BULLISH ABSORPTION" if closes[i] > opens[i] else "BEARISH ABSORPTION"
                        send_telegram_msg(
                            f"🚨 <b>SETUP 4: {absorb_type} DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            f"💲 <b>Absorption Level:</b> {closes[i]:.2f}\n"
                            f"📊 <b>Volume:</b> {volumes[i]} (Avg: {int(avg_vol)})\n"
                            f"🎯 <b>Range:</b> {lows[i]:.2f} - {highs[i]:.2f}\n"
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
    data = fetch_dhan_intraday_candles()
    if not data or "close" not in data or len(data["close"]) == 0:
        return jsonify({"status": "failed", "detail": "Dhan historical candles not returned"}), 400

    closes = data["close"]
    highs = data["high"]
    lows = data["low"]
    opens = data["open"]
    total_candles = len(closes)

    # Pick latest closed candle from today
    last_idx = total_candles - 1
    recent_high = max(highs[max(0, last_idx-6):last_idx])
    recent_low = min(lows[max(0, last_idx-6):last_idx])
    
    # Calculate actual Order Block zone from previous candles
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
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Dhan real candles parsed without errors.</i>"
    )
    send_telegram_msg(msg)
    return jsonify({
        "status": "success",
        "candles_analyzed": total_candles,
        "last_close": closes[last_idx]
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
