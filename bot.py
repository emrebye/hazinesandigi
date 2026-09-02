import asyncio
import json
import os
import requests
import websockets
import urllib.parse

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


# ============================================================
# DUMMY SERVER — RENDER
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

        print("❌ BOT_TOKEN bulunamadı!")

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

            print("📨 Telegram gönderildi.")

            return True

        print(
            "⚠️ Telegram HTTP hatası:",
            response.status_code
        )

        print(response.text[:500])

        return False

    except Exception as e:

        print(
            f"⚠️ Telegram bağlantı hatası: {e}"
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
# UPSTASH ATOMİK DUPLICATE
# ============================================================

def upstash_mark_if_new(unique_key):

    """
    Redis:

        SET key 1 NX EX 1800

    NX sayesinde iki bot aynı anda gelse bile
    yalnızca ilk bot OK alır.

    OK     = yeni hazine
    null   = daha önce alınmış
    """

    if not upstash_ready():

        print(
            "❌ UPSTASH ENV bulunamadı!"
        )

        print(
            "⛔ Güvenlik nedeniyle bildirim gönderilmiyor."
        )

        return False

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
                "❌ Upstash HTTP hatası:",
                response.status_code
            )

            print(response.text[:500])

            # Redis doğrulanamıyorsa gönderme.
            return False

        try:

            result = response.json().get(
                "result"
            )

        except Exception:

            result = None

        # ====================================================
        # İLK BOT
        # ====================================================

        if str(result).upper() == "OK":

            print(
                "🟢 UPSTASH: İLK BOT KAZANDI."
            )

            print(
                f"🔑 KEY: {unique_key}"
            )

            return True

        # ====================================================
        # İKİNCİ BOT
        # ====================================================

        print(
            "⏭️ UPSTASH: AYNI HAZİNE ZATEN KAYITLI."
        )

        print(
            f"🔑 KEY: {unique_key}"
        )

        return False

    except Exception as e:

        print(
            f"❌ Upstash bağlantı hatası: {e}"
        )

        # Redis'e ulaşılamıyorsa gönderme.
        return False


# ============================================================
# SAYIYA ÇEVİR
# ============================================================

def to_int(value):

    try:

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        number = int(float(value))

        if 0 <= number <= 100000:

            return number

    except Exception:

        pass

    return None


# ============================================================
# İÇ İÇE SAYISAL KEY ARAMA
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

                    if value not in (
                        "",
                        None,
                        0,
                        "0"
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

        ["maxusers"],

        ["limit"],

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
                    "coin",
                    "room",
                    "live",
                    "event"
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

    # ========================================================
    # 1 — GERÇEK EVENT / ENVELOPE ID
    # ========================================================

    event_id = recursive_find_raw(
        payload,
        [
            "envelopeId",
            "envelopeID",
            "envelope_id",
            "eventId",
            "eventID",
            "event_id",
            "messageId",
            "messageID",
            "message_id",
            "msgId",
            "msgID",
            "msg_id"
        ]
    )

    if event_id:

        return (
            "treasure:event:"
            f"{event_id}"
        )

    # ========================================================
    # 2 — ROOM / LIVE ID
    # ========================================================

    room_id = recursive_find_raw(
        payload,
        [
            "roomId",
            "roomID",
            "room_id",
            "liveId",
            "liveID",
            "live_id"
        ]
    )

    if room_id:

        return (
            "treasure:room:"
            f"{room_id}:"
            f"user:{username.lower()}:"
            f"coins:{coins}:"
            f"people:{recipients}"
        )

    # ========================================================
    # 3 — FALLBACK
    # ========================================================

    return (
        "treasure:fallback:"
        f"user:{username.lower()}:"
        f"coins:{coins}:"
        f"people:{recipients}"
    )


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("=" * 60)

    print(
        "🚀 TREASURE ALERT BAŞLADI"
    )

    print(
        "🎁 HAZİNE SANDIĞI TAKİBİ AKTİF"
    )

    print(
        "🎯 canOpen + peopleCount ARAMASI AKTİF"
    )

    print(
        "☁️ ATOMİK UPSTASH DUPLICATE AKTİF"
    )

    print(
        "🏷️ OTOMATİK ETİKETLEME YOK"
    )

    print("=" * 60)

    # ========================================================
    # AYAR KONTROLÜ
    # ========================================================

    if TELEGRAM_BOT_TOKEN:

        print(
            "✅ Telegram BOT_TOKEN hazır."
        )

    else:

        print(
            "❌ Telegram BOT_TOKEN YOK!"
        )

    if CHAT_ID:

        print(
            f"✅ Telegram CHAT_ID: {CHAT_ID}"
        )

    if upstash_ready():

        print(
            "✅ Upstash bağlantı bilgileri hazır."
        )

    else:

        print(
            "❌ Upstash ENV eksik!"
        )

    print("=" * 60)

    # ========================================================
    # SÜREKLİ BAĞLAN
    # ========================================================

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
                timeout=10
            )

            print(
                f"📡 Proxy HTTP: {res.status_code}"
            )

            if not res.ok:

                print(
                    "⚠️ Proxy cevap vermedi."
                )

                await asyncio.sleep(3)

                continue

            try:

                data = res.json()

            except Exception as e:

                print(
                    f"⚠️ Proxy JSON hatası: {e}"
                )

                print(
                    res.text[:500]
                )

                await asyncio.sleep(3)

                continue

            if not data.get("success"):

                print(
                    "⚠️ Proxy success=false"
                )

                print(
                    str(data)[:500]
                )

                await asyncio.sleep(3)

                continue

            path = data.get("path")

            if not path:

                print(
                    "⚠️ Proxy path vermedi."
                )

                await asyncio.sleep(3)

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
                ping_timeout=10,
                close_timeout=5,
                max_size=None
            ) as websocket:

                print(
                    "✅ WebSocket bağlandı."
                )

                # ============================================
                # MESAJLAR
                # ============================================

                async for message in websocket:

                    try:

                        if isinstance(
                            message,
                            bytes
                        ):

                            message = message.decode(
                                "utf-8",
                                errors="ignore"
                            )

                        event_data = json.loads(
                            message
                        )

                    except Exception:

                        continue

                    if not isinstance(
                        event_data,
                        dict
                    ):

                        continue

                    # ========================================
                    # DATA
                    # ========================================

                    if isinstance(
                        event_data.get("data"),
                        dict
                    ):

                        payload = dict(
                            event_data["data"]
                        )

                    else:

                        payload = dict(
                            event_data
                        )

                    # ========================================
                    # DIŞ PAYLOAD BİLGİLERİNİ KAYBETME
                    # ========================================

                    if isinstance(
                        event_data,
                        dict
                    ):

                        for key, value in event_data.items():

                            if key not in payload:

                                payload[key] = value

                    if not isinstance(
                        payload,
                        dict
                    ):

                        continue

                    # ========================================
                    # CONNECTED
                    # ========================================

                    status = str(
                        payload.get(
                            "status",
                            ""
                        )
                    ).lower()

                    if status == "connected":

                        print(
                            "🔗 Proxy bağlantısı onaylandı."
                        )

                        continue

                    # ========================================
                    # ENVELOPE INFO
                    # ========================================

                    envelope_info = (
                        payload.get(
                            "envelopeInfo"
                        )
                        or
                        payload.get(
                            "envelope_info"
                        )
                        or
                        {}
                    )

                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}

                    # ========================================
                    # BUSINESS TYPE
                    # ========================================

                    business_type = (
                        payload.get(
                            "businessType"
                        )
                        or
                        payload.get(
                            "business_type"
                        )
                        or
                        envelope_info.get(
                            "businessType"
                        )
                        or
                        envelope_info.get(
                            "business_type"
                        )
                    )

                    # ========================================
                    # GOODY BAG
                    # ========================================

                    payload_type = str(
                        payload.get(
                            "type",
                            ""
                        )
                    ).lower()

                    payload_source = str(
                        payload.get(
                            "source",
                            ""
                        )
                    ).lower()

                    payload_text = ""

                    try:

                        payload_text = json.dumps(
                            payload,
                            ensure_ascii=False
                        ).lower()

                    except Exception:

                        pass

                    is_goody = (

                        str(
                            business_type
                        ) == "2"

                        or

                        "goody" in payload_type

                        or

                        "goody" in payload_source

                        or

                        "goody" in payload_text
                    )

                    if is_goody:

                        print(
                            "⏭️ Goody Bag atlandı."
                        )

                        continue

                    # ========================================
                    # USERNAME
                    # ========================================

                    username = (

                        payload.get(
                            "uniqueId"
                        )

                        or

                        payload.get(
                            "unique_id"
                        )

                        or

                        payload.get(
                            "nickname"
                        )

                        or

                        payload.get(
                            "username"
                        )

                        or

                        payload.get(
                            "streamer"
                        )

                        or
                        ""
                    )

                    clean_username = (
                        str(username)
                        .replace("@", "")
                        .strip()
                    )

                    if not clean_username:

                        continue

                    # ========================================
                    # ELMAS
                    # ========================================

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

                        or
                        0
                    )

                    coins_number = to_int(
                        coins
                    )

                    if coins_number is None:

                        continue

                    if coins_number < 10:

                        continue

                    # ========================================
                    # LEVEL
                    # ========================================

                    level = to_int(
                        payload.get(
                            "level"
                        )
                    )

                    if level is None:

                        level = 0

                    if level > 0:

                        box_title = (
                            "🎁 HAZİNE SANDIĞI "
                            f"(Level {level})"
                        )

                    else:

                        box_title = (
                            "🎁 HAZİNE SANDIĞI"
                        )

                    # ========================================
                    # İZLEYİCİ
                    # ========================================

                    viewers = (

                        payload.get(
                            "viewerCount"
                        )

                        or

                        payload.get(
                            "viewer_count"
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

                        payload.get(
                            "user_count"
                        )

                        or

                        envelope_info.get(
                            "viewerCount"
                        )

                        or
                        0
                    )

                    # ========================================
                    # KİŞİ SAYISI
                    # ========================================

                    recipients, recipients_path = (
                        get_chest_recipients(
                            payload
                        )
                    )

                    # ========================================
                    # BULUNAMADI
                    # ========================================

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

                        try:

                            print(
                                json.dumps(
                                    payload,
                                    ensure_ascii=False,
                                    indent=2
                                )
                            )

                        except Exception:

                            print(
                                str(payload)
                            )

                        print(
                            "=" * 60
                        )

                        continue

                    # ========================================
                    # UNIQUE KEY
                    # ========================================

                    unique_key = (
                        create_unique_chest_key(
                            payload,
                            clean_username,
                            coins_number,
                            recipients
                        )
                    )

                    print(
                        f"🔑 HAZİNE KEY: "
                        f"{unique_key}"
                    )

                    # ========================================
                    # UPSTASH
                    # ========================================

                    is_new = await asyncio.to_thread(
                        upstash_mark_if_new,
                        unique_key
                    )

                    if not is_new:

                        print(
                            "⏭️ AYNI HAZİNE "
                            "GÖNDERİLMEDİ."
                        )

                        continue

                    # ========================================
                    # LINK
                    # ========================================

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

                    # ========================================
                    # TELEGRAM MESAJI
                    # ========================================

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

                    # ========================================
                    # GÖNDER
                    # ========================================

                    sent = await send_telegram(
                        mesaj
                    )

                    if sent:

                        print(
                            "✅ GÖNDERİLDİ:"
                            f" @{clean_username}"
                            f" | Elmas: {coins_number}"
                            f" | Kişi: {recipients}"
                        )

                    else:

                        print(
                            "⚠️ Telegram gönderilemedi."
                        )

        # ====================================================
        # BAĞLANTI HATASI
        # ====================================================

        except Exception as e:

            print(
                f"⚠️ BAĞLANTI HATASI: {e}"
            )

            await asyncio.sleep(2)


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
