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

def get_exact_viewers(payload):
    """
    Yanlış küçük sayaçları eleyip gerçek ve doğru izleyici sayısını bulan gelişmiş fonksiyon.
    """
    candidate_values = []
    
    # Tüm anahtarları tarayarak içinde 'viewer', 'izleyici', 'count' geçen sayıları topluyoruz
    for k, v in payload.items():
        k_lower = str(k).lower()
        if any(term in k_lower for term in ["viewer", "izleyici", "count", "participant", "user"]):
            try:
                val = float(v)
                if val > 0:
                    candidate_values.append(val)
            except:
                pass
                
    # Eğer aday bulunduysa, aralarındaki en mantıklı (gerçek oda büyüklüğünü veren) değeri seçiyoruz
    if candidate_values:
        # Genellikle en doğru izleyici sayısı bu adaylar içinde en büyük veya ortalama olandır
        # Küçük alt sayaçları (örn: 2, 5 gibi) elemek için 0'dan büyük mantıklı rakamlara bakıyoruz
        valid_ones = [val for val in candidate_values if val > 3]
        if valid_ones:
            return max(valid_ones) # En büyük olan gerçek oda izleyicisidir
        return max(candidate_values)
        
    return 9999

async def listen_live_feed():
    print("🚀 DICHVU321 KESİN ÇÖZÜM MODU BAŞLATILDI")
    
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

                        # Doğru ve filtrelenmiş izleyici tespiti
                        people = get_exact_viewers(payload)

                        clean_username = str(username).replace("@", "").strip()
                        if not clean_username or clean_username.lower() == "bilinmiyor":
                            continue

                        if amount <= 0:
                            continue
                            
                        # --- 3 JETON = 1 KİŞİ ORANI ---
                        max_kisi_izni = amount / 3.0

                        print(f"Kontrol: @{clean_username} | Elmas: {int(amount)} | Okunan Kişi: {int(people)} | İzin Verilen Sınır: {max_kisi_izni:.1f}")

                        if people <= 0 or people > max_kisi_izni:
                            continue

                        display_username = f"@{clean_username}"
                        live_link = payload.get("link") or payload.get("url") or f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"🤖 **ORANLI FIRSAT!** {SENIN_TELEGRAM_ID}\n\n"
                            f"🎁 **HAZİNE SANDIĞI**\n"
                            f"👤 **YAYINCI:** `{display_username}`\n"
                            f"💎 **ELMAS:** {int(amount)}\n"
                            f"👥 **DAĞITILAN:** {int(people)} KİŞİ (Max Sınır: {int(max_kisi_izni)})\n\n"
                            f"⚡ **Kaçırma, hemen yayına gir:**\n"
                            f"{live_link}"
                        )

                        send_telegram(mesaj)
                        print(f"🎯 KESİN YAKALANDI VE GÖNDERİLDİ: {display_username} (Elmas: {int(amount)}, Kişi: {int(people)})")

        except Exception as e:
            print(f"Bağlantı koptu veya hata oluştu: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
