import os
import json
import re
import time
import asyncio
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active!")

    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    logging.info(f"🌐 Dummy HTTP Server {port} portunda çalışıyor.")
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "1"))

PROCESSED_CACHE = {}

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        await asyncio.to_thread(requests.post, url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram Gönderim Hatası: {e}")

def process_item(username, coins, box_type="HAZİNE SANDIĞI", viewers=0):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS:
        return

    dedup_key = f"{clean_username}_{coins}"
    current_time = time.time()

    if dedup_key in PROCESSED_CACHE and (current_time - PROCESSED_CACHE[dedup_key]) < 60:
        return

    PROCESSED_CACHE[dedup_key] = current_time

    if len(PROCESSED_CACHE) > 500:
        PROCESSED_CACHE.clear()

    live_link = f"https://www.tiktok.com/@{clean_username}/live"
    mesaj = (
        f"🎁 <b>{box_type.upper()}</b>\n\n"
        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
        f"👁️ <b>İZLEYİCİ:</b> {viewers}\n"
        f"💎 <b>ELMAS:</b> {coins}\n\n"
        f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
    )
    asyncio.create_task(send_telegram(mesaj))
    logging.info(f"🔥 YAKALANDI: @{clean_username} ({coins} Elmas)")

def parse_and_process(raw_str):
    try:
        data = json.loads(raw_str)
        items = data if isinstance(data, list) else [data.get("data", data)]
        for item in items:
            if not isinstance(item, dict) or item.get("status") == "connected":
                continue
            username = item.get("uniqueId") or item.get("username") or item.get("nickname") or item.get("author") or ""
            coins = 0
            for k in ["coins", "diamonds", "totalCoins", "val", "amount"]:
                if item.get(k) is not None:
                    try:
                        coins = int(item[k])
                        break
                    except (ValueError, TypeError):
                        pass
            box_type = str(item.get("type") or "HAZİNE SANDIĞI")
            viewers = item.get("viewers", item.get("viewerCount", 0))
            process_item(username, coins, box_type, viewers)
    except Exception:
        pass

async def scrape_dom_cards(page):
    try:
        body_text = await page.inner_text("body")
        for chunk in body_text.upper().split("YAYINCI:"):
            if "ELMAS:" in chunk or "COIN:" in chunk or "DIAMOND:" in chunk:
                user_match = re.search(r'@([A-Z0-9_\.]+)', chunk)
                coin_match = re.search(r'(?:ELMAS|COIN|DIAMOND):\s*(\d+)', chunk)
                if user_match and coin_match:
                    process_item(user_match.group(1), int(coin_match.group(1)))
    except Exception:
        pass

async def main():
    await send_telegram("🤖 <b>Playwright Bot Başlatıldı!</b> Hızlı tarama modunda izleniyor...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
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
        
        while True:
            await scrape_dom_cards(page)
            await asyncio.sleep(2) 

if __name__ == "__main__":
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
