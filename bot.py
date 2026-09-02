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

def find_value_smart(data_dict, target_keywords):
    """
    Sözlük içinde anahtar adında target_keywords geçen veya 
    değeri sayı olan en uygun alanı akıllıca bulur.
    """
    if not isinstance(data_dict, dict):
        return 0
        
    for key, value in data_dict.items():
        key_lower = str(key).lower()
        for kw in target_keywords:
            if kw in key_lower:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    pass
    return None

async def listen_live_feed():
    print("🚀 DICHVU321 AKILLI KONTROL SİSTEMİ BAŞLATILDI")
    
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

                        # Tüm olası katmanları birleştirip tek bir büyük havuz yapıyoruz
                        payload = event_data.copy()
                        if "data" in event_data and isinstance(event_data["data"], dict):
                            payload.update(event_data["data"])
                        if "payload" in event_data and isinstance(event_data["payload"], dict):
                            payload.update(event_data["payload"])

                        # Kullanıcı Adı
                        username = (
                            payload.get("uniqueId") or payload.get("nickname") or 
                            payload.get("streamer") or payload.get("channel") or 
                            payload.get("username") or payload.get("user") or 
                            payload.get("author") or payload.get("name") or "Bilinmiyor"
                        )
                        
                        # --- AKILLI ELMAS TESPİTİ ---
                        amount = find_value_smart(payload, ["coin", "diamond", "elmas", "amount", "prize", "value", "xu", "jeton"])
                        if amount is None:
                            amount = 0

                        # --- AKILLI İZLEYİCİ / KİŞİ TESPİTİ ---
                        # İngilizce, Türkçe ve Vietnamca tüm olası sayaç terimlerini tarar
                        people = find_value_smart(payload, ["viewer", "participant", "count", "people", "user", "kisi", "izleyici", "katilimci", "soluong", "nguoi"])
                        if people is None:
                            people = 0

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        # Kademeli sınır matrisi (Birebir istediğin oranlar)
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

                        # Eğer izleyici sayısı 0 okunduysa veya belirlenen sınırın üzerindeyse eliyoruz
                        if people <= 0 or people > max_kisi_izni:
                            print(f"⏩ Elendi: @{clean_username} | Elmas: {int(amount)} | Kişi: {int(people)} (Sınır: {max_kisi_izni})")
                            continue

                        display_username = f"@{clean_username}"
                        live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

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
                        print(f"🎯 KESİN VE DOĞRU YAKALANDI: {display_username} (Elmas: {int(amount)}, Kişi: {int(people)})")

        except Exception as e:
            print(f"Bağlantı koptu veya hata oluştu: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
