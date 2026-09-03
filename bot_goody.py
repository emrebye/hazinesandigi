import os
import asyncio
import json
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# Render / UptimeRobot Kapanma Engelleyici (Dummy Server)
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Goody Bot Active!")

    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Telegram Ayarları
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "7609507830:AAFFNURagzXkBlrV0eLpnaQ7_y7wOyxONvY")
CHAT_ID = os.getenv("CHAT_ID", "-1003999489709")
PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

http_session = requests.Session()
LOCAL_CACHE = set()

async def send_telegram(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "disable_web_page_preview": True
    }
    try:
        await asyncio.to_thread(http_session.post, url, json=payload, timeout=2)
    except Exception:
        pass

async def listen_live_feed():
    while True:
        try:
            res = await asyncio.to_thread(http_session.get, PROXY_URL, headers=HEADERS, timeout=5)
            data = res.json()

            if data.get("success"):
                path = data.get("path")
                ws_url = f"wss://dichvu321.com{path}"

                async with websockets.connect(
                    ws_url,
                    additional_headers=HEADERS,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:

                    async for message in websocket:
                        try:
                            event_data = json.loads(message)
                        except Exception:
                            continue

                        payload = (
                            event_data.get("data")
                            if isinstance(event_data.get("data"), dict)
                            else event_data
                        )

                        if not isinstance(payload, dict) or payload.get("status") == "connected":
                            continue

                        box_type_raw = str(payload.get("type") or "").lower()
                        source_raw = str(payload.get("source") or "").lower()
                        envelope_info = payload.get("envelopeInfo") or {}

                        if not isinstance(envelope_info, dict):
                            envelope_info = {}

                        business_type = envelope_info.get("businessType", 1)
                        
                        # Sadece Goody Bag Filtresi
                        is_goody = (business_type == 2 or "goody" in box_type_raw or "goody" in source_raw)
                        if not is_goody:
                            continue

                        # Elmas/Jeton Sayısı Tespiti (Önce Toplam Havuz Değerleri)
                        coins = int(
                            envelope_info.get("totalDiamondCount")
                            or envelope_info.get("diamondCount")
                            or envelope_info.get("coinCount")
                            or payload.get("totalCoins")
                            or payload.get("coins")
                            or payload.get("diamondCount")
                            or 0
                        )

                        # 50 Elmasın Altındaki Kutuları Filtreleme
                        if coins < 50:
                            continue

                        username = (
                            payload.get("uniqueId")
                            or payload.get("nickname")
                            or payload.get("username")
                            or ""
                        )
                        clean_username = str(username).replace("@", "").strip().lower()

                        if not clean_username or clean_username in LOCAL_CACHE:
                            continue

                        LOCAL_CACHE.add(clean_username)

                        viewers = (
                            payload.get("viewerCount")
                            or payload.get("userCount")
                            or envelope_info.get("viewerCount")
                            or 0
                        )

                        live_link = f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"🎁 GOODY BAG (KUTU)\n"
                            f"👤 YAYINCI: @{clean_username}\n"
                            f"👁️ İZLEYİCİ: {viewers}\n"
                            f"💎 ELMAS: {coins}\n"
                            f"🔗 {live_link}"
                        )

                        asyncio.create_task(send_telegram(mesaj))
                        print(f"GOODY: @{clean_username} | Elmas: {coins}")

        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
