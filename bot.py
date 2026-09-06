import os
import json
import asyncio
import logging
import requests
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Render Environment Variables üzerinden okunur
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MIN_COINS = int(os.getenv("MIN_COINS", "5"))

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
    logging.warning("⚠️ UYARI: BOT_TOKEN veya CHAT_ID ortam değişkeni ayarlanmamış!")

BASE_URL = "https://dichvu321.com"
PAGE_URL = f"{BASE_URL}/en/tiktok-treasure-box-bot/"
PROXY_URL = f"{BASE_URL}/proxy.php"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Origin": BASE_URL,
    "Referer": PAGE_URL,
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

LOCAL_KEYS = set()

def is_seen(key):
    """Sandık daha önce görüldü mü kontrol eder (Upstash Redis + Lokal Yedek)."""
    if key in LOCAL_KEYS:
        return True

    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            # SET key 1 NX EX 86400 (Sadece yoksa yazar ve 24 saat saklar)
            req_url = f"{UPSTASH_URL}/set/{key}/1/nx/ex/86400"
            headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
            res = requests.get(req_url, headers=headers, timeout=3).json()
            if res.get("result") is None:
                return True
        except Exception as e:
            logging.error(f"Redis Hatası: {e}")

    LOCAL_KEYS.add(key)
    if len(LOCAL_KEYS) > 10000:
        LOCAL_KEYS.clear()
    return False

def send_telegram(mesaj):
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
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram Hatası: {e}")

def get_ticket(session):
    session.get(PAGE_URL, headers=BROWSER_HEADERS, timeout=10)
    params = {
        "transport": "ws",
        "mode": "bootstrap",
        "stream": "all",
        "live": "30000"
    }
    res = session.post(PROXY_URL, params=params, headers=FETCH_HEADERS, timeout=10)
    try:
        data = res.json()
        if data.get("success") and "path" in data:
            return data["path"], session.cookies.get_dict()
    except Exception as e:
        logging.error(f"Bilet Ayrıştırma Hatası: {e}")
    return None, None

async def connect_ws(ws_url, ws_headers):
    try:
        return await websockets.connect(ws_url, additional_headers=ws_headers, ping_interval=20, ping_timeout=20)
    except TypeError:
        try:
            return await websockets.connect(ws_url, extra_headers=ws_headers, ping_interval=20, ping_timeout=20)
        except TypeError:
            return await websockets.connect(ws_url, ping_interval=20, ping_timeout=20)

async def run_bot():
    send_telegram("🚀 <b>TikTok Sandık Botu Devrede!</b>\nUpstash Redis & 30.000+ Canlı Yayın Aktif...")
    session = requests.Session()

    while True:
        try:
            logging.info("🎫 Bilet talep ediliyor...")
            path, cookies = await asyncio.to_thread(get_ticket, session)

            if not path:
                logging.warning("⚠️ Bilet alınamadı, 4 saniye sonra tekrar deneniyor...")
                await asyncio.sleep(4)
                continue

            ws_url = f"wss://dichvu321.com{path}"
            logging.info("🎯 Bilet alındı, WebSocket bağlanıyor...")

            cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            ws_headers = {
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Origin": BASE_URL,
                "Cookie": cookie_header
            }

            ws = await connect_ws(ws_url, ws_headers)
            async with ws:
                logging.info("✅ Canlı WebSocket bağlı! Sandıklar yakalanıyor...")
                while True:
                    msg = await ws.recv()
                    try:
                        raw = json.loads(msg)
                        msg_type = raw.get("type")

                        if msg_type == "ready":
                            covered = raw.get("data", {}).get("coveredLive", 0)
                            logging.info(f"💓 Aktif Dinlenen Canlı Yayın: {covered}")
                            continue

                        if msg_type == "demoEvents" and isinstance(raw.get("events"), list):
                            for item in raw["events"]:
                                username = item.get("uniqueId")
                                if not username:
                                    continue

                                coins = int(item.get("coins") or 0)
                                if coins < MIN_COINS:
                                    continue

                                timestamp = item.get("timestamp", 0)
                                key = f"box:{username}:{coins}:{timestamp}"

                                # Upstash Redis üzerinden mükerrer kontrolü
                                if is_seen(key):
                                    continue

                                can_open = item.get("canOpen", 0)
                                viewers = item.get("viewerCount", 0)
                                level = item.get("level", 0)
                                b_type = item.get("businessType", 0)
                                event_type = item.get("type", "box")

                                if event_type == "goody_bag":
                                    box_name = f"🎁 GOODY BAG (Lvl {level})"
                                elif b_type == 4:
                                    box_name = "👑 ALTIN SANDIK"
                                else:
                                    box_name = "📦 HAZİNE SANDIĞI"

                                live_link = f"https://www.tiktok.com/@{username}/live"
                                viewers_str = f"👁️ <b>İzleyici:</b> {viewers}\n" if viewers else ""
                                people_str = f"👥 <b>Kişi Sayısı:</b> {can_open}\n" if can_open else ""

                                mesaj = (
                                    f"✨ <b>{box_name}</b>\n\n"
                                    f"👤 <b>Yayıncı:</b> @{username}\n"
                                    f"💎 <b>Coin:</b> {coins}\n"
                                    f"{people_str}"
                                    f"{viewers_str}\n"
                                    f"⚡ <a href='{live_link}'>YAYINA GİT</a>"
                                )
                                send_telegram(mesaj)
                                logging.info(f"🔥 TELEGRAMA İLETİLDİ: @{username} ({coins} Coin)")

                    except Exception as err:
                        logging.error(f"Ayrıştırma hatası: {err}")

        except Exception as e:
            logging.error(f"Soket döngüsü koptu: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(run_bot())
