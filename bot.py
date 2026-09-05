import os, sys, json, time, asyncio, logging
import cloudscraper
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Aktif!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler).serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "1"))
PROCESSED_CACHE = {}

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        await asyncio.to_thread(scraper.post, url, json={
            "chat_id": CHAT_ID, 
            "text": mesaj, 
            "parse_mode": "HTML", 
            "disable_web_page_preview": True
        }, timeout=8)
    except Exception as e:
        logging.error(f"Telegram Gönderme Hatası: {e}")

def process_item(username, coins, box_type="HAZİNE SANDIĞI", viewers=0):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS: return
    
    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_CACHE and (time.time() - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = time.time()
    if len(PROCESSED_CACHE) > 500: PROCESSED_CACHE.clear()

    logging.info(f"🎯 Sandık Yakalandı: @{clean_username} ({coins} Coin)")
    turkce_tur = "HAZİNE SANDIĞI" if "box" in box_type.lower() else "ŞANSLI KESE"
    mesaj = (
        f"🎁 <b>{turkce_tur}</b>\n\n"
        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
        f"💎 <b>ELMAS:</b> {coins}\n"
        f"👥 <b>İZLEYİCİ:</b> {viewers}\n\n"
        f"⚡ <a href='https://www.tiktok.com/@{clean_username}/live'>YAYINA GİT</a>"
    )
    asyncio.create_task(send_telegram(mesaj))

async def init_session_and_get_ticket():
    main_url = "https://dichvu321.com/en/tiktok-treasure-box-bot/"
    
    # Tarayıcının gönderdiği tam parametreler
    proxy_url = "https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live=1000&demo=true"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": main_url,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    try:
        logging.info("1️⃣ Ana sayfaya gidiliyor...")
        r1 = await asyncio.to_thread(scraper.get, main_url, headers=headers, timeout=15)
        
        logging.info("2️⃣ proxy.php'den bilet isteniyor (GET)...")
        # POST yerine GET kullanıyoruz
        r2 = await asyncio.to_thread(scraper.get, proxy_url, headers=headers, timeout=15)
        logging.info(f"2️⃣ Bilet yanıt kodu: {r2.status_code}")
        logging.info(f"2️⃣ Bilet ham yanıtı: {r2.text[:150]}")
        
        data = r2.json()
        if data.get("success") and data.get("path"):
            return f"wss://dichvu321.com{data.get('path')}"
        else:
            logging.warning(f"⚠️ Bilet reddedildi: {data}")
    except Exception as e:
        logging.error(f"❌ Oturum hatası: {e}")
    return None

async def listen_to_feed():
    while True:
        ws_url = await init_session_and_get_ticket()
        if not ws_url:
            logging.warning("⏳ Bilet alınamadı. 5 saniye sonra tekrar deneniyor...")
            await asyncio.sleep(5)
            continue

        try:
            ws_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Origin": "https://dichvu321.com"
            }
            cookie_str = "; ".join([f"{k}={v}" for k, v in scraper.cookies.get_dict().items()])
            if cookie_str:
                ws_headers["Cookie"] = cookie_str

            async with websockets.connect(ws_url, ping_interval=20, extra_headers=ws_headers) as ws:
                logging.info("🚀 TÜNEL AÇILDI! TikTok Canlı Veri Akışı Başladı.")
                
                async for message in ws:
                    msg_str = message.decode('utf-8', 'ignore') if isinstance(message, bytes) else str(message)
                    if msg_str in ["ping", "pong", "{}"]: continue
                    
                    try:
                        data = json.loads(msg_str)
                        
                        # Kiwi'de yakaladığımız demoEvents/events yapısı
                        items = []
                        if isinstance(data, dict):
                            if "events" in data and isinstance(data["events"], list):
                                items = data["events"]
                            elif "data" in data:
                                items = data["data"] if isinstance(data["data"], list) else [data["data"]]
                            else:
                                items = [data]
                        elif isinstance(data, list):
                            items = data
                            
                        for item in items:
                            if not isinstance(item, dict): continue
                            username = item.get("uniqueId") or item.get("username") or ""
                            coins = int(item.get("coins", 0) or item.get("diamonds", 0))
                            box_type = str(item.get("type", "box"))
                            viewers = int(item.get("viewerCount", 0))
                            
                            if username and coins > 0:
                                process_item(username, coins, box_type, viewers)
                    except Exception:
                        pass
                        
        except Exception as e:
            logging.warning(f"⚠️ Tünel koptu ({e}). Yeniden bağlanılacak...")
            await asyncio.sleep(3)

async def main():
    logging.info("🏁 Bot başlatıldı.")
    await send_telegram("🤖 <b>Bot Çekirdeği Başlatıldı!</b> Canlı sandık akışı devrede...")
    await listen_to_feed()

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
