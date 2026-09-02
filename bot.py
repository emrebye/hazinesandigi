import asyncio
import json
import os
import requests
import websockets

# ============================================================
# TELEGRAM
# ============================================================

# Güvenlik için token'ı ortam değişkeninden alır.
# Termux'ta:
# export BOT_TOKEN="BOT_TOKENIN"
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "")

CHAT_ID = os.getenv(
    "CHAT_ID",
    "-1004325133382"
)

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
        "AppleWebKit/537.36"
    ),
    "Origin": "https://dichvu321.com",
    "Referer": "https://dichvu321.com/"
}

# ============================================================
# ETİKET KURALI
# ============================================================

TAG_USERNAME = "@jiminienn"

# 100 veya daha fazla elmas
TAG_COINS_MIN = 100

# 5 veya daha az kişi
TAG_RECIPIENTS_MAX = 5

# ============================================================
# TELEGRAM GÖNDER
# ============================================================

async def send_telegram(mesaj):

    if not TELEGRAM_BOT_TOKEN:
        print(
            "❌ BOT_TOKEN bulunamadı."
        )
        return

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "disable_web_page_preview": True
    }

    try:

        loop = asyncio.get_running_loop()

        await loop.run_in_executor(
            None,
            lambda: requests.post(
                url,
                json=payload,
                timeout=5
            )
        )

    except Exception as e:

        print(
            f"⚠️ Telegram hatası: {e}"
        )


# ============================================================
# CANLI AKIŞ
# ============================================================

async def listen_live_feed():

    print("🚀 HAZİNE BOTU BAŞLADI")
    print(
        "🚫 20 elmas / 16 kişi filtresi AKTİF"
    )
    print(
        f"🏷️ Etiket: {TAG_COINS_MIN}+ elmas "
        f"ve {TAG_RECIPIENTS_MAX} veya daha az kişi"
    )

    while True:

        try:

            # ------------------------------------------------
            # PROXY'DEN WS ADRESİ AL
            # ------------------------------------------------

            loop = asyncio.get_running_loop()

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

            ws_url = (
                f"wss://dichvu321.com{path}"
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

                print("✅ WebSocket bağlandı")

                async for message in websocket:

                    # ========================================
                    # JSON
                    # ========================================

                    try:

                        event_data = json.loads(
                            message
                        )

                    except Exception:

                        continue

                    # ========================================
                    # PAYLOAD
                    # ========================================

                    payload = (
                        event_data.get("data")
                        if isinstance(
                            event_data.get("data"),
                            dict
                        )
                        else event_data
                    )

                    if not isinstance(
                        payload,
                        dict
                    ):
                        continue

                    if payload.get(
                        "status"
                    ) == "connected":

                        continue

                    # ========================================
                    # GOODY BAG KONTROLÜ
                    # ========================================

                    box_type_raw = str(
                        payload.get("type") or ""
                    ).lower()

                    source_raw = str(
                        payload.get("source") or ""
                    ).lower()

                    envelope_info = (
                        payload.get(
                            "envelopeInfo"
                        ) or {}
                    )

                    if not isinstance(
                        envelope_info,
                        dict
                    ):

                        envelope_info = {}

                    business_type = (
                        envelope_info.get(
                            "businessType",
                            1
                        )
                    )

                    is_goody = (
                        business_type == 2
                        or "goody" in box_type_raw
                        or "goody" in source_raw
                    )

                    if is_goody:

                        continue

                    # ========================================
                    # ELMAS
                    # ========================================

                    coins = payload.get(
                        "coins",
                        0
                    )

                    try:

                        coins = int(
                            float(coins)
                        )

                    except Exception:

                        coins = 0

                    if coins <= 0:

                        continue

                    # ========================================
                    # YAYINCI
                    # ========================================

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

                    # ========================================
                    # LEVEL
                    # ========================================

                    level = payload.get(
                        "level",
                        0
                    )

                    try:

                        level = int(
                            float(level)
                        )

                    except Exception:

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
                    # DAĞITILAN KİŞİ
                    # ========================================

                    recipients = payload.get(
                        "canOpen",
                        0
                    )

                    try:

                        recipients = int(
                            float(recipients)
                        )

                    except Exception:

                        recipients = 0

                    # ========================================
                    # İZLEYİCİ
                    # ========================================

                    viewers = (
                        payload.get(
                            "viewerCount"
                        )
                        or payload.get(
                            "userCount"
                        )
                        or envelope_info.get(
                            "viewerCount"
                        )
                        or 0
                    )

                    try:

                        viewers = int(
                            float(viewers)
                        )

                    except Exception:

                        viewers = 0

                    # ========================================
                    # SADECE 20 / 16'YI KALDIR
                    # ========================================

                    if (
                        coins == 20
                        and recipients == 16
                    ):

                        print(
                            "⏭️ KALDIRILDI → "
                            f"@{clean_username} "
                            "| 20 elmas / 16 kişi"
                        )

                        continue

                    # ========================================
                    # LİNK
                    # ========================================

                    live_link = (
                        "https://www.tiktok.com/"
                        f"@{clean_username}/live"
                    )

                    # ========================================
                    # ETİKET KARARI
                    # ========================================

                    should_tag = (
                        coins >= TAG_COINS_MIN
                        and recipients <= TAG_RECIPIENTS_MAX
                    )

                    # ========================================
                    # MESAJ
                    # ========================================

                    mesaj = (
                        f"{box_title}\n"
                        f"👤 YAYINCI: "
                        f"@{clean_username}\n"
                        f"👁️ İZLEYİCİ: "
                        f"{viewers}\n"
                        f"💎 ELMAS: "
                        f"{coins}\n"
                        f"📦 DAĞITILAN: "
                        f"{recipients} KİŞİ\n"
                        f"🔗 {live_link}"
                    )

                    # ========================================
                    # SADECE UYGUNSA ETİKET
                    # ========================================

                    if should_tag:

                        mesaj = (
                            f"🚨 {TAG_USERNAME}\n\n"
                            + mesaj
                        )

                        print(
                            "🚨 ETİKETLİ → "
                            f"@{clean_username} "
                            f"| {coins} elmas "
                            f"| {recipients} kişi"
                        )

                    else:

                        print(
                            "📩 NORMAL → "
                            f"@{clean_username} "
                            f"| {coins} elmas "
                            f"| {recipients} kişi"
                        )

                    # ========================================
                    # TELEGRAM
                    # ========================================

                    asyncio.create_task(
                        send_telegram(mesaj)
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

    asyncio.run(
        listen_live_feed()
    )
