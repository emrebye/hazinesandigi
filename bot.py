import asyncio
import json
import os
import re
import threading
import requests
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
        self.wfile.write(b"Treasure Alert is running")

    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Render PORT açıldı: {PORT}")
    server.serve_forever()

# ============================================================
# AYARLAR VE HTTP SESSION
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
CHAT_ID = os.getenv("CHAT_ID", "-1004325133382")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

# ------------------------------------------------------------
# UPSTASH REDIS (TERMUX İLE %100 ORTAK KİLİT NOKTASI)
# ------------------------------------------------------------
UPSTASH_URL = "https://exotic-javelin-180919.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAAsK3AAIgcDFmZGQ3Njk5NjBhODQ0MmY3YTIyNThiZTMzYTU4N2M5Yg"

CACHE_TIMEOUT = 1800  # 30 dakika (Termux ile aynı olmalı)

http_session = requests.Session()
LOCAL_CACHE = set()

# ============================================================
# TERMUX İLE UYUMLU ATOMİK UPSTASH KİLİDİ
# ============================================================

def check_and_save_cache(cache_key):
    """
    Termux ve Render bu fonksiyon üzerinden tam senkronize olur.
    İki taraftan hangisi önce varırsa 'OK' alır ve mesajı atar.
    Diğeri 'null' alır ve mesajı SESSİZCE İPTAL EDER.
    """
    if cache_key in LOCAL_CACHE:
        return True

    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}"
    }

    try:
        # Standart REST endpoint formatı
        url = f"{UPSTASH_URL}/set/{cache_key}/1/NX/EX/{CACHE_TIMEOUT}"
        response = http_session.get(url, headers=headers, timeout=2)

        if response.ok:
            result = response.json().get("result")
            if result == "OK":
                LOCAL_CACHE.add(cache_key)
                return False  # Kilit başarıyla alındı -> Telegram'a GÖNDER

        # Zaten bulut veritabanında kilitli -> ENGELLE
        return True

    except Exception as e:
        print(f"⚠️ Upstash Kilit Hatası (GitHub/Render): {e}")
        # Bağlantı koptuğunda çift mesajı önlemek adına kilitli kabul et
        return True

# ============================================================
# TELEGRAM BİLDİRİMİ
# ============================================================

async def send_telegram(mesaj):
    if not TELEGRAM_BOT_TOKEN:
        print("❌ BOT_TOKEN bulunamadı!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: http_session.post(url, json=payload, timeout=3)
        )
        return response.ok
    except Exception as e:
        print(f"⚠️ Telegram hatası: {e}")
        return False

# ============================================================
# CANLI AKIŞ İŞLEME
# ============================================================

async def listen_live_feed():
    print("🚀 GITHUB / RENDER BOTU BAŞLADI")
    print("☁️ Upstash Senkronizasyonu: AKTİF")

    while True:
        try:
            loop = asyncio.get_running_loop()

            res = await loop.run_in_executor(
                None,
                lambda: http_session.get(PROXY_URL, headers=HEADERS, timeout=4)
            )

            data = res.json()
            if not data.get("success") or not data.get("path"):
                await asyncio.sleep(0.5)
                continue

            ws_url = f"wss://dichvu321.com{data.get('path')}"

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=15,
                ping_timeout=5
            ) as websocket:

                print("✅ WebSocket bağlandı - Dinleniyor...")

                async for message in websocket:
                    try:
                        event_data = json.loads(message)
                    except Exception:
                        continue

                    payload = event_data.get("data") if isinstance(event_data.get("data"), dict) else event_data
                    if not isinstance(payload, dict) or payload.get("status") == "connected":
                        continue

                    # Goody Bag Filtresi
                    box_type_raw = str(payload.get("type") or "").lower()
                    source_raw = str(payload.get("source") or "").lower()
                    envelope_info = payload.get("envelopeInfo") if isinstance(payload.get("envelopeInfo"), dict) else {}
                    
                    if envelope_info.get("businessType") == 2 or "goody" in box_type_raw or "goody" in source_raw:
                        continue

                    # Elmas Sayısı
                    try:
                        coins_number = int(payload.get("coins", 0))
                    except Exception:
                        coins_number = 0

                    if coins_number <= 0:
                        continue

                    # Kullanıcı Adı Temizleme
                    username = payload.get("uniqueId") or payload.get("nickname") or payload.get("username") or ""
                    clean_username = re.sub(r'\s+', '', str(username)).replace("@", "").strip().lower()
                    if not clean_username:
                        continue

                    # Dağıtılan Kişi Sayısı
                    try:
                        recipients_number = int(payload.get("canOpen", 0))
                    except Exception:
                        recipients_number = 0

                    # ============================================================
                    # TERMUX İLE BİREBİR ORTAK KEY FORMATI
                    # (Termux da tam olarak bu isimle kaydetmeli)
                    # ============================================================
                    cache_key = f"hazine:{clean_username}"

                    duplicate = await asyncio.to_thread(check_and_save_cache, cache_key)
                    if duplicate:
                        print(f"⏭️ MÜKERRER (Termux veya Render Tarafından Kilitli): @{clean_username}")
                        continue

                    # Mesaj İçeriği
                    try:
                        level = int(payload.get("level", 0))
                    except Exception:
                        level = 0

                    box_title = f"🎁 HAZİNE SANDIĞI (Level {level})" if level > 0 else "🎁 HAZİNE SANDIĞI"
                    viewers = payload.get("viewerCount") or payload.get("userCount") or envelope_info.get("viewerCount") or 0
                    live_link = f"https://www.tiktok.com/@{clean_username}/live"

                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: `@{clean_username}`\n"
                        f"👁️ İZLEYİCİ: {viewers}\n"
                        f"💎 ELMAS: {coins_number}\n"
                        f"📦 DAĞITILAN: {recipients_number} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    asyncio.create_task(send_telegram(mesaj))
                    print(f"✅ GÖNDERİLDİ (GitHub/Render): @{clean_username} | Elmas: {coins_number}")

        except Exception as e:
            print(f"⚠️ BAĞLANTI HATASI: {e}")
            await asyncio.sleep(0.5)

# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    asyncio.run(listen_live_feed())
