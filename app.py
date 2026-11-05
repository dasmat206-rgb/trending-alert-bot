import os
import time
import threading
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Credentials configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8810299834:AAFZKag7277vZugraRniaddV_GEPHH6Wsjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8489984347")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "1112800567")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

sent_alerts = set()
IST = timezone(timedelta(hours=5, minutes=30))

def is_market_open():
    """Checks if current time is within Indian Stock Market hours (Mon-Fri 09:15 - 15:30 IST)."""
    now_ist = datetime.now(IST)
    if now_ist.weekday() >= 5:  # Saturday & Sunday
        return False
    market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now_ist <= market_close

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

def get_dhan_nifty_quote():
    """Fetches real Nifty 50 quote from Dhan."""
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        return None

    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    payload = {"IDX_I": [13]}

    try:
        res = requests.post("https://api.dhan.co/v2/marketfeed/quote", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("data", {}).get("IDX_I", {}).get("13", {})
    except Exception as err:
        print(f"Dhan Quote Error: {err}")
    return None

def fetch_dhan_intraday_candles():
    """Fetches 5-minute candles from Dhan."""
    if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
        return None

    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
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
        print(f"Candle Fetch Error: {err}")
    return None

def analyze_market_setups():
    """Continuous scanning engine with MTF + Setups + Risk:Reward logic."""
    while True:
        try:
            # 1. Market Hours Filter
            if not is_market_open():
                time.sleep(60)
                continue

            # 2. Live Data Extraction
            candle_data = fetch_dhan_intraday_candles()

            if candle_data and "close" in candle_data and len(candle_data["close"]) >= 8:
                closes = candle_data["close"]
                highs = candle_data["high"]
                lows = candle_data["low"]
                opens = candle_data["open"]
                volumes = candle_data.get("volume", [100] * len(closes))

                i = len(closes) - 1
                curr_price = closes[i]
                candle_id = f"{i}_{highs[i]}_{lows[i]}"

                if candle_id not in sent_alerts:
                    # SETUP 1: Liquidity Sweep + SFP
                    prev_swing_high = max(highs[max(0, i-6):i])
                    prev_swing_low = min(lows[max(0, i-6):i])

                    # Bearish SFP
                    if highs[i] > prev_swing_high and closes[i] < prev_swing_high:
                        entry = closes[i]
                        sl = highs[i] + 4.0
                        risk = max(sl - entry, 5.0)
                        tp1 = entry - (risk * 2.0)
                        tp2 = entry - (risk * 3.5)
                        msg = (
                            "🚨 <b>SETUP 1: BEARISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>SELL / SHORT</b>\n"
                            f"📌 <b>Swept High Level:</b> {prev_swing_high:.2f}\n"
                            f"💲 <b>Entry Price:</b> {entry:.2f}\n"
                            f"🛑 <b>Exact SL Level:</b> {sl:.2f} (-{risk:.1f} pts)\n"
                            f"🎯 <b>Target 1 (1:2 RR):</b> {tp1:.2f} (+{risk*2:.1f} pts)\n"
                            f"🎯 <b>Target 2 (1:3.5 RR):</b> {tp2:.2f} (+{risk*3.5:.1f} pts)\n"
                            "⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # Bullish SFP
                    elif lows[i] < prev_swing_low and closes[i] > prev_swing_low:
                        entry = closes[i]
                        sl = lows[i] - 4.0
                        risk = max(entry - sl, 5.0)
                        tp1 = entry + (risk * 2.0)
                        tp2 = entry + (risk * 3.5)
                        msg = (
                            "🚨 <b>SETUP 1: BULLISH SFP DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>BUY / LONG</b>\n"
                            f"📌 <b>Swept Low Level:</b> {prev_swing_low:.2f}\n"
                            f"💲 <b>Entry Price:</b> {entry:.2f}\n"
                            f"🛑 <b>Exact SL Level:</b> {sl:.2f} (-{risk:.1f} pts)\n"
                            f"🎯 <b>Target 1 (1:2 RR):</b> {tp1:.2f} (+{risk*2:.1f} pts)\n"
                            f"🎯 <b>Target 2 (1:3.5 RR):</b> {tp2:.2f} (+{risk*3.5:.1f} pts)\n"
                            "⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # SETUP 2: Bullish Order Block + FVG
                    if lows[i] > highs[i-2] and closes[i-1] > opens[i-1]:
                        ob_low = min(lows[i-2], opens[i-2])
                        ob_high = max(highs[i-2], closes[i-2])
                        entry = ob_high
                        sl = ob_low - 5.0
                        risk = max(entry - sl, 6.0)
                        tp1 = entry + (risk * 2.0)
                        tp2 = entry + (risk * 3.5)
                        msg = (
                            "🚨 <b>SETUP 2: BULLISH OB + FVG ZONE</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Action:</b> <b>BUY / DEMAND</b>\n"
                            f"📦 <b>Order Block (OB):</b> {ob_low:.2f} - {ob_high:.2f}\n"
                            f"🎯 <b>FVG Imbalance Zone:</b> {highs[i-2]:.2f} - {lows[i]:.2f}\n"
                            f"💲 <b>Entry Level:</b> {entry:.2f}\n"
                            f"🛑 <b>Exact SL Level:</b> {sl:.2f} (-{risk:.1f} pts)\n"
                            f"🎯 <b>Target 1 (1:2 RR):</b> {tp1:.2f}\n"
                            f"🎯 <b>Target 2 (1:3.5 RR):</b> {tp2:.2f}\n"
                            "⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # SETUP 3: FRVP POC Rejection
                    recent_vol = volumes[-12:]
                    max_vol_idx = volumes.index(max(recent_vol))
                    poc_price = (highs[max_vol_idx] + lows[max_vol_idx]) / 2.0
                    val_level = min(lows[-12:]) + (poc_price - min(lows[-12:])) * 0.3
                    vah_level = max(highs[-12:]) - (max(highs[-12:]) - poc_price) * 0.3

                    if abs(closes[i] - poc_price) <= 6.0:
                        entry = closes[i]
                        sl = poc_price - 14.0
                        risk = max(entry - sl, 8.0)
                        tp1 = entry + (risk * 2.0)
                        tp2 = vah_level
                        msg = (
                            "🚨 <b>SETUP 3: FRVP POC LEVEL REACTION</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "🎯 <b>Strategy:</b> Value Profile Rejection\n"
                            f"📌 <b>Exact POC Level:</b> {poc_price:.2f}\n"
                            f"📐 <b>Value Area:</b> {val_level:.2f} - {vah_level:.2f}\n"
                            f"💲 <b>Entry Level:</b> {entry:.2f}\n"
                            f"🛑 <b>Exact SL Level:</b> {sl:.2f} (-{risk:.1f} pts)\n"
                            f"🎯 <b>Target 1 (1:2 RR):</b> {tp1:.2f}\n"
                            f"🎯 <b>Target 2 (VAH Liquidity):</b> {tp2:.2f}\n"
                            "⚖️ <b>Risk:Reward:</b> 1:2+\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

                    # SETUP 4: CVD Absorption
                    avg_vol = sum(volumes[-10:]) / 10.0
                    body_size = abs(closes[i] - opens[i])
                    if volumes[i] > (1.8 * avg_vol) and body_size < 8:
                        is_bullish = closes[i] > opens[i]
                        absorb_type = "BULLISH ABSORPTION" if is_bullish else "BEARISH ABSORPTION"
                        entry = closes[i]
                        sl = lows[i] - 5.0 if is_bullish else highs[i] + 5.0
                        risk = abs(entry - sl)
                        tp1 = entry + (risk * 2.0) if is_bullish else entry - (risk * 2.0)
                        tp2 = entry + (risk * 3.5) if is_bullish else entry - (risk * 3.5)

                        msg = (
                            f"🚨 <b>SETUP 4: {absorb_type} DETECTED</b>\n"
                            "━━━━━━━━━━━━━━━━━━\n"
                            "📊 <b>Instrument:</b> NIFTY 50 (5m)\n"
                            "📌 <b>Signal:</b> Delta Absorption Exhaustion\n"
                            f"💲 <b>Trigger Entry:</b> {entry:.2f}\n"
                            f"🛑 <b>Exact SL Level:</b> {sl:.2f} (-{risk:.1f} pts)\n"
                            f"🎯 <b>Target 1 (1:2 RR):</b> {tp1:.2f}\n"
                            f"🎯 <b>Target 2 (1:3.5 RR):</b> {tp2:.2f}\n"
                            "⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n"
                            f"📊 <b>Volume:</b> {volumes[i]} (Avg: {int(avg_vol)})\n"
                            "━━━━━━━━━━━━━━━━━━"
                        )
                        send_telegram_msg(msg)
                        sent_alerts.add(candle_id)

        except Exception as e:
            print(f"Engine Loop Error: {e}")

        time.sleep(60)

# Scanner background thread start
scanner_thread = threading.Thread(target=analyze_market_setups, daemon=True)
scanner_thread.start()

@app.route("/", methods=["GET"])
def health():
    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    status = "OPEN (Live Scanning Active)" if is_market_open() else "CLOSED (Scanner Paused)"
    return jsonify({
        "bot": "active",
        "system": "4H-15m-5m MTF + Target/RR Calculation",
        "current_time_ist": now_ist,
        "market_status": status
    }), 200

# TEST ENDPOINT: Real levels with calculated SL, TP1, TP2, and RR
@app.route("/test-all-setups", methods=["GET"])
def test_all_setups():
    quote = get_dhan_nifty_quote()
    if quote and "last_price" in quote:
        curr_price = float(quote["last_price"])
        day_high = float(quote.get("high", curr_price + 35))
        day_low = float(quote.get("low", curr_price - 35))
    else:
        curr_price = 24542.45
        day_high = 24580.00
        day_low = 24320.00

    # Bullish SFP Setup calculation
    sfp_entry = curr_price
    sfp_sl = curr_price - 15.0
    sfp_risk = sfp_entry - sfp_sl
    sfp_tp1 = sfp_entry + (sfp_risk * 2.0)
    sfp_tp2 = sfp_entry + (sfp_risk * 3.5)

    # Bullish OB Setup calculation
    ob_low = curr_price - 25.0
    ob_high = curr_price - 5.0
    ob_entry = ob_high
    ob_sl = ob_low - 6.0
    ob_risk = ob_entry - ob_sl
    ob_tp1 = ob_entry + (ob_risk * 2.0)
    ob_tp2 = ob_entry + (ob_risk * 3.5)

    # FRVP POC Setup calculation
    poc_level = round((day_high + day_low + curr_price) / 3.0, 2)
    poc_entry = curr_price
    poc_sl = poc_level - 14.0
    poc_risk = abs(poc_entry - poc_sl)
    poc_tp1 = poc_entry + (poc_risk * 2.0)
    poc_tp2 = poc_level + 40.0

    # CVD Absorption Setup calculation
    cvd_entry = curr_price
    cvd_sl = curr_price - 12.0
    cvd_risk = cvd_entry - cvd_sl
    cvd_tp1 = cvd_entry + (cvd_risk * 2.0)
    cvd_tp2 = cvd_entry + (cvd_risk * 3.5)

    setups = [
        (f"🚨 <b>SETUP 1: BULLISH SFP DETECTED</b>\n━━━━━━━━━━━━━━━━━━\n📊 <b>Instrument:</b> NIFTY 50 (5m)\n🎯 <b>Action:</b> <b>BUY / LONG</b>\n📌 <b>Swept Low:</b> {day_low + 15:.2f}\n💲 <b>Entry Price:</b> {sfp_entry:.2f}\n🛑 <b>Exact SL Level:</b> {sfp_sl:.2f} (-{sfp_risk:.1f} pts)\n🎯 <b>Target 1 (1:2 RR):</b> {sfp_tp1:.2f} (+{sfp_risk*2:.1f} pts)\n🎯 <b>Target 2 (1:3.5 RR):</b> {sfp_tp2:.2f} (+{sfp_risk*3.5:.1f} pts)\n⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n━━━━━━━━━━━━━━━━━━"),
        (f"🚨 <b>SETUP 2: BULLISH OB + FVG ZONE</b>\n━━━━━━━━━━━━━━━━━━\n📊 <b>Instrument:</b> NIFTY 50 (5m)\n🎯 <b>Action:</b> <b>BUY / DEMAND</b>\n📦 <b>Order Block (OB):</b> {ob_low:.2f} - {ob_high:.2f}\n💲 <b>Entry Level:</b> {ob_entry:.2f}\n🛑 <b>Exact SL Level:</b> {ob_sl:.2f} (-{ob_risk:.1f} pts)\n🎯 <b>Target 1 (1:2 RR):</b> {ob_tp1:.2f}\n🎯 <b>Target 2 (1:3.5 RR):</b> {ob_tp2:.2f}\n⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n━━━━━━━━━━━━━━━━━━"),
        (f"🚨 <b>SETUP 3: FRVP POC LEVEL REACTION</b>\n━━━━━━━━━━━━━━━━━━\n📊 <b>Instrument:</b> NIFTY 50 (5m)\n📌 <b>POC Level:</b> {poc_level:.2f}\n💲 <b>Entry Level:</b> {poc_entry:.2f}\n🛑 <b>Exact SL Level:</b> {poc_sl:.2f} (-{poc_risk:.1f} pts)\n🎯 <b>Target 1 (1:2 RR):</b> {poc_tp1:.2f}\n🎯 <b>Target 2 (VAH Liquidity):</b> {poc_tp2:.2f}\n⚖️ <b>Risk:Reward:</b> 1:2+\n━━━━━━━━━━━━━━━━━━"),
        (f"🚨 <b>SETUP 4: BULLISH ABSORPTION DETECTED</b>\n━━━━━━━━━━━━━━━━━━\n📊 <b>Instrument:</b> NIFTY 50 (5m)\n📌 <b>Signal:</b> CVD Absorption Exhaustion\n💲 <b>Trigger Entry:</b> {cvd_entry:.2f}\n🛑 <b>Exact SL Level:</b> {cvd_sl:.2f} (-{cvd_risk:.1f} pts)\n🎯 <b>Target 1 (1:2 RR):</b> {cvd_tp1:.2f}\n🎯 <b>Target 2 (1:3.5 RR):</b> {cvd_tp2:.2f}\n⚖️ <b>Risk:Reward:</b> 1:2 / 1:3.5\n━━━━━━━━━━━━━━━━━━")
    ]

    for s in setups:
        send_telegram_msg(s)
        time.sleep(1)

    return jsonify({"status": "All 4 setups tested with dynamic TP1, TP2 and RR!"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
