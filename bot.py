import asyncio
import json
import os
import requests
import websockets

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


# =========================================================
# RENDER HTTP SERVER
# =========================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Jimin Bot Active!")

    def log_message(self, format, *args):
        pass


def run_dummy_server():
    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        SimpleHTTPRequestHandler
    )

    print(f"🌐 HTTP server aktif: {port}")
    server.serve_forever()


# =========================================================
# AYARLAR
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "-1004325133382")

PROXY_URL = "https://dichvu321.com/proxy.php?stream=all&live=4000"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        print("❌ BOT_TOKEN bulunamadı!")
        return

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=15
        )

        if response.ok:
            print("📨 Telegram gönderildi")
        else:
            print(
                "❌ Telegram hatası:",
                response.status_code,
                response.text[:500]
            )

    except Exception as e:
        print("❌ Telegram bağlantı hatası:", e)


# =========================================================
# SAYI ÇEVİRİCİ
# =========================================================

def to_int(value):

    try:

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        number = int(value)

        if 0 <= number <= 100000:
            return number

    except Exception:
        pass

    return None


# =========================================================
# RECURSIVE KEY ARAMA
# =========================================================

def recursive_find_key(data, wanted_keys):

    if isinstance(data, dict):

        for key, value in data.items():

            normalized = (
                str(key)
                .lower()
                .replace("_", "")
                .replace("-", "")
            )

            if normalized in wanted_keys:
                number = to_int(value)

                if number is not None:
                    return number

            result = recursive_find_key(
                value,
                wanted_keys
            )

            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:

            result = recursive_find_key(
                item,
                wanted_keys
            )

            if result is not None:
                return result

    return None


# =========================================================
# HAZİNEDEKİ KİŞİ SAYISI
# =========================================================

def get_chest_recipients(payload):

    keys = [

        "canopen",

        "peoplecount",

        "participantcount",

        "winnercount",

        "claimcount",

        "recipientcount",

        "grabcount",

        "membercount",

        "people",

        "participants",

        "winners",

        "recipients"

    ]

    wanted_keys = set(keys)

    return recursive_find_key(
        payload,
        wanted_keys
    )


# =========================================================
# DİNAMİK ETİKET KURALI
# =========================================================

def should_tag_chest(coins, recipients):

    if coins is None:
        return False

    if recipients is None:
        return False

    # 20'nin altındaki hazineler etiketlenmez
    if coins < 20:
        return False

    # 20 - 99
    if coins < 100:
        max_recipients = 10

    # 100 - 199
    else:
        tier = coins // 100
        max_recipients = tier * 10

    return recipients <= max_recipients


# =========================================================
# DEBUG
# =========================================================

def debug_relevant_keys(payload):

    if not isinstance(payload, dict):
        return

    words = (
        "open",
        "people",
        "participant",
        "winner",
        "claim",
        "recipient",
        "grab",
        "envelope",
        "business",
        "diamond",
        "coin"
    )

    found = []

    def scan(obj, path=""):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if any(word in key_lower for word in words):
                    found.append(
                        (f"{path}.{key}", value)
                    )

                scan(
                    value,
                    f"{path}.{key}"
                )

        elif isinstance(obj, list):

            for index, item in enumerate(obj):

                scan(
                    item,
                    f"{path}[{index}]"
                )

    scan(payload)

    if found:

        print("\n🔎 İLGİLİ ALANLAR:")

        for key, value in found[:50]:
            print(
                f"   {key} = {value}"
            )


# =========================================================
# KULLANICI ADI
# =========================================================

def get_username(payload):

    keys = [
        "uniqueId",
        "unique_id",
        "nickname",
        "username"
    ]

    for key in keys:

        value = recursive_find_raw(
            payload,
            key
        )

        if value:
            return str(value)

    return "Bilinmeyen"


def recursive_find_raw(data, wanted_key):

    if isinstance(data, dict):

        for key, value in data.items():

            if str(key).lower() == wanted_key.lower():

                if isinstance(value, (str, int, float)):
                    return value

            result = recursive_find_raw(
                value,
                wanted_key
            )

            if result is not None:
                return result

    elif isinstance(data, list):

        for item in data:

            result = recursive_find_raw(
                item,
                wanted_key
            )

            if result is not None:
                return result

    return None


# =========================================================
# CANLI DİNLLE
# =========================================================

async def listen_live_feed():

    print("🚀 Hazine botu başlıyor...")
    print("🌐 Proxy:", PROXY_URL)

    while True:

        try:

            print("\n🔌 Proxy WebSocket bağlantısı kuruluyor...")

            async with websockets.connect(
                PROXY_URL,
                additional_headers=HEADERS,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
                max_size=None
            ) as websocket:

                print("✅ WebSocket bağlandı!")

                async for raw_message in websocket:

                    try:

                        if isinstance(raw_message, bytes):
                            raw_message = raw_message.decode(
                                "utf-8",
                                errors="ignore"
                            )

                        event_data = json.loads(
                            raw_message
                        )

                    except Exception:

                        continue

                    # Proxy data alanı
                    payload = event_data.get(
                        "data",
                        event_data
                    )

                    if not isinstance(payload, dict):
                        continue

                    # Bağlantı durum mesajlarını geç
                    status = str(
                        payload.get(
                            "status",
                            ""
                        )
                    ).lower()

                    if status in (
                        "connected",
                        "connecting",
                        "heartbeat"
                    ):
                        continue

                    # =================================================
                    # ENVELOPE
                    # =================================================

                    envelope_info = (
                        payload.get(
                            "envelopeInfo"
                        )
                        or payload.get(
                            "envelope_info"
                        )
                        or {}
                    )

                    business_type = (
                        payload.get(
                            "businessType"
                        )
                        or payload.get(
                            "business_type"
                        )
                        or envelope_info.get(
                            "businessType"
                        )
                        or envelope_info.get(
                            "business_type"
                        )
                    )

                    # =================================================
                    # GOODY BAG DEĞİLSE DEVAM
                    # =================================================

                    payload_text = json.dumps(
                        payload,
                        ensure_ascii=False
                    ).lower()

                    if (
                        business_type == 2
                        or "goody" in payload_text
                    ):
                        continue

                    # =================================================
                    # ELİMAS
                    # =================================================

                    coins = (
                        payload.get("coins")
                        or payload.get("amount")
                        or payload.get("diamond")
                        or payload.get("elmas")
                        or envelope_info.get("coins")
                        or envelope_info.get("diamond")
                    )

                    coins_number = to_int(coins)

                    if coins_number is None:
                        continue

                    # Çok küçük eventleri alma
                    if coins_number < 10:
                        continue

                    # =================================================
                    # KULLANICI
                    # =================================================

                    username = get_username(
                        payload
                    )

                    # =================================================
                    # SEVİYE
                    # =================================================

                    level = (
                        payload.get("level")
                        or payload.get("userLevel")
                        or payload.get("user_level")
                        or envelope_info.get("level")
                        or 0
                    )

                    # =================================================
                    # İZLEYİCİ
                    # =================================================

                    viewers = (
                        payload.get("viewerCount")
                        or payload.get("viewer_count")
                        or payload.get("viewers")
                        or payload.get("userCount")
                        or envelope_info.get("viewerCount")
                        or 0
                    )

                    viewers_number = to_int(
                        viewers
                    ) or 0

                    # =================================================
                    # KİŞİ SAYISI
                    # =================================================

                    recipients = get_chest_recipients(
                        payload
                    )

                    # Bulunamadıysa debug
                    if recipients is None:

                        print(
                            "\n⚠️ Hazine kişi sayısı bulunamadı!"
                        )

                        debug_relevant_keys(
                            payload
                        )

                        continue

                    # =================================================
                    # 20 ELMAS / 16 KİŞİYİ KALDIR
                    # =================================================

                    if (
                        coins_number == 20
                        and recipients == 16
                    ):

                        print(
                            "⏭️ 20 elmas / 16 kişi kaldırıldı"
                        )

                        continue

                    # =================================================
                    # ETİKET KARARI
                    # =================================================

                    tag = should_tag_chest(
                        coins_number,
                        recipients
                    )

                    # =================================================
                    # CANLI LİNK
                    # =================================================

                    live_link = (
                        payload.get("link")
                        or payload.get("url")
                    )

                    if not live_link:
                        live_link = (
                            "https://www.tiktok.com/"
                        )

                    # =================================================
                    # MESAJ
                    # =================================================

                    if tag:

                        message = (
                            "🚨 <b>@jiminienn</b>\n\n"
                        )

                    else:

                        message = ""

                    message += (
                        "🎁 <b>HAZİNE SANDIĞI</b>\n\n"
                        f"👤 Kullanıcı: <b>{username}</b>\n"
                        f"💎 Elmas: <b>{coins_number}</b>\n"
                        f"👥 Dağıtılan: <b>{recipients}</b> kişi\n"
                        f"⭐ Seviye: <b>{level}</b>\n"
                        f"👀 İzleyici: <b>{viewers_number}</b>\n\n"
                        f"🔗 <a href=\"{live_link}\">Canlı yayına git</a>"
                    )

                    # =================================================
                    # LOG
                    # =================================================

                    if tag:

                        print(
                            f"\n🚨 ETİKETLENDİ | "
                            f"{coins_number} elmas / "
                            f"{recipients} kişi | "
                            f"@{username}"
                        )

                    else:

                        print(
                            f"\n🎁 Hazine | "
                            f"{coins_number} elmas / "
                            f"{recipients} kişi | "
                            f"@{username}"
                        )

                    # =================================================
                    # TELEGRAM
                    # =================================================

                    asyncio.create_task(
                        asyncio.to_thread(
                            send_telegram,
                            message
                        )
                    )

        except Exception as e:

            print(
                "\n❌ WebSocket hatası:",
                repr(e)
            )

            print(
                "⏳ 10 saniye sonra yeniden bağlanıyor..."
            )

            await asyncio.sleep(10)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # Render için HTTP server
    Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    try:

        asyncio.run(
            listen_live_feed()
        )

    except KeyboardInterrupt:

        print(
            "\n🛑 Bot durduruldu."
        )
