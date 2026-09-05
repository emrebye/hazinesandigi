import os
import json
import asyncio
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "5"))

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
    server.serve_forever()

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

def parse_and_process(message_str):
    try:
        event_data = json.loads(message_str)
        payload = event_data.get("data") if isinstance(event_data.get("data"), dict) else event_data

        if not isinstance(payload, dict) or payload.get("status") == "connected":
            return None

        username = (
            payload.get("uniqueId")
            or payload.get("username")
            or payload.get("nickname")
            or payload.get("author")
            or payload.get("anchor")
            or payload.get("host")
            or ""
        )
        clean_username = str(username).replace("@", "").strip().lower()
        if not clean_username:
            return None

        coins = 0
        for key in ["coins", "diamonds", "totalCoins", "val", "amount"]:
            if payload.get(key) is not None:
                try:
                    coins = int(payload[key])
                    break
                except (ValueError, TypeError):
                    pass

        if coins < MIN_COINS:
            return None

        return clean_username, coins, payload
    except Exception:
        return None

async def main():
    await send_telegram("🤖 <b>Playwright Bot Başlatıldı!</b> Gerçek Chrome tarayıcısı açılıyor...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        def on_websocket(ws):
            logging.info(f"🌐 WebSocket Yakalandı: {ws.url}")

            def on_frame_received(frame):
                try:
                    payload_str = frame.text if isinstance(frame.text, str) else frame.payload.decode('utf-8', errors='ignore')
                    res = parse_and_process(payload_str)
                    if res:
                        clean_username, coins, data = res
                        box_type = str(data.get("type") or "HAZİNE SANDIĞI").upper()
                        viewers = data.get("viewers", payload.get("viewerCount", 0))
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
                except Exception as e:
                    logging.error(f"Frame işleme hatası: {e}")

            ws.on("framereceived", on_frame_received)

        page.on("websocket", on_websocket)

        logging.info("dichvu321 sayfasına bağlanılıyor...")
        await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
        
        while True:
            await asyncio.sleep(60)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
