import os, json, time, asyncio, logging, requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Core Bot Active!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler).serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "1"))
PROCESSED_CACHE = {}

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        await asyncio.to_thread(requests.post, url, json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=5)
    except Exception: pass

def process_item(username, coins, box_type="HAZİNE SANDIĞI"):
    clean_username = str(username).replace("@", "", 1).strip().lower()
    if not clean_username or coins < MIN_COINS: return
    
    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_CACHE and (time.time() - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = time.time()
    if len(PROCESSED_CACHE) > 500: PROCESSED_CACHE.clear()

    mesaj = f"🎁 <b>{box_type.upper()}</b>\n\n👤 <b>YAYINCI:</b> @{clean_username}\n💎 <b>ELMAS:</b> {coins}\n\n⚡ <a href='https://www.tiktok.com/@{clean_username}/live'>YAYINA GİT</a>"
    asyncio.create_task(send_telegram(mesaj))

async def get_ws_ticket_and_path():
    """Sitenin bilet ürettiği ana kapıya istek atıp şifreli tünel yolunu alır"""
    url = "https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live=1000"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://dichvu321.com/en/tiktok-treasure-box-bot/"
    }
    try:
        response = await asyncio.to_thread(requests.post, url, headers=headers, timeout=10)
        data = response.json()
        if data.get("success"):
            path = data.get("path") # Örn: /live-feed?ticket=eyJ...
            return f"wss://dichvu321.com{path}"
    except Exception as e:
        logging.error(f"Bilet alma hatası: {e}")
    return None

async def listen_to_feed():
    while True:
        ws_url = await get_ws_ticket_and_path()
        if not ws_url:
            logging.warning("Bilet alınamadı, 5 saniye sonra tekrar denenecek...")
            await asyncio.sleep(5)
            continue

        logging.info("Doğrudan WebSocket tüneline bağlanılıyor...")
        try:
            async with websockets.connect(ws_url, ping_interval=20) as websocket:
                logging.info("✅ Tünel bağlantısı başarılı! Veriler dinleniyor...")
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        items = data if isinstance(data, list) else [data.get("data", data)]
                        for item in items:
                            if not isinstance(item, dict): continue
                            username = item.get("uniqueId") or item.get("username") or ""
                            coins = next((int(item[k]) for k in ["coins", "diamonds", "totalCoins", "val"] if item.get(k) is not None), 0)
                            box_type = str(item.get("type", "HAZİNE SANDIĞI"))
                            if username and coins > 0:
                                process_item(username, coins, box_type)
                    except Exception:
                        pass
        except Exception as e:
            logging.warning(f"Tünel bağlantısı koptu veya bilet bitti: {e}. Yeniden bilet alınıyor...")
            await asyncio.sleep(3)

async def main():
    await send_telegram("🤖 <b>Çekirdek Bot Başlatıldı!</b> Ana omurgaya bağlanılıyor...")
    await listen_to_feed()

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
