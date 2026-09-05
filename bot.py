import os
import asyncio
import json
import logging
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Render Canlı Tutan HTTP Sunucusu
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Test Bot Active")
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BOOTSTRAP_URL = "https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live=1000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/en/tiktok-treasure-box-bot/"
}

def test_telegram_connection():
    """Telegram Baglantisini Test Eder"""
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("❌ HATA: BOT_TOKEN veya CHAT_ID Render Environment Variables icinde bulunamadi!")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": "🚀 <b>Bot Baslatildi!</b> Telegram baglantisi basarili.", "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.ok:
            logging.info("✅ TELEGRAM TEST MESAJI BASARIYLA GONDERILDI!")
            return True
        else:
            logging.error(f"❌ TELEGRAM HATASI: HTTP {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logging.error(f"❌ TELEGRAM BAGLANTI HATASI: {e}")
        return False

def get_websocket_url():
    """Site Ticket Istegini Test Eder"""
    try:
        res = requests.get(BOOTSTRAP_URL, headers=HEADERS, timeout=10)
        logging.info(f"Site Yanit Kodu: HTTP {res.status_code}")
        
        if res.status_code == 403 or "cloudflare" in res.text.lower():
            logging.error("❌ CLOUDFLARE ENGELI: Render IP adresi site tarafindan engellendi!")
            return None
            
        data = res.json()
        if data.get("success"):
            path = data.get("path", "").replace("\\/", "/")
            return f"wss://dichvu321.com{path}"
        else:
            logging.error(f"❌ BİLET ALINAMADI. Yanit: {data}")
    except Exception as e:
        logging.error(f"❌ SITE BAGLANTI HATASI: {e}")
    return None

async def listen_and_debug():
    # 1. Telegram Testi
    test_telegram_connection()

    while True:
        # 2. Site Ticket Testi
        ws_url = get_websocket_url()
        if not ws_url:
            logging.warning("⚠️ WebSocket URL alinamadi, 10 sn sonra tekrar deneniyor...")
            await asyncio.sleep(10)
            continue

        logging.info(f"🔗 WebSocket Baglantisi Kuruluyor: {ws_url}")
        try:
            async with websockets.connect(ws_url, additional_headers=HEADERS, ping_interval=20, ping_timeout=10) as ws:
                logging.info("✅ WEBSOCKET BAGLANTISI BASARILI! Gelen ham veriler dinleniyor...")
                
                async for message in ws:
                    # Gelen her ham veriyi filtrelemeden direkt loga basıyoruz
                    logging.info(f"📥 GELEN HAM VERI: {message}")
                    
        except Exception as e:
            logging.error(f"⚠️ WebSocket Kopmasi/Hata: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_and_debug())
