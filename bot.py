import os
import json
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
    logging.info(f"🌐 Dummy Server {port} portunda devrede.")
    server.serve_forever()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "1"))

MAX_PROCESSED_COUNT = 20000
PROCESSED_IDS = OrderedDict()

def to_int(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        num = int(value)
        if 0 <= num <= 2000000:
            return num
    except Exception:
        pass
    return None

def find_deep_value(data, target_keys):
    if isinstance(data, dict):
        for k, v in data.items():
            k_clean = str(k).lower().replace("_", "").replace("-", "")
            if k_clean in target_keys:
                val = to_int(v)
                if val is not None:
                    return val
            res = find_deep_value(v, target_keys)
            if res is not None:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_deep_value(item, target_keys)
            if res is not None:
                return res
    return None

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
        await asyncio.to_thread(requests.post, url, json=payload, timeout=4)
        logging.info("✅ Telegram mesajı iletildi.")
    except Exception as e:
        logging.error(f"Telegram Gönderim Hatası: {e}")

def process_chest_event(payload):
    envelope_info = payload.get("envelopeInfo") or {}
    if not isinstance(envelope_info, dict):
        envelope_info = {}

    username = (
        payload.get("uniqueId")
        or payload.get("nickname")
        or payload.get("username")
        or envelope_info.get("sendUserName")
        or payload.get("author")
        or ""
    )
    clean_username = str(username).replace("@", "").strip().lower()
    if not clean_username:
        return

    # Elmas miktarı
    coins = 0
    coin_keys = ["totaldiamondcount", "diamondcount", "coincount", "totalcoins", "coins", "diamonds", "amount"]
    for k in ["totalDiamondCount", "diamondCount", "coinCount", "coins", "diamonds", "amount", "val"]:
        val = envelope_info.get(k) or payload.get(k)
        num = to_int(val)
        if num is not None and num > 0:
            coins = num
            break
    if coins == 0:
        found_coins = find_deep_value(payload, coin_keys)
        coins = found_coins if found_coins else 0

    if coins < MIN_COINS:
        return

    dedup_key = f"{clean_username}_{coins}"
    if dedup_key in PROCESSED_IDS:
        return
    PROCESSED_IDS[dedup_key] = True
    if len(PROCESSED_IDS) > MAX_PROCESSED_COUNT:
        PROCESSED_IDS.popitem(last=False)

    # İzleyici sayısı
    viewers = 0
    viewer_keys = ["viewercount", "usercount", "roomviewers", "viewers"]
    for k in ["viewerCount", "userCount", "viewers"]:
        val = payload.get(k) or envelope_info.get(k)
        num = to_int(val)
        if num is not None and num > 0:
            viewers = num
            break
    if viewers == 0:
        found_viewers = find_deep_value(payload, viewer_keys)
        viewers = found_viewers if found_viewers else 0

    # Dağıtılacak kişi sayısı
    recipients = None
    recipient_keys = ["peoplecount", "canopen", "winnercount", "claimcount", "recipientcount", "people", "winners", "count"]
    for k in ["peopleCount", "canOpen", "winnerCount", "recipientCount"]:
        val = envelope_info.get(k) or payload.get(k)
        num = to_int(val)
        if num is not None and num > 0:
            recipients = num
            break
    if recipients is None:
        recipients = find_deep_value(payload, recipient_keys)

    # Kalan süre
    countdown_str = None
    time_keys = ["lefttime", "countdown", "duration", "unpacktime", "remaintime"]
    raw_time = None
    for k in ["leftTime", "countdown", "duration", "unpackTime", "remain_time"]:
        val = envelope_info.get(k) or payload.get(k)
        num = to_int(val)
        if num is not None and num > 0:
            raw_time = num
            break
    if raw_time is None:
        raw_time = find_deep_value(payload, time_keys)

    if raw_time:
        dk = raw_time // 60
        sn = raw_time % 60
        countdown_str = f"{dk}dk {sn}sn" if dk > 0 else f"{sn}sn"

    recipients_text = f"{recipients} Kişiye" if recipients is not None else "Bilinmiyor"
    time_line = f"⏳ <b>KALAN SÜRE:</b> {countdown_str}\n" if countdown_str else ""
    live_link = f"https://www.tiktok.com/@{clean_username}/live"

    level = payload.get("level") or envelope_info.get("level", 0)
    title = f"🎁 <b>HAZİNE SANDIĞI (Level {level})</b>" if level else "🎁 <b>HAZİNE SANDIĞI</b>"

    mesaj = (
        f"{title}\n\n"
        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
        f"👁️ <b>İZLEYİCİ:</b> {viewers}\n"
        f"💎 <b>ELMAS:</b> {coins}\n"
        f"👥 <b>DAĞITILAN:</b> {recipients_text}\n"
        f"{time_line}\n"
        f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
    )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_telegram(mesaj))
    except RuntimeError:
        asyncio.run(send_telegram(mesaj))

    logging.info(f"🔥 HAZİNE YAKALANDI: @{clean_username} ({coins} Elmas | {recipients_text} | {viewers} İzleyici)")

def parse_incoming_text(raw_str):
    try:
        data = json.loads(raw_str)
        items = data if isinstance(data, list) else [data.get("data", data)]
        for item in items:
            if isinstance(item, dict) and item.get("status") != "connected":
                process_chest_event(item)
    except Exception:
        pass

async def select_feed_coverage(page):
    try:
        logging.info("🎯 Feed Coverage kontrol ediliyor...")
        select_elem = await page.query_selector("select")
        if select_elem:
            try:
                await page.select_option("select", label="30,000 LIVE")
                logging.info("✅ Menüden 30,000 LIVE seçildi.")
                return
            except Exception:
                pass

        feed_trigger = await page.query_selector("text=FEED COVERAGE")
        if feed_trigger:
            await feed_trigger.click()
            await asyncio.sleep(0.8)

        target_opt = await page.query_selector("text=30,000 LIVE")
        if target_opt:
            await target_opt.click()
            logging.info("✅ Dropdown'dan 30,000 LIVE tıklandı.")
    except Exception as e:
        logging.warning(f"Feed Coverage seçim hatası: {e}")

async def main():
    await send_telegram("🤖 <b>Playwright Bot Başlatıldı!</b> Canlı bağlantı kuruluyor...")

    while True:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # 1. Tarayıcı içinden geçen tüm API / JSON yanıtlarını yakala
                async def on_response(res):
                    try:
                        if "json" in res.headers.get("content-type", "").lower():
                            text = await res.text()
                            parse_incoming_text(text)
                    except Exception:
                        pass

                page.on("response", lambda res: asyncio.create_task(on_response(res)))

                # 2. Tarayıcının siteyle açtığı yasal WebSocket akışını içeriden dinle (Site bot olduğunu anlamaz)
                def on_websocket(ws):
                    logging.info(f"🌐 Canlı WebSocket Yakalandı: {ws.url}")
                    def on_frame(frame_data):
                        payload_str = frame_data.decode('utf-8', errors='ignore') if isinstance(frame_data, bytes) else str(frame_data)
                        parse_incoming_text(payload_str)
                    ws.on("framereceived", on_frame)

                page.on("websocket", on_websocket)

                logging.info("🌐 dichvu321 açılıyor...")
                await page.goto("https://dichvu321.com/en/tiktok-treasure-box-bot/", wait_until="networkidle", timeout=60000)
                
                await asyncio.sleep(5)
                await select_feed_coverage(page)

                logging.info("✅ Sayfa hazır, canlı akış dinleniyor...")

                # Bağlantıyı canlı tut
                while True:
                    await asyncio.sleep(30)
                    # Sayfanın kilitlenmesini önlemek için ufak bir tetikleme
                    await page.evaluate("window.scrollBy(0, 10)")

        except Exception as err:
            logging.error(f"❌ Yeniden başlatılıyor, Hata: {err}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(main())
