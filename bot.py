import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time
import re

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Synced Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "5050032521")

# Upstash Ortak Hafıza Bilgileri
UPSTASH_URL = "https://exotic-javelin-180919.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAsK3AAIgcDFmZGQ3Njk5NjBhODQ0MmY3YTIyNThiZTMzYTU4N2M5Yg"

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

CACHE_TIMEOUT = 1800  # 30 dakika ortak hafızada tutulur

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

# Upstash üzerinden ortak hafıza kontrolü ve kayıt
def check_and_save_cache(cache_key):
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    try:
        # Önce bu anahtar var mı diye bak (GET)
        res = requests.get(f"{UPSTASH_URL}/get/{cache_key}", headers=headers, timeout=2)
        data = res.json()
        
        # Eğer Upstash'te zaten kayıtlıysa True döndür (Yani daha önce atılmış)
        if data.get("result") is not None:
            return True
            
        # Kayıtlı değilse, 30 dakika (1800 sn) süreyle Upstash'e set et
        requests.get(f"{UPSTASH_URL}/set/{cache_key}/1?EX={CACHE_TIMEOUT}", headers=headers, timeout=2)
        return False
    except Exception as e:
        print("Upstash bağlantı hatası:", e)
        return False

async def listen_live_feed():
    print("🚀 ORTAK BULUT HAFIZALI BOT AKTİF")
    
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

                        cache_key = re.sub(r'[^a-z0-9]', '', clean_username.lower())

                        # ORTAK HAFIZA KONTROLÜ (Termux ve Render buraya soracak)
                        is_already_sent = await asyncio.to_thread(check_and_save_cache, cache_key)
                        if is_already_sent:
                            continue  # Diğer bot zaten atmış, atla!

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
                        print(f"✅ ORTAK BULUTA YAZILDI VE GÖNDERİLDİ: @{clean_username}")

            else:
                await asyncio.sleep(2)

        except Exception as e:
            await asyncio.sleep(2)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
