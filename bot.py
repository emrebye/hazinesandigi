import asyncio
import json
import os
import requests
import websockets
import urllib.parse

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


# ============================================================
# DUMMY SERVER
# ============================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(
            b"Treasure Alert Active!"
        )

    def log_message(self, format, *args):
        pass


def run_dummy_server():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        SimpleHTTPRequestHandler
    )

    print(
        f"🌐 Render HTTP server aktif: {port}"
    )

    server.serve_forever()


# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "-1004325133382"
)


# ============================================================
# UPSTASH
# ============================================================

UPSTASH_REDIS_REST_URL = os.getenv(
    "UPSTASH_REDIS_REST_URL",
    ""
).rstrip("/")

UPSTASH_REDIS_REST_TOKEN = os.getenv(
    "UPSTASH_REDIS_REST_TOKEN",
    ""
)

# Aynı hazine 30 dakika boyunca tekrar gönderilmez.
DUPLICATE_TTL = 1800


# ============================================================
# PROXY
# ============================================================

PROXY_URL = (
    "https://dichvu321.com/"
    "proxy.php?stream=all&live=4000"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}


# ============================================================
# TELEGRAM
# ============================================================

async def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:

        print(
            "❌ BOT_TOKEN bulunamadı!"
        )

        return False

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    try:

        response = await asyncio.to_thread(
            requests.post,
            url,
            json=payload,
            timeout=10
        )

        if response.ok:

            print(
                "📨 Telegram gönderildi."
            )

            return True

        print(
            "⚠️ Telegram HTTP hatası:",
            response.status_code
        )

        print(
            response.text[:500]
        )

        return False

    except Exception as e:

        print(
            f"⚠️ Telegram hatası: {e}"
        )

        return False


# ============================================================
# UPSTASH HAZIR MI?
# ============================================================

def upstash_ready():

    return bool(
        UPSTASH_REDIS_REST_URL
        and
        UPSTASH_REDIS_REST_TOKEN
    )


# ============================================================
# UPSTASH DUPLICATE KONTROLÜ
# ============================================================

def upstash_mark_if_new(unique_key):

    """
    Aynı hazineyi iki botun göndermesini engeller.

    Redis işlemi:

        SET key 1 NX EX 1800

    İlk bot:
        OK

    İkinci bot:
        key zaten var
        gönderme
    """

    if not upstash_ready():

        print(
            "⚠️ Upstash ENV bulunamadı!"
        )

        print(
            "⚠️ Duplicate koruması devre dışı!"
        )

        return True

    try:

        encoded_key = urllib.parse.quote(
            unique_key,
            safe=""
        )

        url = (
            f"{UPSTASH_REDIS_REST_URL}"
            f"/set/{encoded_key}/1"
            f"/nx/ex/{DUPLICATE_TTL}"
        )

        response = requests.get(
            url,
            headers={
                "Authorization":
                    f"Bearer {UPSTASH_REDIS_REST_TOKEN}"
            },
            timeout=8
        )

        if not response.ok:

            print(
                "⚠️ Upstash HTTP hatası:",
                response.status_code
            )

            print(
                response.text[:500]
            )

            return True

        try:

            result = response.json().get(
                "result"
            )

        except Exception:

            result = None

        # İlk bot buraya girer.
        if str(result).upper() == "OK":

            print(
                "🟢 UPSTASH: Yeni hazine."
            )

            return True

        # İkinci bot buraya girer.
        print(
            "⏭️ UPSTASH: Bu hazine zaten gönderilmiş."
        )

        return False

    except Exception as e:

        print(
            f"⚠️ Upstash bağlantı hatası: {e}"
        )

        # Upstash geçici olarak ulaşılmazsa
        # bot tamamen durmasın.
        return True


# ============================================================
# SAYIYA ÇEVİR
# ============================================================

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


# ============================================================
# İÇ İÇE KEY ARAMA
# ============================================================

def recursive_find_key(
    obj,
    wanted_keys,
    path=""
):

    if isinstance(obj, dict):

        for key, value in obj.items():

            key_normalized = (
                str(key)
                .lower()
                .replace("_", "")
                .replace("-", "")
            )

            current_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            if key_normalized in wanted_keys:

                number = to_int(value)

                if number is not None:

                    return (
                        number,
                        current_path
                    )

            result = recursive_find_key(
                value,
                wanted_keys,
                current_path
            )

            if result[0] is not None:

                return result

    elif isinstance(obj, list):

        for index, item in enumerate(obj):

            result = recursive_find_key(
                item,
                wanted_keys,
                f"{path}[{index}]"
            )

            if result[0] is not None:

                return result

    return None, None


# ============================================================
# RAW KEY ARAMA
# ============================================================

def recursive_find_raw(
    obj,
    wanted_keys
):

    wanted = {
        str(x).lower()
        for x in wanted_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            key_lower = str(key).lower()

            if key_lower in wanted:

                if isinstance(
                    value,
                    (str, int, float)
                ):

                    return value

            result = recursive_find_raw(
                value,
                wanted_keys
            )

            if result is not None:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find_raw(
                item,
                wanted_keys
            )

            if result is not None:

                return result

    return None


# ============================================================
# HAZİNE KİŞİ SAYISI
# ============================================================

def get_chest_recipients(payload):

    key_groups = [

        ["canopen"],

        ["peoplecount"],

        ["participantcount"],

        ["winnercount"],

        ["claimcount"],

        ["recipientcount"],

        ["grabcount"],

        ["membercount"],

        ["people"],

        ["participants"],

        ["winners"],

        ["recipients"]

    ]

    for wanted_keys in key_groups:

        value, path = recursive_find_key(
            payload,
            wanted_keys
        )

        if value is not None:

            print(
                f"🎯 KİŞİ SAYISI BULUNDU: "
                f"{value} | KEY: {path}"
            )

            return value, path

    return None, None


# ============================================================
# DEBUG
# ============================================================

def debug_relevant_keys(
    obj,
    path=""
):

    if isinstance(obj, dict):

        for key, value in obj.items():

            current_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            key_lower = str(key).lower()

            if any(
                word in key_lower
                for word in [
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
                ]
            ):

                print(
                    f"🔎 {current_path} = {value}"
                )

            debug_relevant_keys(
                value,
                current_path
            )

    elif isinstance(obj, list):

        for index, item in enumerate(obj):

            debug_relevant_keys(
                item,
                f"{path}[{index}]"
            )


# ============================================================
# EŞSİZ HAZİNE KEY
# ============================================================

def create_unique_chest_key(
    payload,
    username,
    coins,
    recipients
):

    # --------------------------------------------------------
    # Önce gerçek event ID
    # --------------------------------------------------------

    event_id = recursive_find_raw(
        payload,
        [
            "envelopeId",
            "envelopeID",
            "eventId",
            "eventID",
            "messageId",
            "messageID",
            "msgId",
            "msgID"
        ]
    )

    if event_id:

        return (
            "treasure:event:"
            f"{event_id}"
        )

    # --------------------------------------------------------
    # Room / Live ID
    # --------------------------------------------------------

    room_id = recursive_find_raw(
        payload,
        [
            "roomId",
            "roomID",
            "liveId",
            "liveID"
        ]
    )

    if room_id:

        return (
            "treasure:room:"
            f"{room_id}:"
            f"user:{username}:"
            f"coins:{coins}:"
            f"people:{recipients}"
        )

    # --------------------------------------------------------
    # Son fallback
    # --------------------------------------------------------

    return (
        "treasure:fallback:"
        f"user:{username}:"
        f"coins:{coins}:"
        f"people:{recipients}"
    )


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("=" * 60)
    print("🚀 TREASURE ALERT BAŞLADI")
    print("🎁 HAZİNE SANDIĞI TAKİBİ AKTİF")
    print("🎯 canOpen + peopleCount araması aktif")
    print("☁️ UPSTASH DUPLICATE KONTROLÜ AKTİF")
    print("🏷️ OTOMATİK ETİKETLEME YOK")
    print("=" * 60)

    if upstash_ready():

        print(
            "☁️ Upstash bağlantısı hazır."
        )

    else:

        print(
            "⚠️ Upstash ENV bulunamadı!"
        )

    while True:

        try:

            # ------------------------------------------------
            # PROXY
            # ------------------------------------------------

            print(
                "🔄 Proxy bağlantısı alınıyor..."
            )

            res = await asyncio.to_thread(
                requests.get,
                PROXY_URL,
                headers=HEADERS,
                timeout=8
            )

            data = res.json()

            if not data.get("success"):

                print(
                    "⚠️ Proxy success=false"
                )

                await asyncio.sleep(2)

                continue

            path = data.get("path")

            if not path:

                print(
                    "⚠️ Proxy path vermedi."
                )

                await asyncio.sleep(2)

                continue

            ws_url = (
                f"wss://dichvu321.com{path}"
            )

            print(
                "🔌 WebSocket bağlanıyor..."
            )

            # ------------------------------------------------
            # WEBSOCKET
            # ------------------------------------------------

            async with websockets.connect(
                ws_url,
                additional_headers=HEADERS,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:

                print(
                    "✅ WebSocket bağlandı."
                )

                async for message in websocket:

                    try:

                        event_data = json.loads(
                            message
                        )

                    except Exception:

                        continue

                    # ------------------------------------------------
                    # DATA
                    # ------------------------------------------------

                    if (
                        isinstance(
                            event_data,
                            dict
                        )
                        and
                        isinstance(
                            event_data.get("data"),
                            dict
                        )
                    ):

                        payload = (
                            event_data["data"]
                        )

                    else:

                        payload = event_data

                    if not isinstance(
                        payload,
                        dict
                    ):

                        continue

                    # ------------------------------------------------
                    # CONNECTED
                    # ------------------------------------------------

                    if payload.get(
                        "status"
                    ) == "connected":

                        continue

                    # ------------------------------------------------
                    # ENVELOPE INFO
                    # ------------------------------------------------

                    envelope_info = (
                        payload.get(
                            "envelopeInfo"
                        )
                        or {}
                    )

                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}

                    business_type = (
                        envelope_info.get(
                            "businessType"
                        )
                    )

                    # ------------------------------------------------
                    # GOODY BAG FİLTRESİ
                    # ------------------------------------------------

                    box_type_raw = str(
                        payload.get(
                            "type"
                        )
                        or ""
                    ).lower()

                    source_raw = str(
                        payload.get(
                            "source"
                        )
                        or ""
                    ).lower()

                    is_goody = (
                        business_type == 2
                        or
                        "goody" in box_type_raw
                        or
                        "goody" in source_raw
                    )

                    if is_goody:

                        print(
                            "⏭️ Goody Bag atlandı."
                        )

                        continue

                    # ------------------------------------------------
                    # USERNAME
                    # ------------------------------------------------

                    username = (
                        payload.get(
                            "uniqueId"
                        )
                        or
                        payload.get(
                            "nickname"
                        )
                        or
                        payload.get(
                            "username"
                        )
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
                    # ELMAS
                    # ------------------------------------------------

                    coins = (
                        payload.get(
                            "coins"
                        )
                        or
                        payload.get(
                            "amount"
                        )
                        or
                        payload.get(
                            "diamond"
                        )
                        or
                        payload.get(
                            "elmas"
                        )
                        or 0
                    )

                    try:

                        coins_number = int(
                            coins
                        )

                    except Exception:

                        coins_number = 0

                    if coins_number < 10:

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
                        payload.get(
                            "viewerCount"
                        )
                        or
                        payload.get(
                            "viewers"
                        )
                        or
                        payload.get(
                            "userCount"
                        )
                        or
                        envelope_info.get(
                            "viewerCount"
                        )
                        or 0
                    )

                    # ------------------------------------------------
                    # KİŞİ SAYISI
                    # ------------------------------------------------

                    recipients, recipients_path = (
                        get_chest_recipients(
                            payload
                        )
                    )

                    # ------------------------------------------------
                    # KİŞİ SAYISI BULUNAMADI
                    # ------------------------------------------------

                    if recipients is None:

                        print(
                            "\n" + "=" * 60
                        )

                        print(
                            "⚠️ KİŞİ SAYISI BULUNAMADI"
                        )

                        print(
                            f"👤 @{clean_username}"
                        )

                        print(
                            f"💎 Elmas: {coins_number}"
                        )

                        print(
                            "\n🔎 İLGİLİ KEY'LER:"
                        )

                        debug_relevant_keys(
                            payload
                        )

                        print(
                            "\n📦 HAM PAYLOAD:"
                        )

                        print(
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                indent=2
                            )
                        )

                        print(
                            "=" * 60
                        )

                        continue

                    # ------------------------------------------------
                    # BURADA ÖZEL 20/16 FİLTRESİ YOK
                    # ------------------------------------------------

                    # ------------------------------------------------
                    # UNIQUE KEY
                    # ------------------------------------------------

                    unique_key = create_unique_chest_key(
                        payload,
                        clean_username,
                        coins_number,
                        recipients
                    )

                    print(
                        f"🔑 HAZİNE KEY: {unique_key}"
                    )

                    # ------------------------------------------------
                    # UPSTASH DUPLICATE KONTROLÜ
                    # ------------------------------------------------

                    is_new = await asyncio.to_thread(
                        upstash_mark_if_new,
                        unique_key
                    )

                    if not is_new:

                        print(
                            "⏭️ AYNI HAZİNE "
                            "İKİNCİ KEZ GÖNDERİLMEDİ."
                        )

                        continue

                    # ------------------------------------------------
                    # LINK
                    # ------------------------------------------------

                    live_link = (
                        payload.get(
                            "link"
                        )
                        or
                        payload.get(
                            "url"
                        )
                        or
                        (
                            "https://www.tiktok.com/"
                            f"@{clean_username}/live"
                        )
                    )

                    # ------------------------------------------------
                    # TELEGRAM MESAJI
                    # ------------------------------------------------

                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: "
                        f"@{clean_username}\n"
                        f"👁️ İZLEYİCİ: "
                        f"{viewers}\n"
                        f"💎 ELMAS: "
                        f"{coins_number}\n"
                        f"📦 DAĞITILAN: "
                        f"{recipients} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    # ------------------------------------------------
                    # TELEGRAM
                    # ------------------------------------------------

                    sent = await send_telegram(
                        mesaj
                    )

                    if sent:

                        print(
                            f"✅ GÖNDERİLDİ: "
                            f"@{clean_username} | "
                            f"Elmas: {coins_number} | "
                            f"Kişi: {recipients}"
                        )

                    else:

                        print(
                            "⚠️ Telegram gönderilemedi."
                        )

        except Exception as e:

            print(
                f"⚠️ BAĞLANTI HATASI: {e}"
            )

            await asyncio.sleep(1)


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":

    Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    asyncio.run(
        listen_live_feed()
    )
