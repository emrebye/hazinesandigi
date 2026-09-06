import os
import json
import re
import asyncio
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from collections import OrderedDict
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

MAX_PROCESSED_COUNT = 20000
PROCESSED_IDS = OrderedDict()

# --- ATTIĞIN KODDAN ALINAN PARSE VE DERİN ARAMA MOTORU ---

def to_int(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        number = int(value)
        if 0 <= number <= 1000000:
            return number
    except Exception:
        pass
    return None

def recursive_find_key(obj, wanted_keys):
    """İç içe geçen JSON içinde hedeflenen anahtarları özyinelemeli arar."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_normalized = str(key).lower().replace("_", "").replace("-", "")
            if key_normalized in wanted_keys:
                number = to_int(value)
                if number is not None:
                    return number
            result = recursive_find_key(value, wanted_keys)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = recursive_find_key(item, wanted_keys)
            if result is not None:
                return result
    return None

def get_chest_coins(payload, envelope_info):
    coin_keys = ["totaldiamondcount", "diamondcount", "coincount", "totalcoins", "coins", "diamonds", "amount"]
    for key in ["coins", "diamonds", "totalCoins", "val", "amount", "totalDiamondCount"]:
        val = envelope_info.get(key) or payload.get(key)
        num = to_int(val)
        if num is not None and num > 0:
            return num
    val = recursive_find_key(payload, coin_keys)
    return val if val is not None else 0

def get_chest_recipients(payload, envelope_info):
    """Kutunun kaç kişiye dağıtılacağını tespit eder."""
    recipient_keys = [
        "canopen", "peoplecount", "participantcount", "winnercount",
        "claimcount", "recipientcount", "grabcount", "membercount",
        "people", "participants", "winners", "recipients", "slots", "count"
    ]
    for key in ["peopleCount", "canOpen", "winners", "recipientCount", "people"]:
        val = envelope_info.get(key) or payload.get(key)
        num = to_int(val)
        if num is not None and num > 0:
            return num
    return recursive_find_key(payload, recipient_keys)

def get_chest_countdown(payload, envelope_info):
    """Kutunun açılmasına kalan süreyi tespit eder."""
    time_keys = ["lefttime", "countdown", "duration", "remaintime", "time", "unpacktime"]
    for key in ["leftTime", "countdown", "duration", "remain_time", "time"]:
        val = envelope_info.get(key) or payload.get(key)
        num = to_int(val)
        if num is not None and num > 0:
            dakika = num // 60
            saniye = num % 60
            return f"{dakika}dk {saniye}sn" if dakika > 0 else f"{saniye}sn"
    val = recursive_find_key(payload, time_keys)
    if val is not None and val > 0:
        dakika = val // 60
        saniye = val % 60
        return f"{dakika}dk {saniye}sn" if dakika > 0 else f"{saniye}sn"
    return None

# --- MESAJLAŞMA VE TETİKLEME ---

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
        await asyncio.to_thread(requests.post, url, json=payload, timeout=4)
        logging.info("✅ Telegram mesajı iletildi.")
    except Exception as e:
        logging.error(f"Telegram Gönderim Hatası: {e}")

def process_item(username, coins, box_type="HAZİNE SANDIĞI", viewers=0, recipients=None, countdown=None):
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username or coins < MIN_COINS:
        return

    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_IDS:
        return
    PROCESSED_IDS[dedup_key] = True

    if len(PROCESSED_IDS) > MAX_PROCESSED_COUNT:
        PROCESSED_IDS.popitem(last=False)

    live_link = f"https://www.tiktok.com/@{clean_username}/live"
    recipients_text = f"{recipients} Kişiye" if recipients is not None else "Bilinmiyor"
    time_text = f"\n⏳ <b>SÜRE:</b> {countdown}" if countdown else ""

    mesaj = (
        f"🎁 <b>{box_type.upper()}</b>\n\n"
        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
        f"👁️ <b>İZLEYİCİ:</b> {viewers}\n"
        f"💎 <b>ELMAS:</b> {coins}\n"
        f"👥 <b>DAĞITILAN:</b> {recipients_text}"
        f"{time_text}\n\n"
        f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
    )
    
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_telegram(mesaj))
    except RuntimeError:
        asyncio.run(send_telegram(mesaj))

    logging.info(f"🔥 HAZİNE YAKALANDI: @{clean_username} ({coins} Elmas | {recipients_text} | {viewers} İzleyici)")

def parse_and_process(raw_str):
    try:
        event_data = json.loads(raw_str)
        items = event_data if isinstance(event_data, list) else [event_data.get("data", event_data)]
        
        for payload in items:
            if not isinstance(payload, dict) or payload.get("status") == "connected":
                continue

            envelope_info = payload.get("envelopeInfo") or {}
            if not isinstance(envelope_info, dict):
                envelope_info = {}

            # Goody Bag eleme filtresi (Attığın koddaki gibi)
            box_type_raw = str(payload.get("type") or "").lower()
            source_raw = str(payload.get("source") or "").lower()
            business_type = envelope_info.get("businessType", 1)
            if business_type == 2 or "goody" in box_type_raw or "goody" in source_raw:
                continue

            username = (
                payload.get("uniqueId")
                or payload.get("nickname")
                or payload.get("username")
                or payload.get("author")
                or ""
            )

            # Elmas hesaplama
            coins = get_chest_coins(payload, envelope_info)

            # Dağıtılacak kişi sayısı
            recipients = get_chest_recipients(payload, envelope_info)

            # Kalan süre
            countdown = get_chest_countdown(payload, envelope_info)

            # İzleyici sayısı
            viewers = (
                payload.get("viewerCount")
                or payload.get("userCount")
                or payload.get("viewers")
                or envelope_info.get("viewerCount")
                or 0
            )

            level = payload.get("level", 0)
            box_title = f"HAZİNE SANDIĞI (Level {level})" if level else "HAZİNE SANDIĞI"

            process_item(username, coins, box_title, viewers, recipients, countdown)
    except Exception:
        pass

async def scrape_dom_cards(page):
    try:
        cards = await page.query_selector_all("div")
        for card in cards:
            text = await card.inner_text()
            if ("coins" in text.lower() or "treasure box" in text.lower()) and "@" in text:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                username = ""
                coins = 0
                recipients = None
                countdown = None
                
                for line in lines:
                    if "@" in line:
                        parts = line.split()
                        if parts:
                            username = parts[0]
                    if "coin" in line.lower():
                        m = re.search(r'(\d+)\s*coin', line, re.IGNORECASE)
                        if m:
                            coins = int(m.group(1))
                    
                    time_match = re.search(r'(\d{1,2}:\d{2})', line)
                    if time_match:
                        countdown = time_match.group(1)

                    people_match = re.search(r'(\d+)\s*(people|user|winner|kişi)', line, re.IGNORECASE)
                    if people_match:
                        recipients = int(people_match.group(1))

                if username and coins > 0:
                    process_item(username, coins, "HAZİNE SANDIĞI", 0, recipients, countdown)
    except Exception:
        pass

async def select_feed_coverage(page):
    try:
        logging.info("🎯 Feed Coverage seçimi kontrol ediliyor...")
        select_elem = await page.query_selector("select")
        if select_elem:
            try:
                await page.select_option("select", label="30,000 LIVE")
                logging.info("✅ <select> üzerinden 30,000 LIVE seçildi.")
                return
            except Exception:
                pass

        feed_trigger = await page.query_selector("text=FEED COVERAGE")
        if feed_trigger:
            await feed_trigger.click()
            await asyncio.sleep(0.8)

        target_option = await page.query_selector("text=30,000 LIVE")
        if target_option:
            await target_option.click()
            logging.info("✅ Dropdown üzerinden '30,000 LIVE' seçildi.")
    except Exception as e:
        logging.warning(f"Feed coverage seçiminde hata: {e}")

async def main():
    await send_telegram("🤖 <b>Playwright Bot Başlatıldı!</b> Canlı ve sayfa verileri izleniyor...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
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

            logging.info("dichvu321 sayfasına bağlanılıyor...")
            await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="domcontentloaded", timeout=60000)
            
            await asyncio.sleep(6)
            await select_feed_coverage(page)
            await asyncio.sleep(2)

            await scrape_dom_cards(page)

            while True:
                await asyncio.sleep(20)
                await scrape_dom_cards(page)

    except Exception as err:
        logging.error(f"❌ Playwright Hatası: {err}", exc_info=True)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
