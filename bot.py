import asyncio
import json
import os
import requests
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import re
import hashlib


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Synced Bot Active!")

    def log_message(self, format, *args):
        pass


def run_dummy_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()


# =========================================================
# ANAHTARLAR
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")


# =========================================================
# PROXY
# =========================================================

PROXY_URL = "https://dichvu321.com/proxy.php?stream=box&live=1000"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/",
}


# =========================================================
# CACHE
# =========================================================

CACHE_TIMEOUT = 1800  # 30 dakika


# =========================================================
# BAŞLANGIÇ KONTROLÜ
# =========================================================

def check_config():
    missing = []

    if not TELEGRAM_BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not TELEGRAM_CHAT_ID:
        missing.append("CHAT_ID")

    if not UPSTASH_URL:
        missing.append("UPSTASH_REDIS_REST_URL")

    if not UPSTASH_TOKEN:
        missing.append("UPSTASH_REDIS_REST_TOKEN")

    if missing:
        print("❌ Eksik Environment Variable:", ", ".join(missing))
        return False

    return True


# =========================================================
# TELEGRAM
# =========================================================

async def send_telegram_async(text):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    def _send():
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                },
                timeout=5,
            )

            if response.ok:
                return True

            print("❌ Telegram gönderim hatası:", response.text)
            return False

        except Exception as e:
            print("❌ Telegram bağlantı hatası:", e)
            return False

    return await asyncio.to_thread(_send)


# =========================================================
# UPSTASH - ATOMİK TEKİLLEŞTİRME
# =========================================================

def upstash_request(command):
    headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json",
    }

    return requests.post(
        UPSTASH_URL,
        headers=headers,
        json=command,
        timeout=8,
    )


def claim_cache(cache_key):
    """
    İki bot aynı anda aynı olayı görse bile yalnızca biri kazanır.

    SET key 1 NX EX 1800

    OK     -> ilk bot aldı
    None   -> başka bot daha önce aldı
    """

    try:
        response = upstash_request(
            [
                "SET",
                cache_key,
                "1",
                "NX",
                "EX",
                str(CACHE_TIMEOUT),
            ]
        )

        data = response.json()
        result = data.get("result")

        if str(result).upper() == "OK":
            return True

        return False

    except Exception as e:
        print("❌ Upstash bağlantı hatası:", e)

        # Upstash yoksa gönderme.
        # Böylece iki botun aynı bildirimi yollama riski oluşmaz.
        return False


def release_cache(cache_key):
    """
    Telegram gönderimi başarısız olursa olay tekrar gönderilebilsin.
    """

    try:
        upstash_request(["DEL", cache_key])
    except Exception:
        pass


# =========================================================
# EVENT CACHE KEY
# =========================================================

def make_cache_key(payload, clean_username, amount, chest_people):
    """
    Öncelik:
    1. eventId
    2. envelopeId
    3. event_id
    4. id

    Bunlar yoksa olay bilgilerinden SHA256 anahtarı oluşturulur.
    """

    event_id = (
        payload.get("eventId")
        or payload.get("event_id")
        or payload.get("envelopeId")
        or payload.get("envelope_id")
        or payload.get("id")
    )

    if event_id:
        safe_event_id = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            str(event_id)
        )

        if safe_event_id:
            return f"mor_zarf:event:{safe_event_id}"

    sender = (
        payload.get("sender")
        or payload.get("senderId")
        or payload.get("sendUserName")
        or payload.get("send_user_name")
        or ""
    )

    raw = (
        f"{clean_username}|"
        f"{amount}|"
        f"{chest_people}|"
        f"{sender}"
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return f"mor_zarf:fallback:{digest}"


# =========================================================
# LIVE FEED
# =========================================================

async def listen_live_feed():

    print("🚀 RENDER ORTAK BULUT BOT AKTİF")

    while True:

        try:

            # -------------------------------------------------
            # Proxy'den websocket yolu al
            # -------------------------------------------------

            res = await asyncio.to_thread(
                requests.get,
                PROXY_URL,
                headers=HEADERS,
                timeout=5,
            )

            data = res.json()

            if not data.get("success"):
                print("⚠️ Proxy başarısız, tekrar deneniyor...")
                await asyncio.sleep(2)
                continue

            path = data.get("path")

            if not path:
                print("⚠️ Proxy path vermedi.")
                await asyncio.sleep(2)
                continue

            ws_url = f"wss://dichvu321.com{path}"

            print("🔌 WebSocket bağlanıyor...")

            # -------------------------------------------------
            # WebSocket
            # -------------------------------------------------

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=None,
            ) as websocket:

                print("✅ WebSocket bağlantısı kuruldu.")

                async for message in websocket:

                    try:
                        event_data = json.loads(message)
                    except Exception:
                        continue

                    # -------------------------------------------------
                    # Payload birleştirme
                    # -------------------------------------------------

                    payload = event_data.copy()

                    if (
                        "data" in event_data
                        and isinstance(event_data["data"], dict)
                    ):
                        payload.update(event_data["data"])

                    if (
                        "payload" in event_data
                        and isinstance(event_data["payload"], dict)
                    ):
                        payload.update(event_data["payload"])

                    # -------------------------------------------------
                    # Yayıncı adı
                    # -------------------------------------------------

                    username = (
                        payload.get("uniqueId")
                        or payload.get("nickname")
                        or payload.get("username")
                        or payload.get("streamer")
                    )

                    if not username:
                        continue

                    clean_username = (
                        str(username)
                        .replace("@", "")
                        .strip()
                    )

                    if not clean_username:
                        continue

                    # -------------------------------------------------
                    # Elmas
                    # -------------------------------------------------

                    coins_raw = (
                        payload.get("coins")
                        or payload.get("amount")
                        or payload.get("elmas")
                        or payload.get("diamond")
                        or 0
                    )

                    try:
                        amount = float(coins_raw)
                    except Exception:
                        amount = 0

                    # Mevcut bot ayarını koruyoruz
                    if amount < 10:
                        continue

                    # -------------------------------------------------
                    # İzleyici
                    # -------------------------------------------------

                    room_viewers = (
                        payload.get("viewerCount")
                        or payload.get("viewers")
                        or 25
                    )

                    # -------------------------------------------------
                    # Sandık kişi sayısı
                    # -------------------------------------------------

                    chest_people = (
                        payload.get("chestUsers")
                        or payload.get("maxUsers")
                        or payload.get("limit")
                        or 15
                    )

                    # -------------------------------------------------
                    # Canlı yayın linki
                    # -------------------------------------------------

                    live_link = (
                        payload.get("link")
                        or payload.get("url")
                        or (
                            f"https://www.tiktok.com/"
                            f"@{clean_username}/live"
                        )
                    )

                    # -------------------------------------------------
                    # ORTAK UPSTASH ANAHTARI
                    # -------------------------------------------------

                    cache_key = make_cache_key(
                        payload=payload,
                        clean_username=clean_username,
                        amount=int(amount),
                        chest_people=chest_people,
                    )

                    # -------------------------------------------------
                    # ATOMİK CLAIM
                    # -------------------------------------------------

                    won_claim = await asyncio.to_thread(
                        claim_cache,
                        cache_key,
                    )

                    if not won_claim:
                        print(
                            f"⏭️ Zaten gönderilmiş: "
                            f"@{clean_username}"
                        )
                        continue

                    # -------------------------------------------------
                    # TELEGRAM MESAJI
                    # -------------------------------------------------

                    mesaj = (
                        f"🎁 **HAZİNE SANDIĞI**\n"
                        f"👤 **YAYINCI:** "
                        f"`@{clean_username}`\n"
                        f"👁️ **İZLEYİCİ:** "
                        f"{room_viewers}\n"
                        f"💎 **ELMAS:** "
                        f"{int(amount)}\n"
                        f"📦 **DAĞITILAN:** "
                        f"{chest_people} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    # -------------------------------------------------
                    # TELEGRAM GÖNDER
                    # -------------------------------------------------

                    sent = await send_telegram_async(mesaj)

                    if sent:
                        print(
                            f"✅ UPSTASH CLAIM + TELEGRAM: "
                            f"@{clean_username} "
                            f"| {int(amount)} elmas"
                        )

                    else:
                        # Telegram başarısızsa cache'i bırak.
                        # Böylece olay yeniden gönderilebilsin.
                        await asyncio.to_thread(
                            release_cache,
                            cache_key,
                        )

                        print(
                            f"↩️ Telegram başarısız, "
                            f"cache bırakıldı: "
                            f"@{clean_username}"
                        )

        except Exception as e:

            print("⚠️ WebSocket/Feed hatası:", e)

            await asyncio.sleep(2)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("======================================")
    print("   SYNCED TREASURE BOT")
    print("   UPSTASH ATOMIC DEDUP AKTİF")
    print("======================================")

    if not check_config():
        raise SystemExit(1)

    Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    asyncio.run(listen_live_feed())
