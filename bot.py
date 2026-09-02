import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import re

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Jimin Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "5050032521")

UPSTASH_URL = "https://exotic-javelin-180919.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAsK3AAIgcDFmZGQ3Njk5NjBhODQ0MmY3YTIyNThiZTMzYTU4N2M5Yg"

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

CACHE_TIMEOUT = 1800

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

def check_and_save_cache(cache_key):
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}", "Content-Type": "application/json"}
    try:
        payload = ["SET", cache_key, "1", "EX", str(CACHE_TIMEOUT), "NX"]
        res = requests.post(UPSTASH_URL, headers=headers, json=payload, timeout=2)
        data = res.json()
        
        if data.get("result") == "OK":
            return False 
        return True 
    except Exception as e:
        return False

async def listen_live_feed():
    print("🚀 JIMIN KİŞİ SAYISI FİX AKTİF")
    
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
                            
                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username:
                            continue

                        coins_raw = payload.get("coins") or payload.get("amount") or payload.get("elmas") or payload.get("diamond") or 0
                        try:
                            amount = float(coins_raw)
                        except:
                            amount = 0

                        if amount < 10:
                            continue

                        cache_key = re.sub(r'[^a-z0-9]', '', clean_username.lower())
                        if await asyncio.to_thread(check_and_save_cache, cache_key):
                            continue

                        room_viewers = payload.get("viewerCount") or payload.get("viewers") or payload.get("totalUserCount") or 0
                        
                        # Genişletilmiş Dağıtılan Kişi Taraması
                        chest_people = (
                            payload.get("chestUsers") or 
                            payload.get("maxUsers") or 
                            payload.get("limit") or 
                            payload.get("userLimit") or 
                            payload.get("userCount") or 
                            payload.get("users") or 
                            payload.get("count") or
                            payload.get("participantCount") or
                            payload.get("maxPeople") or
                            payload.get("chestLimit") or
                            payload.get("boxLimit") or
                            payload.get("chestCount") or
                            payload.get("max_users") or
                            payload.get("user_limit") or
                            payload.get("chest_users") or
                            payload.get("people") or
                            payload.get("num") or
                            payload.get("capacity") or
                            15
                        )

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
                        print(f"✅ GÖNDERİLDİ: @{clean_username} | Elmas: {int(amount)} | Kişi: {chest_people}")

            else:
                await asyncio.sleep(2)

        except Exception as e:
            await asyncio.sleep(2)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
