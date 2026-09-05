import os, json, re, time, asyncio, logging, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)

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
        await asyncio.to_thread(requests.post, url, json={"chat_id": CHAT_ID, "text": mesaj, "parse_mode": "HTML"}, timeout=5)
    except Exception: pass

def process_item(username, coins, box_type="HAZİNE SANDIĞI", viewers=0):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS: return
    
    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_CACHE and (time.time() - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = time.time()
    if len(PROCESSED_CACHE) > 500: PROCESSED_CACHE.clear()

    mesaj = f"🎁 <b>{box_type.upper()}</b>\n\n👤 <b>YAYINCI:</b> @{clean_username}\n👁️ <b>İZLEYİCİ:</b> {viewers}\n💎 <b>ELMAS:</b> {coins}\n\n⚡ <a href='https://www.tiktok.com/@{clean_username}/live'>YAYINA GİT</a>"
    asyncio.create_task(send_telegram(mesaj))

def parse_and_process(raw_str):
    try:
        data = json.loads(raw_str)
        items = data if isinstance(data, list) else [data.get("data", data)]
        for item in items:
            if not isinstance(item, dict) or item.get("status") == "connected": continue
            username = item.get("uniqueId") or item.get("username") or item.get("nickname") or ""
            coins = next((int(item[k]) for k in ["coins", "diamonds", "totalCoins", "val"] if item.get(k) is not None), 0)
            process_item(username, coins, str(item.get("type", "HAZİNE SANDIĞI")), item.get("viewers", 0))
    except Exception: pass

async def scrape_dom_cards(page):
    try:
        body_text = await page.inner_text("body")
        for chunk in body_text.upper().split("YAYINCI:"):
            if "ELMAS:" in chunk or "COIN:" in chunk:
                user_match = re.search(r'@([A-Z0-9_\.]+)', chunk)
                coin_match = re.search(r'(?:ELMAS|COIN):\s*(\d+)', chunk)
                if user_match and coin_match:
                    process_item(user_match.group(1), int(coin_match.group(1)))
    except Exception: pass

async def main():
    await send_telegram("🤖 <b>Bot Başlatıldı!</b> Bulut engelleri atlanıyor...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        async def on_response(res):
            try:
                if "json" in res.headers.get("content-type", "").lower():
                    text = await res.text()
                    parse_and_process(text)
            except Exception:
                pass

        page.on("response", lambda res: asyncio.create_task(on_response(res)))

        def on_websocket(ws):
            def on_frame(frame_data):
                payload_str = frame_data.decode('utf-8', errors='ignore') if isinstance(frame_data, bytes) else str(frame_data)
                parse_and_process(payload_str)
            ws.on("framereceived", on_frame)

        page.on("websocket", on_websocket)

        await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
        
        title = await page.title()
        if "Just a moment" in title or "Cloudflare" in title:
            await send_telegram("⚠️ <b>DİKKAT:</b> Render IP'si site tarafından (Cloudflare) engellendi! Sayfa açılamıyor.")

        while True:
            await scrape_dom_cards(page)
            await asyncio.sleep(2)

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
