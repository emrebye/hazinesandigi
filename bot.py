import asyncio
import json
import os
import threading
import requests
import websockets

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# RENDER PORT
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
# AYARLAR
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "-1004325133382")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}


# ============================================================
# UPSTASH CLOUD CACHE
# ============================================================

UPSTASH_URL = os.getenv(
    "UPSTASH_URL",
    "https://exotic-javelin-180919.upstash.io"
).rstrip("/")

UPSTASH_TOKEN = os.getenv("UPSTASH_TOKEN", "")

CACHE_TIMEOUT = 1800  # 30 dakika


def check_and_save_cache(cache_key):
    """
    Aynı hazineyi 30 dakika içinde tekrar göndermez.

    Upstash:
        OK   = yeni kayıt
        null = kayıt zaten var
    """

    if not UPSTASH_TOKEN:
        print("⚠️ UPSTASH_TOKEN yok: CACHE KAPALI")
        return False

    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json"
    }

    try:

        payload = [
            "SET",
            cache_key,
            "1",
            "EX",
            str(CACHE_TIMEOUT),
            "NX"
        ]

        response = requests.post(
            UPSTASH_URL,
            headers=headers,
            json=payload,
            timeout=5
        )

        response.raise_for_status()

        result = response.json().get("result")

        # OK = ilk kez kaydedildi.
        # Bu yüzden Telegram'a gönderilecek.
        if result == "OK":
            return False

        # null = daha önce kaydedilmiş.
        # Telegram'a tekrar gönderme.
        return True

    except Exception as e:

        print(f"⚠️ Upstash cache hatası: {e}")

        # Upstash geçici hata verirse bot tamamen durmasın.
        return False


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(mesaj):

    if not TELEGRAM_BOT_TOKEN:
        print("❌ BOT_TOKEN bulunamadı!")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "disable_web_page_preview": True
    }

    try:

        loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                url,
                json=payload,
                timeout=5
            )
        )

        if response.ok:
            return True

        print(
            f"⚠️ Telegram HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

        return False

    except Exception as e:

        print(f"⚠️ Telegram hatası: {e}")

        return False


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("🚀 HAZİNE BOTU BAŞLADI")

    if UPSTASH_TOKEN:
        print("☁️ Upstash cloud cache: AKTİF")
    else:
        print("⚠️ Upstash token yok: CACHE KAPALI")

    print("🎁 canOpen kişi sayısı alanı korunuyor")

    while True:

        try:

            loop = asyncio.get_running_loop()

            # ----------------------------------------------------
            # PROXY'DEN WEBSOCKET BİLGİSİ AL
            # ----------------------------------------------------

            res = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    PROXY_URL,
                    headers=HEADERS,
                    timeout=5
                )
            )

            data = res.json()

            if not data.get("success"):

                await asyncio.sleep(1)

                continue

            path = data.get("path")

            if not path:

                await asyncio.sleep(1)

                continue

            ws_url = f"wss://dichvu321.com{path}"

            # ----------------------------------------------------
            # WEBSOCKET
            # ----------------------------------------------------

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:

                print("✅ WebSocket bağlandı")

                async for message in websocket:

                    try:

                        event_data = json.loads(message)

                    except Exception:

                        continue

                    # ------------------------------------------------
                    # DATA
                    # ------------------------------------------------

                    payload = (
                        event_data.get("data")
                        if isinstance(
                            event_data.get("data"),
                            dict
                        )
                        else event_data
                    )

                    if not isinstance(payload, dict):

                        continue

                    if payload.get("status") == "connected":

                        continue

                    # ------------------------------------------------
                    # HAZİNE / GOODY BAG AYRIMI
                    # ------------------------------------------------

                    box_type_raw = str(
                        payload.get("type") or ""
                    ).lower()

                    source_raw = str(
                        payload.get("source") or ""
                    ).lower()

                    envelope_info = (
                        payload.get("envelopeInfo") or {}
                    )

                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}

                    business_type = envelope_info.get(
                        "businessType",
                        1
                    )

                    is_goody = (
                        business_type == 2
                        or "goody" in box_type_raw
                        or "goody" in source_raw
                    )

                    if is_goody:

                        continue

                    # ------------------------------------------------
                    # ELMAS
                    # ------------------------------------------------

                    coins = payload.get(
                        "coins",
                        0
                    )

                    try:

                        coins_number = int(coins)

                    except Exception:

                        coins_number = 0

                    if coins_number <= 0:

                        continue

                    # ------------------------------------------------
                    # YAYINCI
                    # ------------------------------------------------

                    username = (
                        payload.get("uniqueId")
                        or payload.get("nickname")
                        or payload.get("username")
                        or ""
                    )

                    clean_username = (
                        str(username)
                        .replace("@", "")
                        .strip()
                    )

                    if not clean_username:

                        continue

                    # ------------------------------------------------
                    # CAN OPEN / KİŞİ SAYISI
                    # ------------------------------------------------

                    recipients = payload.get(
                        "canOpen",
                        0
                    )

                    try:

                        recipients_number = int(
                            recipients
                        )

                    except Exception:

                        recipients_number = 0

                    # ------------------------------------------------
                    # UPSTASH DUPLICATE
                    # ------------------------------------------------

                    cache_key = (
                        "treasurealert:"
                        + clean_username.lower()
                        + ":"
                        + str(coins_number)
                        + ":"
                        + str(recipients_number)
                    )

                    duplicate = await asyncio.to_thread(
                        check_and_save_cache,
                        cache_key
                    )

                    if duplicate:

                        print(
                            f"⏭️ DUPLICATE/CACHE: "
                            f"@{clean_username} "
                            f"| Elmas: {coins_number} "
                            f"| Kişi: {recipients_number}"
                        )

                        continue

                    # ------------------------------------------------
                    # LEVEL
                    # ------------------------------------------------

                    level = payload.get(
                        "level",
                        0
                    )

                    try:

                        level = int(level)

                    except Exception:

                        level = 0

                    if level > 0:

                        box_title = (
                            f"🎁 HAZİNE SANDIĞI "
                            f"(Level {level})"
                        )

                    else:

                        box_title = (
                            "🎁 HAZİNE SANDIĞI"
                        )

                    # ------------------------------------------------
                    # İZLEYİCİ
                    # ------------------------------------------------

                    viewers = (
                        payload.get("viewerCount")
                        or payload.get("userCount")
                        or envelope_info.get(
                            "viewerCount"
                        )
                        or 0
                    )

                    # ------------------------------------------------
                    # TIKTOK LINK
                    # ------------------------------------------------

                    live_link = (
                        f"https://www.tiktok.com/"
                        f"@{clean_username}/live"
                    )

                    # ------------------------------------------------
                    # TELEGRAM MESAJI
                    # ------------------------------------------------

                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: @{clean_username}\n"
                        f"👁️ İZLEYİCİ: {viewers}\n"
                        f"💎 ELMAS: {coins_number}\n"
                        f"📦 DAĞITILAN: "
                        f"{recipients_number} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    asyncio.create_task(
                        send_telegram(mesaj)
                    )

                    print(
                        f"✅ GÖNDERİLDİ: "
                        f"@{clean_username} "
                        f"| Elmas: {coins_number} "
                        f"| Kişi: {recipients_number}"
                    )

        except Exception as e:

            print(
                f"⚠️ BAĞLANTI HATASI: {e}"
            )

            await asyncio.sleep(0.5)


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":

    # Render'ın port kontrolü için HTTP sunucusu
    # ayrı thread'de çalışır.
    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()

    # Asıl Treasure Alert sistemi
    asyncio.run(
        listen_live_feed()
    )
