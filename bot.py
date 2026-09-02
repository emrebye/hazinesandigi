import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hyper Fast Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "5050032521")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

sent_cache = {}
CACHE_TIMEOUT = 600
last_cache_cleanup = time.time()

async def send_telegram_async(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    def _send():
        try:
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": text, 
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }, timeout=2)
        except:
            pass
    await asyncio.to_thread(_send)

async def listen_live_feed():
    global last_cache_cleanup
    print("🚀 ULTRA HIZLI MOD AKTİF")
    
    while True:
        try:
            res = await asyncio.to_thread(requests.get, PROXY_URL, headers=HEADERS, timeout=5)
            data = res.json()

            if data.get("success"):
                path = data.get("path")
                ws_url = f"wss://dichvu321.com{path}"

                async with websockets.connect(ws_url, additional_headers=HEADERS, ping_interval=None) as websocket:
                    async for message in websocket:
                        try:
                            event_data = json.loads(message)
                        except:
                            continue

                        payload = event_data.copy()
                        if "data" in event_data and isinstance(event_data["data"], dict):
                            payload.update(event_data["data"])
                        if "payload" in event_data and isinstance(event_data["payload"], dict):
                            payload.update(event_data["payload"])

                        username = payload.get("uniqueId") or payload.get("nickname") or payload.get("username") or payload.get("streamer")
                        if not username:
                            continue
                            
                        coins_raw = payload.get("coins") or payload.get("amount") or payload.get("elmas") or payload.get("diamond") or 0
                        try:
                            amount = float(coins_raw)
                        except:
                            amount = 0

                        if amount < 10:
                            continue

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username:
                            continue

                        cache_key = clean_username.lower()

                        # Önbellek temizliği artık her mesajda değil, dakikada bir yapılıyor (Hızı uçurur)
                        current_time = time.time()
                        if current_time - last_cache_cleanup > 60:
                            expired = [k for k, t in sent_cache.items() if current_time - t > CACHE_TIMEOUT]
                            for k in expired:
                                del sent_cache[k]
                            last_cache_cleanup = current_time

                        if cache_key in sent_cache:
                            continue

                        room_viewers = payload.get("viewerCount") or payload.get("viewers") or 25
                        chest_people = payload.get("chestUsers") or payload.get("maxUsers") or payload.get("limit") or 15
                        live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"🎁 **HAZİNE SANDIĞI**\n"
                            f"👤 **YAYINCI:** `@{clean_username}`\n"
                            f"👁️ **İZLEYİCİ:** {room_viewers}\n"
                            f"💎 **ELMAS:** {int(amount)}\n"
                            f"📦 **DAĞITILAN:** {chest_people} KİŞİ\n"
                            f"🔗 {live_link}"
                        )

                        asyncio.create_task(send_telegram_async(mesaj))
                        sent_cache[cache_key] = current_time

            else:
                await asyncio.sleep(2)

        except Exception as e:
            await asyncio.sleep(2)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
