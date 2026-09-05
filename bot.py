import os
import json
import re
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

PROCESSED_IDS = set()

def get_country_flag(code):
    """Ülke kodunu (TR, JP, US) bayrak emojisine dönüştürür."""
    if not code or len(str(code)) != 2:
        return "🌐"
    try:
        return chr(ord(code[0].upper()) + 127397) + chr(ord(code[1].upper()) + 127397)
    except Exception:
        return "🌐"

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram BOT_TOKEN veya CHAT_ID eksik!")
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
        logging.info("✅ Telegram mesajı iletildi.")
    except Exception as e:
        logging.error(f"Telegram Gönderim Hatası: {e}")

def process_item(username, coins, box_type="HAZİNE SANDIĞI", viewers=0, country=""):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS:
        return

    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_IDS:
        return
    PROCESSED_IDS.add(dedup_key)

    flag = get_country_flag(country)
    viewers_count = int(viewers) if viewers else 1
    rate = round(coins / viewers_count, 1) if viewers_count > 0 else 1.0
    live_link = f"https://www.tiktok.com/@{clean_username}/live"

    # Görseldeki tasarıma uygun Telegram mesaj şablonu
    mesaj = (
        f"🎁 <b>## {box_type.upper()}</b> > <code>@{clean_username}</code>\n"
        f"💎 <b>ELMAS:</b> {coins} {flag}\n"
        f"👁️ <b>İZLEYİCİ:</b> {viewers_count} 👀\n"
        f"📈 <b>ORAN (Rate):</b> {rate}\n\n"
        f"⚡ <a href='{live_link}'>YAYINA GİT (TikTok)</a>"
    )
    asyncio.create_task(send_telegram(mesaj))
    logging.info(f"🔥 HAZİNE YAKALANDI: @{clean_username} ({coins} Elmas)")

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
            box_type = str(item.get("type") or "TREASURE BOX")
            viewers = item.get("viewers") or item.get("viewerCount") or item.get("userCount") or 0
            country = item.get("country") or item.get("region") or item.get("nation") or ""
            
            process_item(username, coins, box_type, viewers, country)
    except Exception:
        pass

async def scrape_dom_cards(page):
    try:
        cards = await page.query_selector_all("div")
        for card in cards:
            try:
                text = await card.inner_text()
                if "@" in text and ("coin" in text.lower() or "goody" in text.lower() or "treasure" in text.lower()):
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    username = ""
                    coins = 0
                    box_type = "TREASURE BOX"
                    
                    for line in lines:
                        if "@" in line:
                            parts = line.split()
                            for p in parts:
                                if p.startswith("@"):
                                    username = p
                                    break
                        if "coin" in line.lower():
                            m = re.search(r'(\d+)\s*coin', line, re.IGNORECASE)
                            if m:
                                coins = int(m.group(1))
                        if "goody" in line.lower():
                            box_type = "GOODY BAG"
                        elif "treasure" in line.lower():
                            box_type = "TREASURE BOX"
                            
                    if username and coins > 0:
                        process_item(username, coins, box_type)
            except Exception:
                continue
    except Exception as e:
        pass

async def main():
    await send_telegram("🤖 <b>Playwright Bot Aktif!</b> Gelişmiş tasarım modu başlatıldı.")

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
                    parse_and_process(await res.text())
            except Exception:
                pass

        page.on("response", lambda res: asyncio.create_task(on_response(res)))

        def on_websocket(ws):
            logging.info(f"🌐 WebSocket Yakalandı: {ws.url}")
            def on_frame(frame_data):
                payload_str = frame_data.decode('utf-8', errors='ignore') if isinstance(frame_data, bytes) else str(frame_data)
                parse_and_process(payload_str)
            ws.on("framereceived", on_frame)

        page.on("websocket", on_websocket)

        while True:
            try:
                logging.info("🔄 Sayfa yükleniyor...")
                await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
                
                for _ in range(5):
                    await asyncio.sleep(2)
                    await scrape_dom_cards(page)

                logging.info("⏳ Canlı akış dinleniyor (3 dakika)...")
                await asyncio.sleep(180)
            except Exception as e:
                logging.error(f"Döngü Hatası: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
