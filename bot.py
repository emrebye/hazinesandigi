import asyncio
import json
import os
import requests
import websockets

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


# ============================================================
# RENDER DUMMY SERVER
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
            b"Synced Bot Active!"
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
        f"🌐 Render server aktif: {port}"
    )

    server.serve_forever()


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.getenv(
    "CHAT_ID",
    "5050032521"
)


# ============================================================
# UPSTASH
# ============================================================

UPSTASH_URL = os.getenv(
    "UPSTASH_REDIS_REST_URL",
    ""
).rstrip("/")

UPSTASH_TOKEN = os.getenv(
    "UPSTASH_REDIS_REST_TOKEN",
    ""
)

# Aynı kayıt 30 dakika tutulur.
CACHE_TIMEOUT = 1800


# ============================================================
# PROXY
# ============================================================

PROXY_URL = (
    "https://dichvu321.com/"
    "proxy.php?stream=box&live=1000"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Mobile Safari/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}


# ============================================================
# TELEGRAM GÖNDER
# ============================================================

async def send_telegram_async(text):

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
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:

        response = await asyncio.to_thread(
            requests.post,
            url,
            json=payload,
            timeout=10
        )

        if response.ok:

            return True

        print(
            "❌ Telegram hatası:",
            response.status_code,
            response.text[:500]
        )

        return False

    except Exception as e:

        print(
            f"❌ Telegram bağlantı hatası: {e}"
        )

        return False


# ============================================================
# UPSTASH DURUM
# ============================================================

def upstash_ready():

    return bool(
        UPSTASH_URL
        and
        UPSTASH_TOKEN
    )


# ============================================================
# ATOMİK UPSTASH DUPLICATE KONTROLÜ
# ============================================================

def check_and_save_cache(cache_key):

    """
    ÖNEMLİ:

    Eski sistem:

        GET
        ↓
        SET

    İki bot aynı anda GET yaptığında ikisi de
    kaydın olmadığını görüp SET yapabiliyordu.

    Yeni sistem:

        SET key 1 NX EX 1800

    NX = anahtar yoksa oluştur.

    Redis bunu tek atomik işlem olarak yapar.

    Sonuç:

        Bot 1 → OK
        Bot 2 → NIL

    Böylece aynı hazineyi iki bot gönderemez.
    """

    if not upstash_ready():

        print(
            "❌ UPSTASH AYARLARI BULUNAMADI!"
        )

        # Ortak hafıza yoksa duplicate garantisi veremeyiz.
        return None

    try:

        url = f"{UPSTASH_URL}/"

        headers = {
            "Authorization":
                f"Bearer {UPSTASH_TOKEN}",
            "Content-Type":
                "application/json"
        }

        # ----------------------------------------------------
        # ATOMİK SET NX EX
        # ----------------------------------------------------

        command = [
            "SET",
            cache_key,
            "1",
            "NX",
            "EX",
            str(CACHE_TIMEOUT)
        ]

        response = requests.post(
            url,
            headers=headers,
            json=command,
            timeout=8
        )

        if not response.ok:

            print(
                "❌ Upstash HTTP hatası:",
                response.status_code
            )

            print(
                response.text[:500]
            )

            return None

        try:

            result = response.json().get(
                "result"
            )

        except Exception:

            result = None

        # ----------------------------------------------------
        # İLK BOT KAZANDI
        # ----------------------------------------------------

        if str(result).upper() == "OK":

            print(
                "🟢 UPSTASH: İLK BOT KAZANDI."
            )

            print(
                f"🔑 KEY: {cache_key}"
            )

            return True

        # ----------------------------------------------------
        # DİĞER BOT
        # ----------------------------------------------------

        print(
            "⏭️ UPSTASH: AYNI HAZİNE ZATEN KAYITLI."
        )

        print(
            f"🔑 KEY: {cache_key}"
        )

        return False

    except Exception as e:

        print(
            f"❌ Upstash bağlantı hatası: {e}"
        )

        # Redis kontrol edilemiyorsa gönderme.
        return None


# ============================================================
# SAYIYA ÇEVİR
# ============================================================

def to_int(value):

    try:

        if value is None:
            return None

        if isinstance(
            value,
            bool
        ):

            return None

        return int(
            float(value)
        )

    except Exception:

        return None


# ============================================================
# RECURSIVE VALUE BUL
# ============================================================

def find_raw_value(
    obj,
    wanted_keys
):

    wanted = {
        str(key).lower()
        for key in wanted_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            if str(key).lower() in wanted:

                if value not in (
                    None,
                    "",
                    0,
                    "0"
                ):

                    return value

            result = find_raw_value(
                value,
                wanted_keys
            )

            if result not in (
                None,
                "",
                0,
                "0"
            ):

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = find_raw_value(
                item,
                wanted_keys
            )

            if result not in (
                None,
                "",
                0,
                "0"
            ):

                return result

    return None


# ============================================================
# RECURSIVE SAYI BUL
# ============================================================

def recursive_find_number(
    obj,
    wanted_keys
):

    wanted = {
        str(key)
        .lower()
        .replace("_", "")
        .replace("-", "")
        for key in wanted_keys
    }

    if isinstance(obj, dict):

        for key, value in obj.items():

            normalized = (
                str(key)
                .lower()
                .replace("_", "")
                .replace("-", "")
            )

            if normalized in wanted:

                number = to_int(
                    value
                )

                if number is not None:

                    return number

            result = recursive_find_number(
                value,
                wanted_keys
            )

            if result is not None:

                return result

    elif isinstance(obj, list):

        for item in obj:

            result = recursive_find_number(
                item,
                wanted_keys
            )

            if result is not None:

                return result

    return None


# ============================================================
# HAZİNE KİŞİ SAYISI
# ============================================================

def get_chest_people(payload):

    key_groups = [

        [
            "canOpen",
            "canopen"
        ],

        [
            "peopleCount",
            "peoplecount"
        ],

        [
            "participantCount",
            "participantcount"
        ],

        [
            "winnerCount",
            "winnercount"
        ],

        [
            "claimCount",
            "claimcount"
        ],

        [
            "recipientCount",
            "recipientcount"
        ],

        [
            "grabCount",
            "grabcount"
        ],

        [
            "memberCount",
            "membercount"
        ],

        [
            "chestUsers",
            "chestusers"
        ],

        [
            "maxUsers",
            "maxusers"
        ],

        [
            "limit"
        ],

        [
            "people"
        ],

        [
            "participants"
        ],

        [
            "winners"
        ],

        [
            "recipients"
        ]
    ]

    for keys in key_groups:

        result = recursive_find_number(
            payload,
            keys
        )

        if result is not None:

            print(
                f"🎯 KİŞİ SAYISI: {result}"
            )

            return result

    return None


# ============================================================
# GOODY BAG KONTROLÜ
# ============================================================

def is_goody_bag(payload):

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

    if str(business_type) == "2":

        return True

    payload_text = json.dumps(
        payload,
        ensure_ascii=False
    ).lower()

    if "goody" in payload_text:

        return True

    return False


# ============================================================
# DUPLICATE KEY OLUŞTUR
# ============================================================

def create_cache_key(
    payload,
    username,
    amount,
    chest_people
):

    # --------------------------------------------------------
    # Önce gerçek event ID varsa kullan
    # --------------------------------------------------------

    event_id = find_raw_value(
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

    # --------------------------------------------------------
    # Room / Live ID varsa kullan
    # --------------------------------------------------------

    room_id = find_raw_value(
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
            "treasure:"
            f"room:{room_id}:"
            f"user:{username.lower()}:"
            f"coins:{amount}:"
            f"people:{chest_people}"
        )

    # --------------------------------------------------------
    # Fallback
    #
    # Eski kod sadece username kullanıyordu.
    #
    # Bu yüzden aynı yayıncının 30 dakika içindeki
    # bütün hazineleri birbirini engelliyordu.
    #
    # Şimdi elmas + kişi sayısı da dahil.
    # --------------------------------------------------------

    return (
        "treasure:"
        f"user:{username.lower()}:"
        f"coins:{amount}:"
        f"people:{chest_people}"
    )


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("=" * 60)
    print("🚀 KESİN ÇÖZÜM BULUT BOT AKTİF")
    print("🎁 HAZİNE SANDIĞI TAKİBİ AKTİF")
    print("☁️ ATOMİK UPSTASH DUPLICATE AKTİF")
    print("🏷️ OTOMATİK ETİKET YOK")
    print("=" * 60)

    if upstash_ready():

        print(
            "☁️ Upstash bağlantısı hazır."
        )

    else:

        print(
            "❌ Upstash ENV eksik!"
        )

    while True:

        try:

            # ====================================================
            # PROXY
            # ====================================================

            print(
                "🔄 Proxy bağlantısı alınıyor..."
            )

            res = await asyncio.to_thread(
                requests.get,
                PROXY_URL,
                headers=HEADERS,
                timeout=8
            )

            if not res.ok:

                print(
                    "⚠️ Proxy HTTP:",
                    res.status_code
                )

                await asyncio.sleep(2)

                continue

            data = res.json()

            if not data.get(
                "success"
            ):

                print(
                    "⚠️ Proxy success=false"
                )

                await asyncio.sleep(2)

                continue

            path = data.get(
                "path"
            )

            if not path:

                print(
                    "⚠️ Proxy path vermedi."
                )

                await asyncio.sleep(2)

                continue

            ws_url = (
                f"wss://dichvu321.com"
                f"{path}"
            )

            print(
                "🔌 WebSocket bağlanıyor..."
            )

            # ====================================================
            # WEBSOCKET
            # ====================================================

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

                async for message in websocket:

                    # =================================================
                    # JSON
                    # =================================================

                    try:

                        if isinstance(
                            message,
                            bytes
                        ):

                            message = (
                                message.decode(
                                    "utf-8",
                                    errors="ignore"
                                )
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

                    # =================================================
                    # PAYLOAD
                    # =================================================

                    payload = event_data

                    if (
                        isinstance(
                            event_data.get(
                                "data"
                            ),
                            dict
                        )
                    ):

                        payload = event_data[
                            "data"
                        ]

                    elif (
                        isinstance(
                            event_data.get(
                                "payload"
                            ),
                            dict
                        )
                    ):

                        payload = event_data[
                            "payload"
                        ]

                    if not isinstance(
                        payload,
                        dict
                    ):

                        continue

                    # =================================================
                    # CONNECTED
                    # =================================================

                    if (
                        str(
                            payload.get(
                                "status",
                                ""
                            )
                        ).lower()
                        ==
                        "connected"
                    ):

                        continue

                    # =================================================
                    # GOODY BAG
                    # =================================================

                    if is_goody_bag(
                        payload
                    ):

                        print(
                            "⏭️ Goody Bag atlandı."
                        )

                        continue

                    # =================================================
                    # USERNAME
                    # =================================================

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
                    )

                    if not username:

                        continue

                    clean_username = (
                        str(username)
                        .replace(
                            "@",
                            ""
                        )
                        .strip()
                    )

                    if not clean_username:

                        continue

                    # =================================================
                    # ELMAS
                    # =================================================

                    coins_raw = (
                        payload.get(
                            "coins"
                        )
                        or
                        payload.get(
                            "amount"
                        )
                        or
                        payload.get(
                            "elmas"
                        )
                        or
                        payload.get(
                            "diamond"
                        )
                        or
                        0
                    )

                    amount = to_int(
                        coins_raw
                    )

                    if amount is None:

                        continue

                    if amount < 10:

                        continue

                    # =================================================
                    # İZLEYİCİ
                    # =================================================

                    room_viewers = (
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
                        0
                    )

                    # =================================================
                    # KİŞİ SAYISI
                    # =================================================

                    chest_people = (
                        get_chest_people(
                            payload
                        )
                    )

                    if chest_people is None:

                        print(
                            "⚠️ Kişi sayısı bulunamadı:"
                            f" @{clean_username}"
                        )

                        continue

                    # =================================================
                    # LEVEL
                    # =================================================

                    level = (
                        payload.get(
                            "level"
                        )
                        or
                        0
                    )

                    # =================================================
                    # DUPLICATE KEY
                    # =================================================

                    cache_key = create_cache_key(
                        payload,
                        clean_username,
                        amount,
                        chest_people
                    )

                    print(
                        f"🔑 HAZİNE KEY: {cache_key}"
                    )

                    # =================================================
                    # ATOMİK UPSTASH KONTROLÜ
                    # =================================================

                    cache_result = await asyncio.to_thread(
                        check_and_save_cache,
                        cache_key
                    )

                    # -------------------------------------------------
                    # UPSTASH HATASI
                    # -------------------------------------------------

                    if cache_result is None:

                        print(
                            "⛔ Upstash doğrulanamadı."
                        )

                        print(
                            "⏭️ Güvenlik nedeniyle "
                            "bildirim gönderilmiyor."
                        )

                        continue

                    # -------------------------------------------------
                    # BAŞKA BOT ÖNCE GÖNDERDİ
                    # -------------------------------------------------

                    if cache_result is False:

                        print(
                            "⏭️ AYNI HAZİNE "
                            "GÖNDERİLMEDİ."
                        )

                        continue

                    # =================================================
                    # LINK
                    # =================================================

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

                    # =================================================
                    # MESAJ
                    # =================================================

                    mesaj = (
                        "🎁 **HAZİNE SANDIĞI**\n"
                        f"👤 **YAYINCI:** "
                        f"`@{clean_username}`\n"
                        f"👁️ **İZLEYİCİ:** "
                        f"{room_viewers}\n"
                        f"💎 **ELMAS:** "
                        f"{amount}\n"
                        f"📦 **DAĞITILAN:** "
                        f"{chest_people} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    # =================================================
                    # TELEGRAM
                    # =================================================

                    sent = await send_telegram_async(
                        mesaj
                    )

                    if sent:

                        print(
                            "✅ GÖNDERİLDİ: "
                            f"@{clean_username} | "
                            f"{amount} elmas | "
                            f"{chest_people} kişi"
                        )

                    else:

                        print(
                            "❌ Telegram gönderilemedi."
                        )

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
