import os, json, re, time, asyncio, logging, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active!")

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
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS: return
    
    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_CACHE and (time.time() - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = time.time()
    if len(PROCESSED_CACHE) > 500: PROCESSED_CACHE.clear()

    mesaj = f"🎁 <b>{box_type.upper()}</b>\n\n👤 <b>YAYINCI:</b> @{clean_username}\n💎 <b>ELMAS:</b> {coins}\n\n⚡ <a href='https://www.tiktok.com/@{clean_username}/live'>YAYINA GİT</a>"
    asyncio.create_task(send_telegram(mesaj))

async def main():
    await send_telegram("🤖 <b>Bot Başlatıldı!</b> Veri tüneli dinleniyor...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-dev-shm-usage", 
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            # WebSocket üzerinden gelen tüm ham verileri doğrudan yakalayan casus dinleyici
            page.on("websocket", lambda ws: ws.on("framereceived", lambda frame: process_ws_data(frame)))

            async def process_ws_data(frame):
                try:
                    text = frame.decode('utf-8', 'ignore') if isinstance(frame, bytes) else str(frame)
                    # Gelen verinin içinde kullanıcı ve coin geçiyorsa ayıkla
                    if "coins" in text or "uniqueId" in text:
                        data = json.loads(text)
                        # Gelen JSON yapısına göre verileri çek
                        username = data.get("uniqueId") or data.get("username") or ""
                        coins = int(data.get("coins", 0) or data.get("diamonds", 0))
                        box_type = str(data.get("type", "HAZİNE SANDIĞI"))
                        if username and coins > 0:
                            process_item(username, coins, box_type)
                except Exception:
                    pass

            await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
            logging.info("WebSocket tüneli dinlemeye başladı...")

            while True:
                # Sayfanın düşmesini engellemek ve oturumu taze tutmak için akıllı döngü
                await asyncio.sleep(150)
                try:
                    logging.info("Oturum tazelemek için sayfa yenileniyor...")
                    await page.reload(wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    pass
                
    except Exception as e:
        logging.error(f"Sistem Hatası: {e}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
