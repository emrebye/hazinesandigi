import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Dichvu321 Treasure Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "5050032521")
SENIN_TELEGRAM_ID = "@Jiminienn"

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

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

async def listen_live_feed():
    print("🚀 DICHVU321 KONTROLLÜ BOT BAŞLATILDI")
    
    while True:
        try:
            print("Proxy üzerinden bilet alınıyor...")
            res = requests.get(PROXY_URL, headers=HEADERS, timeout=10)
            data = res.json()

            if data.get("success"):
                path = data.get("path")
                ws_url = f"wss://dichvu321.com{path}"
                print(f"Canlı akışa bağlanılıyor: {ws_url}")

                async with websockets.connect(ws_url, additional_headers=HEADERS) as websocket:
                    print("Bağlantı başarılı! Akış taranıyor...")

                    async for message in websocket:
                        try:
                            event_data = json.loads(message)
                        except:
                            continue

                        payload = event_data
                        if "data" in event_data and isinstance(event_data["data"], dict):
                            payload = event_data["data"]
                        elif "payload" in event_data and isinstance(event_data["payload"], dict):
                            payload = event_data["payload"]

                        username = (
                            payload.get("uniqueId") or
                            payload.get("nickname") or
                            payload.get("streamer") or 
                            payload.get("channel") or 
                            payload.get("username") or 
                            payload.get("user") or 
                            payload.get("author") or 
                            payload.get("name") or 
                            payload.get("sender") or
                            event_data.get("uniqueId") or
                            event_data.get("username") or 
                            "Bilinmiyor"
                        )
                        
                        coins_raw = (
                            payload.get("coins") or 
                            payload.get("coin") or 
                            payload.get("amount") or 
                            payload.get("elmas") or 
                            payload.get("value") or 
                            payload.get("diamond") or
                            payload.get("diamonds") or
                            payload.get("prize") or
                            event_data.get("coins") or
                            "0"
                        )
                        
                        # İzleyici sayısını çeken anahtarlar, ekrandaki gerçek değere (viewers/viewerCount) öncelik verecek şekilde düzenlendi
                        viewers_raw = (
                            payload.get("viewerCount") or 
                            payload.get("viewers") or 
                            payload.get("totalUser") or
                            payload.get("participants") or 
                            payload.get("participantCount") or
                            payload.get("count") or 
                            payload.get("userCount") or
                            payload.get("people") or
                            event_data.get("viewerCount") or
                            event_data.get("viewers") or
                            "0"
                        )

                        clean_username = str(username).replace("@", "").strip()
                        
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        try:
                            amount = float(coins_raw)
                            people = float(viewers_raw)
                        except ValueError:
                            amount = 0
                            people = 0

                        # Kademeli sınır matrisi
                        if amount <= 20:
                            max_kisi_izni = 7
                        elif amount <= 30:
                            max_kisi_izni = 14
                        elif amount <= 50:
                            max_kisi_izni = 22
                        elif amount <= 100:
                            max_kisi_izni = 35
                        elif amount <= 500:
                            max_kisi_izni = 60
                        elif amount <= 1000:
                            max_kisi_izni = 100
                        else:
                            max_kisi_izni = 150

                        if people <= 0 or people > max_kisi_izni:
                            print(f"⏩ Elendi: @{clean_username} (Elmas: {amount}, Kişi: {people}, Sınır: {max_kisi_izni})")
                            continue

                        display_username = f"@{clean_username}"
                        live_link = payload.get("link") or payload.get("url") or event_data.get("link") or f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"🤖 **KADEMELİ FIRSAT!** {SENIN_TELEGRAM_ID}\n\n"
                            f"🎁 **HAZİNE SANDIĞI**\n"
                            f"👤 **YAYINCI:** `{display_username}`\n"
                            f"💎 **ELMAS:** {int(amount)}\n"
                            f"👥 **DAĞITILAN:** {int(people)} KİŞİ (Sınır: {max_kisi_izni})\n\n"
                            f"⚡ **Kaçırma, hemen yayına gir:**\n"
                            f"{live_link}"
                        )

                        send_telegram(mesaj)
                        print(f"🎯 DOĞRU YAKALANDI: {display_username} (Elmas: {amount}, Kişi: {people})")

        except Exception as e:
            print(f"Bağlantı koptu veya hata oluştu: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
