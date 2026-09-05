import os
import time
import asyncio
import json
import logging
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Render Web Servis Sürdürme Sunucusu
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

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
LIVE_CAPACITY = os.getenv("LIVE_CAPACITY", "1000")

PAGE_URL = "https://dichvu321.com/en/tiktok-treasure-box-bot/"
BOOTSTRAP_URL = f"https://dichvu321.com/proxy.php?transport=ws&mode=bootstrap&stream=box&live={LIVE_CAPACITY}"

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
CACHE_TIMEOUT = 15

http_session = requests.Session()
LOCAL_CACHE = {}

def is_already_taken_by_other_bot(clean_username):
    now = time.time()
    expired_keys = [k for k, v in LOCAL_CACHE.items() if now - v > CACHE_TIMEOUT]
    for k in expired_keys:
        del LOCAL_CACHE[k]

    if clean_username in LOCAL_CACHE:
        return True

    if not UPSTASH_URL or not UPSTASH_TOKEN:
        LOCAL_CACHE[clean_username] = now
        return False

    cache_key = f"hazine:{clean_username}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    try:
        url = f"{UPSTASH_URL}/set/{cache_key}/1/NX/EX/{CACHE_TIMEOUT}"
        response = http_session.get(url, headers=headers, timeout=2)
        if response.ok and response.json().get("result") == "OK":
            LOCAL_CACHE[clean_username] = now
            return False
        return True
    except Exception as e:
        logging.warning(f"Upstash bağlantı hatası: {e}")
        LOCAL_CACHE[clean_username] = now
        return False

def extract_coins(data):
    if not isinstance(data, dict):
        return 0
    for key in ["coins", "diamonds", "totalCoins", "totalCoinsCount", "diamondCount"]:
        val = data.get(key)
        if val is not None:
            try:
                num = int(val)
                if num > 0:
                    return num
            except (ValueError, TypeError):
                pass
    env = data.get("envelopeInfo")
    if isinstance(env, dict):
        for key in ["coins", "diamonds", "totalCoins", "diamondCount"]:
            val = env.get(key)
            if val is not None:
                try:
                    num = int(val)
                    if num > 0:
                        return num
                except (ValueError, TypeError):
                    pass
    return 0

def extract_recipients(data):
    if not isinstance(data, dict):
        return 0
    for key in ["recipients", "people", "peopleCount", "winnerCount", "canOpen"]:
        val = data.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return 0

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
        res = await asyncio.to_thread(http_session.post, url, json=payload, timeout=5)
        if not res.ok:
            logging.error(f"Telegram API Hatası: {res.status_code} - {res.text}")
    except Exception as e:
        logging.error(f"Telegram Gönderim Hatası: {e}")

def get_websocket_ticket():
    """Ana sayfadan çerez alıp bilet isteğini atar, URL ve Çerez başlığını döner."""
    try:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        
        # 1. Oturum çerezlerini oluştur
        http_session.get(PAGE_URL, headers={"User-Agent": user_agent}, timeout=10)

        ajax_headers = {
            "User-Agent": user_agent,
            "Origin": "https://dichvu321.com",
            "Referer": PAGE_URL,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest"
        }

        res = http_session.get(BOOTSTRAP_URL, headers=ajax_headers, timeout=10)
        data = res.json()

        if not data.get("success"):
            res = http_session.post(BOOTSTRAP_URL, headers=ajax_headers, timeout=10)
            data = res.json()

        if data.get("success"):
            path = data.get("path", "").replace("\\/", "/")
            ws_url = f"wss://dichvu321.com{path}"
            
            # Oluşan çerezleri string formatına çevir
            cookies = http_session.cookies.get_dict()
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            return ws_url, cookie_str, user_agent
    except Exception as e:
        logging.error(f"Bilet alma hatası: {e}")
    return None, None, None

async def listen_live_feed():
    while True:
        ws_url, cookie_str, user_agent = await asyncio.to_thread(get_websocket_ticket)
        if not ws_url:
            logging.warning("WebSocket URL alınamadı, 10 saniye sonra tekrar deneniyor...")
            await asyncio.sleep(10)
            continue

        logging.info("WebSocket bağlantısı kuruluyor...")
        
        # 403 engelini aşmak için çerezler ve tarayıcı başlığı ekleniyor
        ws_headers = {
            "User-Agent": user_agent,
            "Origin": "https://dichvu321.com",
            "Cookie": cookie_str
        }
        
        try:
            async with websockets.connect(
                ws_url,
                additional_headers=ws_headers,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:
                logging.info("✅ WebSocket bağlantısı başarılı! Akış dinleniyor...")

                async for message in websocket:
                    try:
                        event_data = json.loads(message)
                    except Exception:
                        continue

                    payload = event_data.get("data") if isinstance(event_data.get("data"), dict) else event_data

                    if not isinstance(payload, dict) or payload.get("status") == "connected":
                        continue

                    box_type_raw = str(payload.get("type") or "").lower()
                    source_raw = str(payload.get("source") or "").lower()
                    if "goody" in box_type_raw or "goody" in source_raw:
                        continue

                    username = (
                        payload.get("uniqueId")
                        or payload.get("username")
                        or payload.get("nickname")
                        or payload.get("author")
                        or ""
                    )
                    clean_username = str(username).replace("@", "").strip().lower()

                    if not clean_username:
                        continue

                    coins = extract_coins(payload)

                    if coins < 30:
                        continue

                    taken = await asyncio.to_thread(is_already_taken_by_other_bot, clean_username)
                    if taken:
                        continue

                    level = payload.get("level", 0)
                    box_title = f"🎁 <b>HAZİNE SANDIĞI</b> (Level {level})" if level else "🎁 <b>HAZİNE SANDIĞI</b>"
                    recipients = extract_recipients(payload)
                    recipients_text = f"{recipients} KİŞİ" if recipients > 0 else "Belirtilmedi"
                    viewers = payload.get("viewers", payload.get("viewerCount", 0))

                    live_link = f"https://www.tiktok.com/@{clean_username}/live"

                    mesaj = (
                        f"{box_title}\n\n"
                        f"👤 <b>YAYINCI:</b> @{clean_username}\n"
                        f"👁️ <b>İZLEYİCİ:</b> {viewers}\n"
                        f"💎 <b>ELMAS:</b> {coins}\n"
                        f"📦 <b>DAĞITILAN:</b> {recipients_text}\n\n"
                        f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
                    )

                    asyncio.create_task(send_telegram(mesaj))
                    logging.info(f"HAZİNE YAKALANDI: @{clean_username} | Elmas: {coins}")

        except Exception as e:
            logging.warning(f"Bağlantı koptu veya hata oluştu: {e}. 3 saniye sonra yeniden bağlanılıyor...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    logging.info("Bot Başlatılıyor...")
    Thread(target=run_dummy_server, daemon=True).start()
    asyncio.run(listen_live_feed())
