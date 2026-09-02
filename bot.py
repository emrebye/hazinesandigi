import asyncio
import json
import os
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent,
    DisconnectEvent,
    EnvelopeEvent,
)


# =========================================================
# AYARLAR
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

AUTHORIZED_CHAT_ID = os.getenv("AUTHORIZED_CHAT_ID")

CHAT_ID_FILE = "chat_id.txt"
DATA_FILE = "takip_listesi.json"

# 50 ve üzeri mor zarflar bildirilecek
MIN_CHEST_VALUE = 50


# =========================================================
# UPSTASH
# İKİ BOTTA DA AYNI UPSTASH HESABI KULLANILACAK
# =========================================================

UPSTASH_REDIS_REST_URL = os.getenv(
    "UPSTASH_REDIS_REST_URL"
)

UPSTASH_REDIS_REST_TOKEN = os.getenv(
    "UPSTASH_REDIS_REST_TOKEN"
)

# Aynı olay 30 dakika boyunca tekrar gönderilmez
CACHE_TIMEOUT = 1800


# =========================================================
# GLOBAL
# =========================================================

sent_envelopes = set()

tracking_tasks = {}

users_lock = asyncio.Lock()

telegram_application = None


# =========================================================
# UPSTASH DUPLICATE KONTROLÜ
# =========================================================

def claim_envelope(
    envelope_id,
    username,
    diamond,
    people,
    sender,
):
    """
    Aynı mor zarfı birden fazla bot yakalarsa
    Telegram'a yalnızca İLK bot gönderir.

    Redis:
        SET key 1 NX EX 1800

    NX sayesinde işlem atomiktir.
    """

    if not UPSTASH_REDIS_REST_URL:
        print("❌ UPSTASH_REDIS_REST_URL bulunamadı.")
        print("⛔ Bildirim gönderilmiyor.")
        return False

    if not UPSTASH_REDIS_REST_TOKEN:
        print("❌ UPSTASH_REDIS_REST_TOKEN bulunamadı.")
        print("⛔ Bildirim gönderilmiyor.")
        return False

    # -----------------------------------------------------
    # Öncelik gerçek Envelope ID
    # -----------------------------------------------------

    if envelope_id:
        cache_key = (
            f"mor_zarf:event:{envelope_id}"
        )

    else:
        # ID bulunamazsa güçlü yedek anahtar
        cache_key = (
            f"mor_zarf:"
            f"{str(username).lower()}:"
            f"{diamond}:"
            f"{people}:"
            f"{str(sender).lower()}"
        )

    print(
        f"🔑 Upstash key: {cache_key}"
    )

    try:

        headers = {
            "Authorization":
                f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
            "Content-Type":
                "application/json",
        }

        command = [
            "SET",
            cache_key,
            "1",
            "NX",
            "EX",
            str(CACHE_TIMEOUT),
        ]

        response = requests.post(
            UPSTASH_REDIS_REST_URL,
            headers=headers,
            json=command,
            timeout=8,
        )

        response.raise_for_status()

        data = response.json()

        result = data.get("result")

        # -------------------------------------------------
        # İLK BOT
        # -------------------------------------------------

        if str(result).upper() == "OK":

            print(
                "🟢 UPSTASH: İLK BOT KAZANDI"
            )

            print(
                "📨 Telegram gönderilebilir."
            )

            return True

        # -------------------------------------------------
        # BAŞKA BOT ÖNCEDEN ALMIŞ
        # -------------------------------------------------

        print(
            "♻️ UPSTASH: BU ZARF ZATEN ALINMIŞ"
        )

        print(
            "⏭️ Telegram gönderilmiyor."
        )

        return False

    except Exception as e:

        print(
            "❌ UPSTASH HATASI:"
        )

        print(e)

        # Upstash çalışmıyorsa iki botun da
        # aynı mesajı göndermemesi için gönderme.
        print(
            "⛔ Güvenlik nedeniyle Telegram gönderilmiyor."
        )

        return False


# =========================================================
# TAKİP LİSTESİ
# =========================================================

def load_users():

    if not os.path.exists(DATA_FILE):
        return []

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, list):
            return []

        users = []

        for user in data:

            username = (
                str(user)
                .replace("@", "")
                .strip()
                .lower()
            )

            if username:
                users.append(username)

        return list(dict.fromkeys(users))

    except Exception as e:

        print(
            f"⚠️ Takip listesi okunamadı: {e}"
        )

        return []


# =========================================================
# TAKİP LİSTESİ KAYDET
# =========================================================

def save_users(users):

    try:

        clean_users = []

        for user in users:

            username = (
                str(user)
                .replace("@", "")
                .strip()
                .lower()
            )

            if username:
                clean_users.append(username)

        clean_users = sorted(
            set(clean_users)
        )

        with open(
            DATA_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                clean_users,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(
            "💾 Takip listesi kaydedildi."
        )

    except Exception as e:

        print(
            f"❌ Takip listesi kaydedilemedi: {e}"
        )


# =========================================================
# CHAT ID
# =========================================================

def load_chat_id():

    value = os.getenv("CHAT_ID")

    if value:

        try:
            return int(value.strip())

        except ValueError:
            pass

    if not os.path.exists(CHAT_ID_FILE):
        return None

    try:

        with open(
            CHAT_ID_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return int(
                f.read().strip()
            )

    except Exception:

        return None


# =========================================================
# YETKİ
# =========================================================

def authorized(update: Update):

    if not AUTHORIZED_CHAT_ID:
        return False

    if not update.effective_chat:
        return False

    try:

        return (
            update.effective_chat.id
            == int(AUTHORIZED_CHAT_ID)
        )

    except Exception:

        return False


# =========================================================
# /EKLE
# =========================================================

async def ekle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    if not context.args:

        await update.message.reply_text(
            "❌ Kullanıcı adı yazmalısın.\n\n"
            "Örnek:\n"
            "/ekle @kullanici"
        )

        return

    username = (
        context.args[0]
        .replace("@", "")
        .strip()
        .lower()
    )

    if not username:

        await update.message.reply_text(
            "❌ Geçerli bir kullanıcı adı yaz."
        )

        return

    async with users_lock:

        users = load_users()

        if username in users:

            await update.message.reply_text(
                f"⚠️ @{username} zaten takip ediliyor."
            )

            return

        users.append(username)

        save_users(users)

    if username not in tracking_tasks:

        tracking_tasks[username] = (
            asyncio.create_task(
                takip_et(username)
            )
        )

    await update.message.reply_text(
        f"✅ @{username} takip listesine eklendi.\n\n"
        f"🟣 Mor zarf otomatik takibi başladı."
    )


# =========================================================
# /SİL
# =========================================================

async def sil_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    if not context.args:

        await update.message.reply_text(
            "❌ Kullanıcı adı yazmalısın.\n\n"
            "Örnek:\n"
            "/sil @kullanici"
        )

        return

    username = (
        context.args[0]
        .replace("@", "")
        .strip()
        .lower()
    )

    async with users_lock:

        users = load_users()

        if username not in users:

            await update.message.reply_text(
                f"⚠️ @{username} takip listesinde yok."
            )

            return

        users.remove(username)

        save_users(users)

    task = tracking_tasks.get(username)

    if task:

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass

        except Exception:
            pass

        tracking_tasks.pop(
            username,
            None
        )

    await update.message.reply_text(
        f"🗑️ @{username} takip listesinden çıkarıldı."
    )


# =========================================================
# /LİSTE
# =========================================================

async def liste_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    users = load_users()

    if not users:

        await update.message.reply_text(
            "📭 Takip listesi boş."
        )

        return

    text = "📋 TAKİP LİSTESİ\n\n"

    for i, username in enumerate(
        users,
        1
    ):

        if username in tracking_tasks:
            durum = "🟢"
        else:
            durum = "🔴"

        text += (
            f"{i}. {durum} @{username}\n"
        )

    text += (
        f"\n👥 Toplam: {len(users)}"
    )

    await update.message.reply_text(
        text
    )


# =========================================================
# /YARDIM
# =========================================================

async def yardim_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    await update.message.reply_text(

        "🟣 MOR ZARF BOTU\n\n"

        "Komutlar:\n\n"

        "/ekle @kullanici\n"
        "➡️ TikTok kullanıcısı ekle\n\n"

        "/sil @kullanici\n"
        "➡️ TikTok kullanıcısını sil\n\n"

        "/liste\n"
        "➡️ Takip listesini göster\n\n"

        "/yardim\n"
        "➡️ Yardım mesajını göster\n\n"

        "📡 Takip sistemi otomatik çalışır.\n"
        "▶️ Başlat komutu gerekmez.\n"
        "⏹️ Durdur komutu gerekmez.\n\n"

        f"💎 Minimum mor zarf değeri: "
        f"{MIN_CHEST_VALUE}\n\n"

        "♻️ Ortak Upstash duplicate sistemi: AKTİF"
    )


# =========================================================
# ENVELOPE INFO
# =========================================================

def get_envelope_info(event):

    try:

        info = getattr(
            event,
            "envelope_info",
            None
        )

        if info:
            return info

    except Exception:
        pass

    return None


# =========================================================
# MOR ZARF DEĞERİ
# =========================================================

def get_envelope_value(event):

    info = get_envelope_info(event)

    if not info:
        return None

    fields = [

        "diamond_count",
        "diamondCount",

        "diamond",
        "diamonds",

        "coin_count",
        "coinCount",

        "coins",
        "coin",

        "value",
        "amount",
        "reward",
        "count",
    ]

    for field in fields:

        try:

            value = getattr(
                info,
                field,
                None
            )

            if value is None:
                continue

            if isinstance(
                value,
                (int, float)
            ):

                return int(value)

            if isinstance(
                value,
                str
            ):

                cleaned = (
                    value
                    .replace(",", "")
                    .strip()
                )

                if cleaned.isdigit():
                    return int(cleaned)

        except Exception:
            continue

    return None


# =========================================================
# MOR ZARF TAKİBİ
# =========================================================

async def takip_et(username):

    username = (
        username
        .replace("@", "")
        .strip()
        .lower()
    )

    while True:

        client = None

        try:

            print("")
            print("=" * 60)

            print(
                f"📡 @{username} takip başlatılıyor..."
            )

            print("=" * 60)

            client = TikTokLiveClient(
                unique_id=username
            )

            # -------------------------------------------------
            # BAĞLANDI
            # -------------------------------------------------

            @client.on(ConnectEvent)
            async def on_connect(event):

                print(
                    f"✅ @{username} TikTok LIVE'a bağlandı!"
                )

            # -------------------------------------------------
            # BAĞLANTI KESİLDİ
            # -------------------------------------------------

            @client.on(DisconnectEvent)
            async def on_disconnect(event):

                print(
                    f"❌ @{username} bağlantısı kesildi."
                )

            # -------------------------------------------------
            # ENVELOPE / MOR ZARF
            # -------------------------------------------------

            @client.on(EnvelopeEvent)
            async def on_envelope(event):

                info = get_envelope_info(
                    event
                )

                if not info:
                    return

                # ---------------------------------------------
                # ENVELOPE ID
                # ---------------------------------------------

                envelope_id = getattr(
                    info,
                    "envelope_id",
                    ""
                )

                if not envelope_id:

                    # Bazı sürümlerde farklı isim olabilir
                    envelope_id = getattr(
                        info,
                        "envelopeId",
                        ""
                    )

                # ---------------------------------------------
                # DISPLAY
                # ---------------------------------------------

                display = str(
                    getattr(
                        event,
                        "display",
                        ""
                    )
                )

                # ---------------------------------------------
                # DIAMOND
                # ---------------------------------------------

                diamond = getattr(
                    info,
                    "diamond_count",
                    0
                )

                if not diamond:

                    diamond = getattr(
                        info,
                        "diamondCount",
                        0
                    )

                # ---------------------------------------------
                # PEOPLE
                # ---------------------------------------------

                people = getattr(
                    info,
                    "people_count",
                    0
                )

                if not people:

                    people = getattr(
                        info,
                        "peopleCount",
                        0
                    )

                # ---------------------------------------------
                # SENDER
                # ---------------------------------------------

                sender = getattr(
                    info,
                    "send_user_name",
                    ""
                )

                if not sender:

                    sender = getattr(
                        info,
                        "sendUserName",
                        ""
                    )

                # ---------------------------------------------
                # TERMINAL
                # ---------------------------------------------

                print("")
                print("=" * 70)

                print(
                    "📨 ENVELOPE EVENT"
                )

                print(
                    f"👤 Yayın: @{username}"
                )

                print(
                    f"💎 Diamond: {diamond}"
                )

                print(
                    f"👥 Kişi: {people}"
                )

                print(
                    f"👤 Gönderen: {sender}"
                )

                print(
                    f"🆔 ID: {envelope_id}"
                )

                print(
                    f"📌 Display: {display}"
                )

                print("=" * 70)

                # ---------------------------------------------
                # SADECE YENİ ZARF
                # ---------------------------------------------

                if (
                    "ENVELOPE_DISPLAY_NEW"
                    not in display
                ):

                    print(
                        "⏭️ Yeni zarf olayı değil."
                    )

                    return

                # ---------------------------------------------
                # LOKAL DUPLICATE
                # ---------------------------------------------

                if envelope_id:

                    if envelope_id in sent_envelopes:

                        print(
                            "♻️ Lokal: zarf daha önce işlendi."
                        )

                        return

                # ---------------------------------------------
                # DEĞER
                # ---------------------------------------------

                envelope_value = (
                    get_envelope_value(event)
                )

                if envelope_value is None:

                    print(
                        "⚠️ Mor zarf bulundu fakat "
                        "değeri okunamadı."
                    )

                    return

                print(
                    f"🟣 MOR ZARF BULUNDU! "
                    f"💎 {envelope_value}"
                )

                # ---------------------------------------------
                # 50 FİLTRESİ
                # ---------------------------------------------

                if (
                    envelope_value
                    < MIN_CHEST_VALUE
                ):

                    print(
                        f"⏭️ {envelope_value} < "
                        f"{MIN_CHEST_VALUE}, "
                        f"bildirim gönderilmiyor."
                    )

                    return

                # ---------------------------------------------
                # UPSTASH ORTAK DUPLICATE
                # ---------------------------------------------

                claimed = claim_envelope(

                    envelope_id=envelope_id,

                    username=username,

                    diamond=envelope_value,

                    people=people,

                    sender=sender,
                )

                # ---------------------------------------------
                # BAŞKA BOT ALMIŞSA
                # ---------------------------------------------

                if not claimed:

                    return

                # ---------------------------------------------
                # LOKALE KAYDET
                # ---------------------------------------------

                if envelope_id:

                    sent_envelopes.add(
                        envelope_id
                    )

                # ---------------------------------------------
                # TIKTOK LIVE LINK
                # ---------------------------------------------

                live_url = (
                    f"https://www.tiktok.com/"
                    f"@{username}/live"
                )

                # ---------------------------------------------
                # TELEGRAM BUTONU
                # ---------------------------------------------

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔴 CANLI YAYINA GİT",
                                url=live_url
                            )
                        ]
                    ]
                )

                # ---------------------------------------------
                # TELEGRAM MESAJI
                # ---------------------------------------------

                message = (

                    "🟣🎁 MOR ZARF BULUNDU!\n\n"

                    f"📺 Yayın: @{username}\n"

                    f"💎 Miktar: "
                    f"{envelope_value}\n"

                    f"👥 Kişi: "
                    f"{people}\n"

                    f"👤 Gönderen: "
                    f"@{sender if sender else 'Bilinmiyor'}\n\n"

                    "⚡ Mor zarf yakalandı!"
                )

                chat_id = load_chat_id()

                if not chat_id:

                    print(
                        "⚠️ CHAT_ID bulunamadı."
                    )

                    return

                if telegram_application is None:

                    print(
                        "⚠️ Telegram uygulaması hazır değil."
                    )

                    return

                # ---------------------------------------------
                # TELEGRAM GÖNDER
                # ---------------------------------------------

                try:

                    await telegram_application.bot.send_message(

                        chat_id=chat_id,

                        text=message,

                        reply_markup=keyboard,

                        disable_web_page_preview=False,
                    )

                    print(
                        "📨 🟣 MOR ZARF Telegram'a gönderildi!"
                    )

                except Exception as e:

                    print(
                        "❌ Telegram mesaj hatası:"
                    )

                    print(e)

            # -------------------------------------------------
            # TIKTOK'A BAĞLAN
            # -------------------------------------------------

            await client.connect()

        except asyncio.CancelledError:

            print(
                f"🛑 @{username} takip görevi durduruldu."
            )

            break

        except Exception as e:

            print("")
            print(
                f"⚠️ @{username} bağlantı hatası:"
            )

            print(e)

        finally:

            if client:

                try:

                    await client.disconnect()

                except Exception:
                    pass

        # -----------------------------------------------------
        # YENİDEN DENE
        # -----------------------------------------------------

        print(
            f"🔄 @{username} için "
            f"10 saniye sonra tekrar denenecek..."
        )

        try:

            await asyncio.sleep(10)

        except asyncio.CancelledError:

            print(
                f"🛑 @{username} takip görevi durduruldu."
            )

            break


# =========================================================
# TELEGRAM BOTU
# =========================================================

async def start_telegram_bot():

    global telegram_application

    telegram_application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /ekle
    telegram_application.add_handler(
        CommandHandler(
            "ekle",
            ekle_command
        )
    )

    # /sil
    telegram_application.add_handler(
        CommandHandler(
            "sil",
            sil_command
        )
    )

    # /liste
    telegram_application.add_handler(
        CommandHandler(
            "liste",
            liste_command
        )
    )

    # /yardim
    telegram_application.add_handler(
        CommandHandler(
            "yardim",
            yardim_command
        )
    )

    await telegram_application.initialize()

    await telegram_application.start()

    await telegram_application.updater.start_polling()

    print(
        "✅ Telegram botu çalışıyor!"
    )


# =========================================================
# ANA PROGRAM
# =========================================================

async def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN bulunamadı."
        )

        print(
            "❌ Render Environment Variables "
            "içinde BOT_TOKEN olmalı."
        )

        return

    if not UPSTASH_REDIS_REST_URL:

        print(
            "❌ UPSTASH_REDIS_REST_URL bulunamadı."
        )

        return

    if not UPSTASH_REDIS_REST_TOKEN:

        print(
            "❌ UPSTASH_REDIS_REST_TOKEN bulunamadı."
        )

        return

    users = load_users()

    print("")
    print("=" * 60)

    print(
        "🟣 MOR ZARF TELEGRAM BOTU"
    )

    print("=" * 60)

    print(
        f"👥 Takip edilen hesap: "
        f"{len(users)}"
   
