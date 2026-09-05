import os, json, time, asyncio, logging
import cloudscraper
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

# Cloudflare ve çerezleri tutan özel oturum oluşturuyoruz
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        await asyncio.to_thread(scraper.post, url, json={
            "chat_id": CHAT_ID, 
            "text": mesaj, 
            "parse_mode": "HTML", 
            "disable_web_page_preview": True
        }, timeout=5)
    except Exception as e:
        logging.error(f"Telegram gönderme hatası: {e}")

def process_item(username, coins, box_type="HAZİNE SANDIĞI"):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS: return
    
    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_CACHE and (time.time() - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = time.time()
    if len(PROCESSED_CACHE) > 500: PROCESSED_CACHE.clear()

    logging.info(f"🎯 Sandık Yakalandı: @{clean_username} ({coins} Coin)")
    mesaj = f"🎁 <b>{box_type.upper()}</b>\n\n👤 <b>YAYINCI:</b> @{clean_username}\n💎 <b>ELMAS:</b> {coins}\n\n⚡ <a href='https://www.tiktok.com/@{clean_username}/live'>YAYINA GİT</a>"
    asyncio.create_task(send_telegram(mesaj))

async def init_session_and_get_ticket():
    """Önce sayfayı ziyaret edip oturum açar, sonra bileti (ticket) alır"""
    main_url = "https://dichvu321.com/en/tiktok-treasure-box-bot/"
    proxy_url = "https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live=1000"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": main_url,
        "Origin": "https://dichvu321.com",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # 1. Adım: Ana sayfayı ziyaret et (Çerezleri ve Cloudflare iznini hafızaya al)
        logging.info("Oturum başlatılıyor, ana sayfa ziyaret ediliyor...")
        await asyncio.to_thread(scraper.get, main_url, headers=headers, timeout=15)
        
        # 2. Adım: proxy.php'den bilet iste
        logging.info("Bilet talep ediliyor...")
        res = await asyncio.to_thread(scraper.post, proxy_url, headers=headers, timeout=15)
        
        logging.info(f"Proxy Yanıtı ({res.status_code}): {res.text[:150]}")
        data = res.json()
        
        if data.get("success") and data.get("path"):
            return f"wss://dichvu321.com{data.get('path')}"
    except Exception as e:
        logging.error(f"Oturum/Bilet alma hatası: {e}")
    return None

async def listen_to_feed():
    while True:
        ws_url = await init_session_and_get_ticket()
        if not ws_url:
            logging.warning("Geçerli tünel adresi alınamadı. 5 saniye sonra tekrar deneniyor...")
            await asyncio.sleep(5)
            continue

        logging.info("✅ Canlı WebSocket Tüneline Bağlanılıyor...")
        try:
            ws_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Origin": "https://dichvu321.com"
            }
            
            # Sitenin çerezlerini WebSocket bağlantısına da aktar
            cookie_str = "; ".join([f"{k}={v}" for k, v in scraper.cookies.get_dict().items()])
            if cookie_str:
                ws_headers["Cookie"] = cookie_str

            async with websockets.connect(ws_url, ping_interval=20, extra_headers=ws_headers) as ws:
                logging.info("🚀 TÜNEL AÇILDI! TikTok Canlı Veri Akışı Başladı.")
                
                async for message in ws:
                    msg_str = message.decode('utf-8', 'ignore') if isinstance(message, bytes) else str(message)
                    
                    # Kalp atışı / ping paketlerini atla
                    if msg_str in ["ping", "pong", "{}"]: 
                        continue
                        
                    try:
                        data = json.loads(msg_str)
                        items = data if isinstance(data, list) else [data.get("data", data)]
                        for item in items:
                            if not isinstance(item, dict): continue
                            username = item.get("uniqueId") or item.get("username") or item.get("nickname") or ""
                            coins = next((int(item[k]) for k in ["coins", "diamonds", "totalCoins", "val"] if item.get(k) is not None), 0)
                            box_type = str(item.get("type", "HAZİNE SANDIĞI"))
                            if username and coins > 0:
                                process_item(username, coins, box_type)
                    except Exception:
                        pass
                        
        except Exception as e:
            logging.warning(f"Tünel kapandı veya bilet süresi bitti ({e}). Taze bilet alınıyor...")
            await asyncio.sleep(2)

async def main():
    await send_telegram("🤖 <b>Bot Çekirdeği Başlatıldı!</b> Doğrudan tünel dinleniyor...")
    await listen_to_feed()

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
