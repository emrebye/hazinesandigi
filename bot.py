import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# --- 1. RENDER KAPANMASIN DIYE SAHTE PORT SUNUCUSU ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Dichvu321 Treasure Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- 2. AYARLAR VE ÇEVRE DEĞİŞKENLERİ ---
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "5050032521")
SENIN_TELEGRAM_ID = "@Jiminienn"

# Hızlı ve Sadece Sandık Odaklı Canlı Bağlantı Linki
PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

# --- 3. TELEGRAM MESAJ GÖNDERME VE FİLTRE ---
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
    print("🚀 DICHVU321 BİLDİRİM BOTU (SADECE AZ KİŞİ MODU) BAŞLATILDI")
    
    while True:
        try:
            print("Proxy üzerinden bilet (ticket) alınıyor...")
            res = requests.get(PROXY_URL, headers=HEADERS, timeout=10)
            data = res.json()

            if data.get("success"):
                path = data.get("path")
                ws_url = f"wss://dichvu321.com{path}"
                print(f"Canlı akışa bağlanılıyor: {ws_url}")

                async with websockets.connect(ws_url, additional_headers=HEADERS) as websocket:
                    print("Bağlantı başarılı! Hızlı sandık akışı dinleniyor...")

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

                        # Kullanıcı Adı Yakalama
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
                        
                        # Elmas Miktarı (Sadece gösterim için alınıyor, filtrede kullanılmıyor)
                        coins_raw = (
                            payload.get("coins") or 
                            payload.get("coin") or 
                            payload.get("amount") or 
                            payload.get("elmas") or 
                            payload.get("value") or 
                            payload.get("diamond") or
                            event_data.get("coins") or
                            "0"
                        )
                        
                        # Katılımcı/Kişi Sayısı
                        viewers_raw = (
                            payload.get("viewers") or 
                            payload.get("viewerCount") or 
                            payload.get("participants") or 
                            payload.get("count") or 
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

                        # --- TEK VE NET KİRTER: SADECE KİŞİ SAYISI ---
                        # Buradaki '20' rakamını en fazla kaç kişi olmasını istiyorsan değiştirebilirsin (Örn: 15, 20, 25 vb.)
                        MAX_KISI_SINIRI = 20  

                        is_few_people = (0 < people <= MAX_KISI_SINIRI)

                        if not is_few_people:
                            print(f"⏩ Kalabalık Elendi: @{clean_username} (Kişi: {people}, Elmas: {amount})")
                            continue

                        display_username = f"@{clean_username}"
                        live_link = payload.get("link") or payload.get("url") or event_data.get("link") or f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"🤖 **AZ KİŞİLİ FIRSAT!** {SENIN_TELEGRAM_ID}\n\n"
                            f"🎁 **HAZİNE SANDIĞI**\n"
                            f"👤 **YAYINCI:** `{display_username}`\n"
                            f"👥 **DAĞITILAN:** {int(people)} KİŞİ\n"
                            f"💎 **ELMAS:** {int(amount)}\n\n"
                            f"⚡ **Kaçırma, hemen yayına gir:**\n"
                            f"{live_link}"
                        )

                        send_telegram(mesaj)
                        print(f"🎯 AZ KİŞİLİ SANDIK YAKALANDI: {display_username} (Kişi: {people})")

        except Exception as e:
            print(f"Bağlantı koptu veya hata oluştu: {e}")
            print("5 saniye sonra yeniden denenecek...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Render için HTTP sunucusunu başlat
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
