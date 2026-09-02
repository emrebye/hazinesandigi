import asyncio
import json
import os
import re
import socket
import threading
import aiohttp
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# RENDER PORT & HEALTH CHECK
# ============================================================

PORT = int(os.getenv("PORT", "10000"))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Jimin Bot Fast Runner Active!")

    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

# ============================================================
# AYARLAR & UPSTASH REDIS ENTEGRASYONU
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
CHAT_ID = os.getenv("CHAT_ID", "-1004325133382")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

UPSTASH_URL = "https://exotic-javelin-180919.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAsK3AAIgcDFmZGQ3Njk5NjBhODQ0MmY3YTIyNThiZTMzYTU4N2M5Yg"
CACHE_TIMEOUT = 1800

LOCAL_CACHE = set()

# ============================================================
# ASENKRON KİLİT MEKANİZMASI (MİLİSANİYELİK KONTROL)
# ============================================================

async def is_already_taken_by_other_bot(session, clean_username):
    if clean_username in LOCAL_CACHE:
        return True

    cache_key = f"hazine:{clean_username}"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    url = f"{UPSTASH_URL}/set/{cache_key}/1/NX/EX/{CACHE_TIMEOUT}"

    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=1.5)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("result") == "OK":
                    LOCAL_CACHE.add(clean_username)
                    return False
        return True
    except Exception:
        return True

# ============================================================
# TELEGRAM BİLDİRİMİ
# ============================================================

async def send_telegram(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=3)) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"⚠️ Telegram hatası: {e}")
        return False

# ============================================================
# ARAMA VE PARSE FONKSİYONLARI
# ============================================================

def to_int(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        number = int(value)
        if 0 <= number <= 10000:
            return number
    except Exception:
        pass
    return None

def recursive_find_key(obj, wanted_keys, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_normalized = str(key).lower().replace("_", "").replace("-", "")
            current_path = f"{path}.{key}" if path else str(key)
            if key_normalized in wanted_keys:
                number = to_int(value)
                if number is not None:
                    return number, current_path
            result = recursive_find_key(value, wanted_keys, current_path)
            if result[0] is not None:
                return result
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            result = recursive_find_key(item, wanted_keys, f"{path}[{index}]")
            if result[0] is not None:
                return result
    return None, None

def get_chest_recipients(payload):
    key_groups = [
        ["canopen"], ["peoplecount"], ["participantcount"], ["winnercount"],
        ["claimcount"], ["recipientcount"], ["grabcount"], ["membercount"],
        ["people"], ["participants"], ["winners"], ["recipients"]
    ]
    for wanted_keys in key_groups:
        value, path = recursive_find_key(payload, wanted_keys)
        if value is not None:
            return value, path
    return None, None

# ============================================================
# ULTRA HIZLI CANLI AKIŞ
# ============================================================

async def listen_live_feed():
    print("=" * 60)
    print("🚀 HIGH-SPEED TREASURE ALERT (GITHUB/RENDER) BAŞLADI")
    print("=" * 60)

    # Hızlı TCP Soket ayarları
    connector = aiohttp.TCPConnector(
        limit=100,
        ttl_dns_cache=300,
        force_close=False,
        enable_cleanup_closed=True
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            try:
                async with session.get(PROXY_URL, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=4)) as res:
                    data = await res.json()

                if not data.get("success") or not data.get("path"):
                    await asyncio.sleep(0.2)
                    continue

                ws_url = f"wss://dichvu321.com{data.get('path')}"

                # Gecikmeyi önleyen WebSocket konfigürasyonu
                async with websockets.connect(
                    ws_url,
                    additional_headers=HEADERS,
                    ping_interval=10,
                    ping_timeout=4,
                    max_queue=1024,
                    read_limit=2**20
                ) as websocket:

                    print("✅ Hızlı WebSocket Bağlandı.")

                    async for message in websocket:
                        try:
                            event_data = json.loads(message)
                        except Exception:
                            continue

                        payload = event_data.get("data") if isinstance(event_data, dict) and isinstance(event_data.get("data"), dict) else event_data
                        if not isinstance(payload, dict) or payload.get("status") == "connected":
                            continue

                        envelope_info = payload.get("envelopeInfo") if isinstance(payload.get("envelopeInfo"), dict) else {}
                        box_type_raw = str(payload.get("type") or "").lower()
                        source_raw = str(payload.get("source") or "").lower()

                        if envelope_info.get("businessType") == 2 or "goody" in box_type_raw or "goody" in source_raw:
                            continue

                        username = payload.get("uniqueId") or payload.get("nickname") or payload.get("username") or ""
                        clean_username = str(username).replace("@", "").strip().lower()
                        if not clean_username:
                            continue

                        # Asenkron Hızlı Kilit Kontrolü
                        taken = await is_already_taken_by_other_bot(session, clean_username)
                        if taken:
                            continue

                        coins = payload.get("coins") or payload.get("amount") or payload.get("diamond") or payload.get("elmas") or 0
                        try:
                            coins_number = int(coins)
                        except Exception:
                            coins_number = 0

                        if coins_number < 10:
                            continue

                        level = int(payload.get("level", 0) or 0)
                        box_title = f"🎁 HAZİNE SANDIĞI (Level {level})" if level > 0 else "🎁 HAZİNE SANDIĞI"
                        viewers = payload.get("viewerCount") or payload.get("viewers") or payload.get("userCount") or envelope_info.get("viewerCount") or 0
                        recipients, _ = get_chest_recipients(payload)
                        recipients_text = f"{recipients} KİŞİ" if recipients is not None else "BULUNAMADI"
                        live_link = f"https://www.tiktok.com/@{clean_username}/live"

                        mesaj = (
                            f"{box_title}\n"
                            f"👤 YAYINCI: @{clean_username}\n"
                            f"👁️ İZLEYİCİ: {viewers}\n"
                            f"💎 ELMAS: {coins_number}\n"
                            f"📦 DAĞITILAN: {recipients_text}\n"
                            f"🔗 {live_link}"
                        )

                        asyncio.create_task(send_telegram(session, mesaj))
                        print(f"⚡ [HIZLI] GÖNDERİLDİ: @{clean_username} | Elmas: {coins_number}")

            except Exception as e:
                print(f"⚠️ Bağlantı yenileniyor: {e}")
                await asyncio.sleep(0.3)

if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    asyncio.run(listen_live_feed())
