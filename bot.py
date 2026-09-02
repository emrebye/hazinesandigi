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
        self.wfile.write(b"Clean Chest Bot Active!")

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

# Aynı isimleri tekrar göndermemek için hafıza (Yayıncı adı -> Gönderilme Zamanı)
sent_cache = {}
CACHE_TIMEOUT = 300  # 5 dakika boyunca aynı kullanıcı tekrar gönderilmez

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
        print("Telegram mesaj hatası:", e)

def parse_box_data(payload):
    chest_people = None
    for k in ["chestUsers", "maxUsers", "limit", "slot", "boxUserCount", "recipientCount", "max_people", "userCount"]:
        if k in payload and payload[k] is not None:
            try:
                val = int(payload[k])
                if val > 0:
                    chest_people = val
                    break
            except:
                pass

    if chest_people is None:
        for k, v in payload.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ["chest", "box", "limit", "slot", "recipient"]):
                try:
                    val = int(v)
                    if 0 < val < 500:
                        chest_people = val
                        break
                except:
                    pass

    room_viewers = 0
    for k in ["viewerCount", "viewers", "roomViewers", "participantCount"]:
        if k in payload and payload[k] is not None:
            try:
                room_viewers = int(payload[k])
                break
            except:
                pass

    return chest_people, room_viewers

async def listen_live_feed():
    print("🚀 TEMİZ FORMAT VE TEKRAR ENGELLEME SİSTEMİ AKTİF")
    
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

                        username = (
                            payload.get("uniqueId") or payload.get("nickname") or 
                            payload.get("streamer") or payload.get("channel") or 
                            payload.get("username") or payload.get("user") or 
                            payload.get("author") or payload.get("name") or "Bilinmiyor"
                        )
                        
                        coins_raw = (
                            payload.get("coins") or payload.get("coin") or 
                            payload.get("amount") or payload.get("elmas") or 
                            payload.get("value") or payload.get("diamond") or "0"
                        )
                        
                        try:
                            amount = float(coins_raw)
                        except ValueError:
                            amount = 0

                        chest_people, room_viewers = parse_box_data(payload)

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        if amount <= 0 or chest_people is None:
                            continue

                        # Süre aşımı geçmiş eski kayıtları temizle
                        current_time = time.time()
                        expired_keys = [k for k, t in sent_cache.items() if current_time - t > CACHE_TIMEOUT]
                        for k in expired_keys:
                            del sent_cache[k]

                        # Aynı kullanıcı daha önce gönderildiyse atla
                        if clean_username in sent_cache:
                            continue

                        # İstediğin kriter (Örn: Elmas 15 ve üstü, dağıtılan kişi 20'den az)
                        if amount >= 15 and chest_people <= 20:
                            display_username = f"@{clean_username}"
                            live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

                            mesaj = (
                                f"🎁 **HAZİNE SANDIĞI**\n"
                                f"👤 **YAYINCI:** `{display_username}`\n"
                                f"👁️ **İZLEYİCİ:** {room_viewers}\n"
                                f"💎 **ELMAS:** {int(amount)}\n"
                                f"📦 **DAĞITILAN:** {chest_people} KİŞİ\n"
                                f"🔗 {live_link}"
                            )

                            send_telegram(mesaj)
                            sent_cache[clean_username] = current_time
                            print(f"✅ GÖNDERİLDİ: {display_username} | Elmas: {int(amount)} | Dağıtılan: {chest_people}")

        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
