import asyncio
import json
import os

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

BOT_TOKEN = os.getenv("8910200072:AAHKi4G2GkhWupvBIfx2KoCruKrmMcTEbYw")
AUTHORIZED_CHAT_ID = os.getenv("5050032521")

DATA_FILE = "takip_listesi.json"
CHAT_ID_FILE = "chat_id.txt"

# 50 ve üzeri mor zarflar bildirilecek
MIN_CHEST_VALUE = 50

# Aynı zarfın tekrar bildirilmesini engeller
sent_envelopes = set()

# Aktif TikTok takip görevleri
tracking_tasks = {}

# Liste işlemleri için kilit
users_lock = asyncio.Lock()

# Telegram uygulaması
telegram_application = None


# =========================================================
# TAKİP LİSTESİ
# =========================================================

def load_users():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return list(dict.fromkeys(
            str(user).replace("@", "").strip().lower()
            for user in data
            if str(user).strip()
        ))

    except Exception as e:
        print(f"⚠️ Takip listesi okunamadı: {e}")
        return []


def save_users(users):
    try:
        users = sorted(set(
            str(user).replace("@", "").strip().lower()
            for user in users
            if str(user).strip()
        ))

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                users,
                f,
                ensure_ascii=False,
                indent=2
            )

        print("💾 Takip listesi kaydedildi.")

    except Exception as e:
        print(f"❌ Takip listesi kaydedilemedi: {e}")


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
        with open(CHAT_ID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())

    except Exception:
        return None


# =========================================================
# TELEGRAM MESAJ GÖNDER
# =========================================================

async def send_telegram(message):
    chat_id = load_chat_id()

    if not chat_id:
        print("⚠️ CHAT_ID bulunamadı.")
        return

    if telegram_application is None:
        print("⚠️ Telegram uygulaması hazır değil.")
        return

    try:
        await telegram_application.bot.send_message(
            chat_id=chat_id,
            text=message,
            disable_web_page_preview=False,
        )

        print("📨 Telegram bildirimi gönderildi.")

    except Exception as e:
        print(f"❌ Telegram gönderme hatası: {e}")


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
    context: ContextTypes.DEFAULT_TYPE
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

        tracking_tasks[username] = asyncio.create_task(
            takip_et(username)
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
    context: ContextTypes.DEFAULT_TYPE
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

        tracking_tasks.pop(username, None)

    await update.message.reply_text(
        f"🗑️ @{username} takip listesinden çıkarıldı."
    )


# =========================================================
# /LİSTE
# =========================================================

async def liste_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

    for i, username in enumerate(users, 1):

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

    await update.message.reply_text(text)


# =========================================================
# /YARDIM
# =========================================================

async def yardim_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
        f"{MIN_CHEST_VALUE}"
    )


# =========================================================
# MOR ZARF DEĞERİ
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

            if isinstance(value, (int, float)):
                return int(value)

            if isinstance(value, str):

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

            # =================================================
            # CANLI YAYINA BAĞLANDI
            # =================================================

            @client.on(ConnectEvent)
            async def on_connect(event):

                print(
                    f"✅ @{username} TikTok LIVE'a bağlandı!"
                )

            # =================================================
            # BAĞLANTI KESİLDİ
            # =================================================

            @client.on(DisconnectEvent)
            async def on_disconnect(event):

                print(
                    f"❌ @{username} bağlantısı kesildi."
                )

            # =================================================
            # ENVELOPE / MOR ZARF
            # =================================================

            @client.on(EnvelopeEvent)
            async def on_envelope(event):

                info = get_envelope_info(event)

                if not info:
                    return

                envelope_id = getattr(
                    info,
                    "envelope_id",
                    ""
                )

                if not envelope_id:
                    return

                display = str(
                    getattr(
                        event,
                        "display",
                        ""
                    )
                )

                diamond = getattr(
                    info,
                    "diamond_count",
                    0
                )

                people = getattr(
                    info,
                    "people_count",
                    0
                )

                sender = getattr(
                    info,
                    "send_user_name",
                    ""
                )

                # =================================================
                # TERMINAL TEST / KAYIT
                # =================================================

                print("")
                print("=" * 70)
                print("📨 ENVELOPE EVENT")
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

                # =================================================
                # HIDE EVENTLERİ BİLDİRİM YAPMA
                # =================================================

                if "ENVELOPE_DISPLAY_NEW" not in display:

                    print(
                        "⏭️ Yeni zarf olayı değil."
                    )

                    return

                # =================================================
                # TEKRAR KONTROL
                # =================================================

                if envelope_id in sent_envelopes:

                    print(
                        "♻️ Bu mor zarf daha önce bildirildi."
                    )

                    return

                # =================================================
                # DEĞER
                # =================================================

                envelope_value = get_envelope_value(
                    event
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

                # =================================================
                # 50 FİLTRESİ
                # =================================================

                if envelope_value < MIN_CHEST_VALUE:

                    print(
                        f"⏭️ {envelope_value} < "
                        f"{MIN_CHEST_VALUE}, "
                        f"bildirim gönderilmiyor."
                    )

                    return

                # =================================================
                # KAYDET
                # =================================================

                sent_envelopes.add(
                    envelope_id
                )

                # =================================================
                # TIKTOK CANLI YAYIN LINKİ
                # =================================================

                live_url = (
                    f"https://www.tiktok.com/"
                    f"@{username}/live"
                )

                # =================================================
                # TELEGRAM BUTONU
                # =================================================

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

                # =================================================
                # TELEGRAM MESAJI
                # =================================================

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

            # =================================================
            # TIKTOK'A BAĞLAN
            # =================================================

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

        # =================================================
        # YENİDEN DENE
        # =================================================

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

    telegram_application.add_handler(
        CommandHandler(
            "ekle",
            ekle_command
        )
    )

    telegram_application.add_handler(
        CommandHandler(
            "sil",
            sil_command
        )
    )

    telegram_application.add_handler(
        CommandHandler(
            "liste",
            liste_command
        )
    )

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
            "❌ TELEGRAM_BOT_TOKEN bulunamadı."
        )

        print(
            "Termux'ta token değişkenini ayarlamalısın."
        )

        return

    users = load_users()

    print("")
    print("=" * 60)
    print("🟣 MOR ZARF TELEGRAM BOTU")
    print("=" * 60)

    print(
        f"👥 Takip edilen hesap: "
        f"{len(users)}"
    )

    print(
        "📡 Otomatik takip: AKTİF"
    )

    print(
        "🟣 Mor zarf sistemi: AKTİF"
    )

    print(
        f"💎 Minimum değer: "
        f"{MIN_CHEST_VALUE}"
    )

    print("=" * 60)

    await start_telegram_bot()

    # =========================================================
    # KAYITLI KULLANICILARI OTOMATİK BAŞLAT
    # =========================================================

    for username in users:

        if username in tracking_tasks:
            continue

        tracking_tasks[username] = (
            asyncio.create_task(
                takip_et(username)
            )
        )

        print(
            f"▶️ Otomatik takip: @{username}"
        )

    print("")
    print(
        "🟣 Bot hazır. Mor zarf bekleniyor..."
    )

    # =========================================================
    # BOTU AÇIK TUT
    # =========================================================

    try:

        await asyncio.Event().wait()

    finally:

        print(
            "🛑 Bot kapatılıyor..."
        )

        for task in tracking_tasks.values():
            task.cancel()

        await asyncio.gather(
            *tracking_tasks.values(),
            return_exceptions=True
        )

        if telegram_application:

            try:
                await telegram_application.updater.stop()
            except Exception:
                pass

            try:
                await telegram_application.stop()
            except Exception:
                pass

            try:
                await telegram_application.shutdown()
            except Exception:
                pass


# =========================================================
# BAŞLAT
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
