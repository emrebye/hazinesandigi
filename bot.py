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

def parse_and_process(raw_str):
    try:
        data = json.loads(raw_str)
        items = data if isinstance(data, list) else [data.get("data", data)]
        for item in items:
            if not isinstance(item, dict) or item.get("status") == "connected": continue
            username = item.get("uniqueId") or item.get("username") or item.get("nickname") or ""
            coins = next((int(item[k]) for k in ["coins", "diamonds", "totalCoins", "val"] if item.get(k) is not None), 0)
            process_item(username, coins, str(item.get("type", "HAZİNE SANDIĞI")))
    except Exception: pass

async def scrape_dom_cards(page):
    try:
        body_text = await page.inner_text("body")
        parts = body_text.split('@')
        
        for i in range(1, len(parts)):
            chunk_before = parts[i-1][-150:] 
            chunk_after = parts[i][:100] 
            
            logging.info(f"🔍 BOTUN GÖRDÜĞÜ METİN -> ÖNCE: {chunk_before.strip()} | SONRA: {chunk_after.strip()}")
            
            user_match = re.search(r'^([a-zA-Z0-9_\.]+)', chunk_after)
            coin_match = re.search(r'(\d+)\s*(?:coins?|elmas|diamonds?)', chunk_before, re.IGNORECASE)
            
            if user_match and coin_match:
                username = user_match.group(1)
                coins = int(coin_match.group(1))
                box_type = "GOODY BAG" if "GOODY BAG" in chunk_before.upper() else "HAZİNE SANDIĞI"
                process_item(username, coins, box_type)
            else:
                logging.warning(f"❌ Eşleşme Başarısız! Bulunan User: {user_match}, Bulunan Coin: {coin_match}")
    except Exception: pass

async def main():
    await send_telegram("🤖 <b>Bot Başlatıldı!</b> Sistem hazır...")
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

            async def on_response(res):
                try:
                    if "json" in res.headers.get("content-type", "").lower():
                        text = await res.text()
                        parse_and_process(text)
                except Exception: pass

            page.on("response", lambda res: asyncio.create_task(on_response(res)))

            def on_websocket(ws):
                ws.on("framereceived", lambda f: parse_and_process(f.decode('utf-8', 'ignore') if isinstance(f, bytes) else str(f)))

            page.on("websocket", on_websocket)

            await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
            
            title = await page.title()
            if "Just a moment" in title or "Cloudflare" in title:
                await send_telegram("⚠️ <b>DİKKAT:</b> Render IP'si site tarafından engellendi!")

            logging.info("Taramaya başlandı...")
            dongu_sayaci = 0
            
            while True:
                await scrape_dom_cards(page)
                await asyncio.sleep(2)
                
                dongu_sayaci += 1
                if dongu_sayaci >= 150:
                    logging.info("♻️ Oturum süresi doldu, sayfa yenileniyor (Demo engeli aşıldı)...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        logging.warning(f"Sayfa yenilenirken gecikme oldu: {e}")
                    dongu_sayaci = 0
                
    except Exception as e:
        logging.error(f"Sistem Hatası: {e}")
        await send_telegram(f"⚠️ Bot çöktü: {e}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
