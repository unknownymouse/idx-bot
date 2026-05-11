"""
IDX StockFlow Bot - Telegram Bot untuk Sinyal Saham Oversold IDX
Jalankan: python bot.py
"""

import logging
import asyncio
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from scanner import IDXScanner
from config import BOT_TOKEN, CHAT_ID_LIST, SCAN_TIME

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

scanner = IDXScanner()


# ─────────────────────────────────────────────
#  HELPER: Format pesan sinyal
# ─────────────────────────────────────────────

def format_signal_message(signals: list, scan_count: int) -> str:
    now = datetime.now().strftime("%d %b %Y · %H:%M WIB")

    if not signals:
        return (
            "📊 *IDX Full Scan — Oversold Signals*\n"
            f"🕐 {now}\n\n"
            "❌ *Tidak ada sinyal BUY ditemukan saat ini.*\n\n"
            "Kondisi pasar sedang tidak ideal untuk entry.\n"
            f"_Scan: {scan_count} saham IDX_"
        )

    lines = [
        "📊 *IDX Full Scan — Oversold Signals*",
        f"🕐 {now}",
        "",
        "🟢 *BUY SIGNALS DITEMUKAN:*",
        ""
    ]

    for s in signals:
        change_icon = "📈" if s["change"] >= 0 else "📉"
        lines += [
            f"━━━━━━━━━━━━━━━━━━",
            f"🏷 *{s['ticker']}* — {s['name']}",
            f"💰 Harga: Rp {s['price']:,.0f}",
            f"{change_icon} Perubahan: {s['change']:+.2f}%",
            f"📦 Volume: {s['volume_b']:.1f}B ({s['vol_ratio']:.1f}x normal)",
            f"📉 RSI({s['rsi_period']}): *{s['rsi']:.1f}* ← Oversold",
            f"📊 MACD: {'↗ Bullish crossover' if s['macd_signal'] else '—'}",
            f"🎯 Target: Rp {s['target']:,.0f} (+{s['upside']:.1f}%)",
            f"🛡 Stop Loss: Rp {s['stop_loss']:,.0f}",
            f"💡 Sektor: {s['sector']}",
        ]

    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "",
        "✅ *Kondisi Terpenuhi:*",
        "▫️ Harga sudah turun terlalu dalam (oversold)",
        "▫️ Indikator momentum mulai balik arah",
        "▫️ Volume naik — ada akumulasi diam-diam",
        "",
        f"📌 Scan: {scan_count} saham IDX | BUY: {len(signals)}",
        "",
        "⚠️ _Bukan rekomendasi investasi. DYOR & manage risiko._"
    ]

    return "\n".join(lines)


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Scan Sekarang", callback_data="scan"),
            InlineKeyboardButton("⚡ Top 5", callback_data="top5"),
        ],
        [
            InlineKeyboardButton("❓ Cara Kerja", callback_data="howto"),
            InlineKeyboardButton("⚙️ Status Bot", callback_data="status"),
        ],
        [
            InlineKeyboardButton("⚠️ Disclaimer", callback_data="disclaimer"),
        ]
    ])


# ─────────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Selamat datang di IDX StockFlow Bot!*\n\n"
        "Bot ini memindai seluruh saham IDX dan mencari saham "
        "*oversold* dengan potensi rebound.\n\n"
        "🔍 Metodologi:\n"
        "▫️ RSI < 30 (oversold)\n"
        "▫️ MACD bullish crossover\n"
        "▫️ Volume spike (akumulasi)\n"
        "▫️ Harga di Bollinger Band bawah\n\n"
        "✅ *Cocok untuk swing trade 3–10 hari*\n\n"
        "Pilih menu di bawah untuk mulai:"
    )
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "⏳ Sedang scan saham IDX...\n_Mohon tunggu 15–30 detik_",
        parse_mode="Markdown"
    )
    signals, count = scanner.scan_oversold(top_n=5)
    result = format_signal_message(signals, count)
    await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_keyboard())


async def cmd_top5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "⚡ Mencari Top 5 sinyal terkuat...",
        parse_mode="Markdown"
    )
    signals, count = scanner.scan_oversold(top_n=5, strict=True)
    result = format_signal_message(signals, count)
    await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_keyboard())


async def cmd_howto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "⚙️ *Cara Kerja Bot Oversold IDX*\n\n"
        "*1. Data Source*\n"
        "Bot mengambil data dari Yahoo Finance (delay ~15 menit) "
        "untuk semua saham IDX.\n\n"
        "*2. Filter Oversold*\n"
        "▫️ RSI 14-hari di bawah 30\n"
        "▫️ Harga menyentuh Bollinger Band bawah\n"
        "▫️ Penurunan > 10% dari harga tertinggi 20 hari\n\n"
        "*3. Konfirmasi Momentum*\n"
        "▫️ MACD line crossing signal line ke atas\n"
        "▫️ Stochastic RSI < 20 lalu naik\n\n"
        "*4. Filter Volume*\n"
        "▫️ Volume hari ini > 1.5x rata-rata 20 hari\n"
        "▫️ Menandakan akumulasi institusional\n\n"
        "*5. Target & Stop Loss*\n"
        "▫️ Target: resistance terdekat / +15%\n"
        "▫️ Stop Loss: -5% dari harga entry\n\n"
        "📅 *Scan otomatis:* Setiap hari pukul 09.15 WIB\n"
        "_(15 menit setelah market buka)_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())


# ─────────────────────────────────────────────
#  CALLBACK QUERY (tombol inline)
# ─────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "scan":
        await query.edit_message_text(
            "⏳ Sedang scan saham IDX...\n_Mohon tunggu 15–30 detik_",
            parse_mode="Markdown"
        )
        signals, count = scanner.scan_oversold(top_n=5)
        result = format_signal_message(signals, count)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "top5":
        await query.edit_message_text(
            "⚡ Mencari Top 5 sinyal terkuat...",
            parse_mode="Markdown"
        )
        signals, count = scanner.scan_oversold(top_n=5, strict=True)
        result = format_signal_message(signals, count)
        await query.edit_message_text(result, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "howto":
        msg = (
            "⚙️ *Cara Kerja Bot Oversold IDX*\n\n"
            "Bot scan semua saham IDX dan cari yang memenuhi:\n\n"
            "✅ RSI < 30 — harga oversold\n"
            "✅ MACD bullish crossover\n"
            "✅ Volume spike > 1.5x normal\n"
            "✅ Harga di Bollinger Band bawah\n\n"
            "Kalau 3–4 kondisi terpenuhi → *sinyal BUY keluar*\n\n"
            "📅 Scan otomatis tiap hari pukul *09.15 WIB*"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "status":
        now = datetime.now().strftime("%d %b %Y %H:%M WIB")
        msg = (
            f"🤖 *Status Bot*\n\n"
            f"✅ Bot online & aktif\n"
            f"🕐 Waktu server: {now}\n"
            f"📅 Scan otomatis: 09.15 WIB\n"
            f"📊 Saham IDX di-monitor: ~800+\n"
            f"🔄 Data delay: ~15 menit (Yahoo Finance)\n"
            f"📡 Sumber data: Yahoo Finance (.JK)"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "disclaimer":
        msg = (
            "⚠️ *DISCLAIMER PENTING*\n\n"
            "Bot ini adalah *tools analisis teknikal otomatis*, "
            "bukan rekomendasi investasi resmi.\n\n"
            "• Semua sinyal bersifat *edukatif*\n"
            "• Investasi selalu mengandung risiko\n"
            "• Selalu lakukan riset mandiri (DYOR)\n"
            "• Past performance ≠ future result\n"
            "• Gunakan hanya dana siap hilang\n"
            "• Bot tidak berafiliasi dengan BEI/OJK\n\n"
            "_Pembuat bot tidak bertanggung jawab atas keputusan investasi._"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())


# ─────────────────────────────────────────────
#  AUTO SCAN (Scheduled Job)
# ─────────────────────────────────────────────

async def auto_scan_job(context: ContextTypes.DEFAULT_TYPE):
    """Kirim sinyal otomatis setiap hari ke semua chat terdaftar."""
    logger.info("Menjalankan auto scan terjadwal...")
    signals, count = scanner.scan_oversold(top_n=5)
    result = format_signal_message(signals, count)

    for chat_id in CHAT_ID_LIST:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=result,
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            logger.info(f"Sinyal dikirim ke chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Gagal kirim ke {chat_id}: {e}")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Daftarkan command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("top5", cmd_top5))
    app.add_handler(CommandHandler("cara", cmd_howto))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Auto scan terjadwal setiap hari jam 09:15 WIB (UTC+7 = 02:15 UTC)
    scan_hour, scan_minute = map(int, SCAN_TIME.split(":"))
    utc_hour = (scan_hour - 7) % 24

    app.job_queue.run_daily(
        auto_scan_job,
        time=time(hour=utc_hour, minute=scan_minute),
        name="daily_scan"
    )

    logger.info("✅ IDX StockFlow Bot aktif dan berjalan...")
    logger.info(f"📅 Auto scan dijadwalkan: {SCAN_TIME} WIB")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
