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

def parse_box_data(payload):
    """
    Yayındaki toplam izleyici ile sandığa dağıtılan kişi sayısını kesin olarak ayrıştırır.
    """
    # 1. Sandığa dağıtılan kişi sınırı (Sandık kontenjanı / slot)
    chest_keys = ["chestUsers", "maxUsers", "limit", "slot", "boxUserCount", "recipientCount", "max_people", "userCount"]
    chest_people = None
    for k in chest_keys:
        if k in payload and payload[k] is not None:
            try:
                val = int(payload[k])
                if val > 0:
                    chest_people = val
                    break
            except:
            
                pass

    # Eğer özel anahtar bulunamazsa genel sayıları tarayalım
    if chest_people is None:
        for k, v in payload.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ["chest", "box", "limit", "slot", "recipient"]):
                try:
                    val = int(v)
                    if 0 < val < 500: # Sandık kişi sayıları genelde makul rakamlardır
                        chest_people = val
                        break
                except:
                    pass

    # 2. Yayındaki toplam izleyici sayısı
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
    print("🚀 SANDIK VE ODA KİŞİ AYRIŞTIRMA SİSTEMİ BAŞLATILDI")
    
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

                        # Sandığa dağıtılan kişi ve oda izleyicisini net olarak ayırıyoruz
                        chest_people, room_viewers = parse_box_data(payload)

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        if amount <= 0 or chest_people is None:
                            continue

                        print(f"Kontrol -> @{clean_username} | Elmas: {int(amount)} | Sandığa Dağıtılan: {chest_people} | Oda İzleyicisi: {room_viewers}")

                        # Kriter: Ödül yüksek (örn: 20 ve üstü) VE sandığın dağıtıldığı kişi sayısı az (örn: 15 ve altı)
                        if amount >= 20 and chest_people <= 15:
                            display_username = f"@{clean_username}"
                            live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

                            mesaj = (
                                f"🤖 **ORANLI FIRSAT!** {SENIN_TELEGRAM_ID}\n\n"
                                f"🎁 **HAZİNE SANDIĞI**\n"
                                f"👤 **YAYINCI:** `{display_username}`\n"
                                f"💎 **ELMAS:** {int(amount)}\n"
                                f"👥 **DAĞITILAN:** {chest_people} KİŞİ\n"
                                f"👀 **ODA İZLEYİCİSİ:** {room_viewers}\n\n"
                                f"⚡ **Kaçırma, hemen yayına gir:**\n"
                                f"{live_link}"
                            )

                            send_telegram(mesaj)
                            print(f"🎯 YAKALANDI VE GÖNDERİLDİ: {display_username} | Elmas: {int(amount)} | Dağıtılan: {chest_people}")

        except Exception as e:
            print(f"Bağlantı koptu veya hata oluştu: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
