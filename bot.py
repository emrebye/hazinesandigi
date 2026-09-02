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
        self.wfile.write(b"Bot Active!")

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
CACHE_TIMEOUT = 300

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": text, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=5)
    except Exception as e:
        print("Telegram hata:", e)

async def listen_live_feed():
    print("🚀 SAĞLAMLAŞTIRILMIŞ BOT BAŞLATILDI")
    
    while True:
        try:
            res = requests.get(PROXY_URL, headers=HEADERS, timeout=10)
            data = res.json()

            if data.get("success"):
                path = data.get("path")
                ws_url = f"wss://dichvu321.com{path}"

                async with websockets.connect(ws_url, additional_headers=HEADERS) as websocket:
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

                        username = payload.get("uniqueId") or payload.get("nickname") or payload.get("username") or payload.get("streamer") or "Bilinmiyor"
                        coins_raw = payload.get("coins") or payload.get("amount") or payload.get("elmas") or payload.get("diamond") or "0"
                        
                        try:
                            amount = float(coins_raw)
                        except:
                            amount = 0

                        if amount <= 0:
                            continue

                        # İzleyici ve dağıtılan kişi sayılarını esnek çekiyoruz (bulamazsa varsayılan veriyor)
                        room_viewers = 0
                        for k in ["viewerCount", "viewers", "roomViewers", "participantCount"]:
                            if k in payload and payload[k] is not None:
                                try:
                                    room_viewers = int(payload[k])
                                    break
                                except:
                                    pass
                        if room_viewers == 0:
                            room_viewers = 25 # Varsayılan

                        chest_people = 0
                        for k in ["chestUsers", "maxUsers", "limit", "slot", "boxUserCount", "recipientCount", "userCount"]:
                            if k in payload and payload[k] is not None:
                                try:
                                    chest_people = int(payload[k])
                                    break
                                except:
                                    pass
                        if chest_people == 0:
                            chest_people = 15 # Varsayılan

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        # Süre kontrolü (Aynı yayıncıyı 5 dakika içinde tekrar göndermez)
                        current_time = time.time()
                        if clean_username in sent_cache and current_time - sent_cache[clean_username] < CACHE_TIMEOUT:
                            continue

                        # İstediğin format ve esnek filtre (Elmas 10 ve üstü)
                        if amount >= 10:
                            live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

                            mesaj = (
                                f"🎁 **HAZİNE SANDIĞI**\n"
                                f"👤 **YAYINCI:** `@{clean_username}`\n"
                                f"👁️ **İZLEYİCİ:** {room_viewers}\n"
                                f"💎 **ELMAS:** {int(amount)}\n"
                                f"📦 **DAĞITILAN:** {chest_people} KİŞİ\n"
                                f"🔗 {live_link}"
                            )

                            send_telegram(mesaj)
                            sent_cache[clean_username] = current_time
                            print(f"✅ GÖNDERİLDİ: @{clean_username} | Elmas: {int(amount)}")

            else:
                await asyncio.sleep(5)

        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
