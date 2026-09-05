import os
import json
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

# Tekrarlanan bildirimleri engellemek için hafıza listesi
PROCESSED_IDS = set()

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

def process_single_item(item):
    if not isinstance(item, dict):
        return

    # Benzersiz ID kontrolü (Aynı sandığı tekrar atmamak için)
    event_id = item.get("id") or item.get("_id") or item.get("time") or item.get("uniqueId")
    username = (
        item.get("uniqueId")
        or item.get("username")
        or item.get("nickname")
        or item.get("author")
        or item.get("anchor")
        or item.get("host")
        or ""
    )
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username:
        return

    coins = 0
    for key in ["coins", "diamonds", "totalCoins", "val", "amount"]:
        if item.get(key) is not None:
            try:
                coins = int(item[key])
                break
            except (ValueError, TypeError):
                pass

    if coins < MIN_COINS:
        return

    dedup_key = f"{clean_username}_{coins}_{event_id}"
    if dedup_key in PROCESSED_IDS:
        return
    PROCESSED_IDS.add(dedup_key)

    box_type = str(item.get("type") or "HAZİNE SANDIĞI").upper()
    viewers = item.get("viewers", item.get("viewerCount", 0))
    live_link = f"https://www.tiktok.com/@{clean_username}/live"

    mesaj = (
        f"🎁 <b>{box_type}</b>\n\n"
        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
        f"👁️ <b>İZLEYİCİ:</b> {viewers}\n"
        f"💎 <b>ELMAS:</b> {coins}\n\n"
        f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
    )
    asyncio.create_task(send_telegram(mesaj))
    logging.info(f"🔥 HAZİNE YAKALANDI: @{clean_username} ({coins} Elmas)")

def parse_and_process(raw_str):
    try:
        data = json.loads(raw_str)
        
        # Liste halinde geldiyse (Recent events gibi)
        if isinstance(data, list):
            for item in data:
                process_single_item(item)
            return

        # Tekil obje geldiyse
        if isinstance(data, dict):
            payload = data.get("data")
            if isinstance(payload, list):
                for item in payload:
                    process_single_item(item)
            elif isinstance(payload, dict):
                process_single_item(payload)
            else:
                process_single_item(data)
    except Exception:
        pass

async def main():
    await send_telegram("🤖 <b>Playwright Bot Başlatıldı!</b> Sayfa verileri ve canlı akış izleniyor...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1. HTTP İsteklerini Yakalama (Sayfa açıldığında gelen "Recent events" API verileri için)
        async def on_response(response):
            try:
                if "json" in response.headers.get("content-type", "").lower():
                    text = await response.text()
                    parse_and_process(text)
            except Exception:
                pass

        page.on("response", lambda res: asyncio.create_task(on_response(res)))

        # 2. WebSocket Yakalama (Anlık gelen canlı sandıklar için)
        def on_websocket(ws):
            logging.info(f"🌐 WebSocket Yakalandı: {ws.url}")

            def on_frame_received(frame_data):
                try:
                    payload_str = frame_data.decode('utf-8', errors='ignore') if isinstance(frame_data, bytes) else str(frame_data)
                    parse_and_process(payload_str)
                except Exception as e:
                    logging.error(f"Frame hatası: {e}")

            ws.on("framereceived", on_frame_received)

        page.on("websocket", on_websocket)

        logging.info("dichvu321 sayfasına bağlanılıyor...")
        await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="networkidle", timeout=60000)
        
        while True:
            await asyncio.sleep(60)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
