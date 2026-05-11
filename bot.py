"""
IDX StockFlow Bot v2 — dengan Watchlist, Cek Saham,
Historis Sinyal, Price Alert, dan Laporan Mingguan
"""

import sys
import asyncio
import logging
from datetime import datetime, time, timedelta

# Fix Python 3.12+
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)
import yfinance as yf

from scanner import IDXScanner
from database import (
    init_db, save_signals, get_signals_history, get_signal_stats,
    add_watchlist, remove_watchlist, get_watchlist,
    add_alert, get_alerts, get_all_active_alerts, trigger_alert, delete_alert,
    get_weekly_summary
)
from config import BOT_TOKEN, CHAT_ID_LIST, SCAN_TIME

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

scanner = IDXScanner()

# ConversationHandler states
ALERT_TICKER, ALERT_PRICE, ALERT_DIR = range(3)
WATCH_ACTION = range(1)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Scan IDX", callback_data="scan"),
            InlineKeyboardButton("⚡ Top 5", callback_data="top5"),
        ],
        [
            InlineKeyboardButton("📋 Watchlist", callback_data="watchlist"),
            InlineKeyboardButton("🔔 Alert Harga", callback_data="alert_menu"),
        ],
        [
            InlineKeyboardButton("📊 Historis Sinyal", callback_data="history"),
            InlineKeyboardButton("📅 Laporan Minggu Ini", callback_data="weekly"),
        ],
        [
            InlineKeyboardButton("❓ Cara Kerja", callback_data="howto"),
            InlineKeyboardButton("⚙️ Status", callback_data="status"),
        ],
    ])


def format_signal_message(signals: list, scan_count: int) -> str:
    now = datetime.now().strftime("%d %b %Y · %H:%M WIB")
    if not signals:
        return (
            "📊 *IDX Full Scan — Oversold Signals*\n"
            f"🕐 {now}\n\n"
            "❌ *Tidak ada sinyal BUY saat ini.*\n\n"
            "Pasar belum menunjukkan kondisi oversold yang cukup kuat.\n"
            f"_Scan: {scan_count} saham IDX_"
        )
    lines = [
        "📊 *IDX Full Scan — Oversold Signals*",
        f"🕐 {now}", ""
    ]
    for s in signals:
        icon = "📈" if s["change"] >= 0 else "📉"
        lines += [
            "━━━━━━━━━━━━━━━━━━",
            f"🏷 *{s['ticker']}* — {s['name']}",
            f"💰 Harga: Rp {s['price']:,.0f}",
            f"{icon} Perubahan: {s['change']:+.2f}%",
            f"📦 Volume: {s['volume_b']:.1f}B ({s['vol_ratio']:.1f}x normal)",
            f"📉 RSI: *{s['rsi']:.1f}* ← Oversold",
            f"🎯 Target: Rp {s['target']:,.0f} (+{s['upside']:.1f}%)",
            f"🛡 Stop Loss: Rp {s['stop_loss']:,.0f}",
            f"🏢 Sektor: {s['sector']}",
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━", "",
        f"📌 Scan: {scan_count} saham | BUY: {len(signals)}",
        "",
        "⚠️ _Bukan rekomendasi investasi. DYOR._"
    ]
    return "\n".join(lines)


def get_current_price(ticker: str) -> float | None:
    try:
        data = yf.download(ticker + ".JK", period="1d", interval="1m",
                           progress=False, auto_adjust=True)
        if data is not None and len(data) > 0:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Selamat datang di IDX StockFlow Bot v2!*\n\n"
        "Fitur yang tersedia:\n"
        "🔍 Scan saham oversold IDX\n"
        "📋 Watchlist saham pilihan kamu\n"
        "🔔 Alert otomatis kalau harga kena target\n"
        "📊 Historis sinyal & track record\n"
        "📅 Laporan rekap mingguan\n"
        "🔎 Cek kondisi satu saham: /cek BBRI\n\n"
        "Pilih menu di bawah:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=main_keyboard())


# ─────────────────────────────────────────────
#  /cek TICKER — Fitur 4
# ─────────────────────────────────────────────

async def cmd_cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Cara pakai: /cek BBRI\nContoh: /cek TLKM"
        )
        return

    ticker = context.args[0].upper().replace(".JK", "")
    msg = await update.message.reply_text(
        f"🔍 Menganalisis *{ticker}*...", parse_mode="Markdown"
    )

    result = scanner.analyze(ticker + ".JK", strict=False)

    if result is None:
        # Coba ambil data dasar meski tidak ada sinyal
        try:
            df = yf.download(ticker + ".JK", period="5d", interval="1d",
                             progress=False, auto_adjust=True)
            if df is not None and len(df) > 0:
                price = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                change = (price - prev) / prev * 100
                text = (
                    f"📊 *Analisis {ticker}*\n\n"
                    f"💰 Harga: Rp {price:,.0f}\n"
                    f"📈 Perubahan: {change:+.2f}%\n\n"
                    f"⚪ Status: *Belum memenuhi kriteria sinyal*\n"
                    f"_(RSI belum oversold atau momentum belum balik)_"
                )
            else:
                text = f"❌ Saham *{ticker}* tidak ditemukan. Cek kode sahamnya ya."
        except Exception:
            text = f"❌ Tidak bisa mengambil data *{ticker}*. Cek koneksi internet."
    else:
        macd_txt = "Bullish crossover" if result["macd_signal"] else "Belum crossover"
        text = (
            f"📊 *Analisis Teknikal — {result['ticker']}*\n"
            f"_{result['name']} · {result['sector']}_\n\n"
            f"💰 Harga saat ini: Rp {result['price']:,.0f}\n"
            f"📈 Perubahan hari ini: {result['change']:+.2f}%\n"
            f"📦 Volume: {result['volume_b']:.1f}B ({result['vol_ratio']:.1f}x normal)\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📉 RSI (14): *{result['rsi']:.1f}* ← Oversold\n"
            f"📊 MACD: {macd_txt}\n"
            f"📉 Drawdown dari High: {result['drawdown']:.1f}%\n"
            f"⭐ Skor sinyal: {result['score']}/10\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Target: Rp {result['target']:,.0f} (+{result['upside']:.1f}%)\n"
            f"🛡 Stop Loss: Rp {result['stop_loss']:,.0f}\n\n"
            f"✅ *Sinyal BUY terdeteksi!*\n"
            f"⚠️ _DYOR sebelum entry._"
        )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"+ Watchlist {ticker}", callback_data=f"wadd_{ticker}"),
            InlineKeyboardButton(f"Set Alert {ticker}", callback_data=f"alstart_{ticker}"),
        ],
        [InlineKeyboardButton("← Menu Utama", callback_data="menu")]
    ])
    await msg.edit_text(text, parse_mode="Markdown", reply_markup=kb)


# ─────────────────────────────────────────────
#  WATCHLIST — Fitur 3
# ─────────────────────────────────────────────

async def show_watchlist(update_or_query, chat_id: int, context=None):
    wl = get_watchlist(chat_id)
    is_query = hasattr(update_or_query, "edit_message_text")

    if not wl:
        text = (
            "📋 *Watchlist kamu kosong*\n\n"
            "Tambah saham dengan perintah:\n"
            "/watchlist tambah BBRI\n\n"
            "Atau saat cek saham, tekan tombol *+ Watchlist*"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("← Menu Utama", callback_data="menu")
        ]])
    else:
        lines = ["📋 *Watchlist Saham Kamu*\n"]
        buttons = []
        for i, item in enumerate(wl, 1):
            added = item["added_at"][:10]
            lines.append(f"{i}. *{item['ticker']}* _(ditambah {added})_")
            buttons.append(InlineKeyboardButton(
                f"❌ {item['ticker']}", callback_data=f"wdel_{item['ticker']}"
            ))

        lines += ["", "_Tekan ❌ untuk hapus dari watchlist_"]
        text = "\n".join(lines)

        # Susun tombol hapus 3 per baris
        btn_rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
        btn_rows.append([
            InlineKeyboardButton("🔍 Scan Watchlist", callback_data="scan_wl"),
            InlineKeyboardButton("← Menu", callback_data="menu"),
        ])
        kb = InlineKeyboardMarkup(btn_rows)

    if is_query:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        await show_watchlist(update, chat_id)
        return

    action = args[0].lower()
    if len(args) < 2:
        await update.message.reply_text(
            "Format: /watchlist tambah BBRI\natau: /watchlist hapus BBRI"
        )
        return

    ticker = args[1].upper().replace(".JK", "")
    if action in ["tambah", "add"]:
        ok = add_watchlist(chat_id, ticker)
        if ok:
            await update.message.reply_text(
                f"✅ *{ticker}* ditambahkan ke watchlist!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"ℹ️ *{ticker}* sudah ada di watchlist kamu.",
                parse_mode="Markdown"
            )
    elif action in ["hapus", "del", "delete", "remove"]:
        ok = remove_watchlist(chat_id, ticker)
        if ok:
            await update.message.reply_text(
                f"🗑 *{ticker}* dihapus dari watchlist.",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ *{ticker}* tidak ada di watchlist kamu.",
                parse_mode="Markdown"
            )


# ─────────────────────────────────────────────
#  HISTORIS SINYAL — Fitur 5
# ─────────────────────────────────────────────

async def cmd_history(update_or_query, chat_id=None, is_query=False):
    signals = get_signals_history(days=30)
    stats = get_signal_stats()

    if not signals:
        text = (
            "📊 *Historis Sinyal (30 Hari)*\n\n"
            "Belum ada sinyal tersimpan.\n"
            "Jalankan /scan dulu untuk mulai merekam sinyal."
        )
    else:
        # Kelompokkan per tanggal
        by_date = {}
        for s in signals:
            d = s["scan_date"]
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(s)

        lines = [
            "📊 *Historis Sinyal — 30 Hari Terakhir*\n",
            f"Total sinyal: *{stats['total']}*",
        ]
        if stats["top_ticker"]:
            lines.append(
                f"Paling sering muncul: *{stats['top_ticker']['ticker']}* "
                f"({stats['top_ticker']['cnt']}x)\n"
            )
        lines.append("")

        for date in sorted(by_date.keys(), reverse=True)[:10]:
            tickers = by_date[date]
            ticker_str = " · ".join([f"*{s['ticker']}*" for s in tickers])
            lines.append(f"📅 {date}: {ticker_str}")

        if len(by_date) > 10:
            lines.append(f"\n_...dan {len(by_date)-10} hari lainnya_")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("← Menu Utama", callback_data="menu")
    ]])

    if is_query:
        await update_or_query.edit_message_text(
            "\n".join(lines) if signals else text,
            parse_mode="Markdown", reply_markup=kb
        )
    else:
        await update_or_query.message.reply_text(
            "\n".join(lines) if signals else text,
            parse_mode="Markdown", reply_markup=kb
        )


# ─────────────────────────────────────────────
#  PRICE ALERT — Fitur 8
# ─────────────────────────────────────────────

async def show_alert_menu(query, chat_id: int):
    alerts = get_alerts(chat_id, only_active=True)
    lines = ["🔔 *Alert Harga Aktif*\n"]

    if not alerts:
        lines.append("Belum ada alert aktif.\n")
    else:
        for a in alerts:
            dir_txt = "naik ke" if a["direction"] == "above" else "turun ke"
            lines.append(
                f"▫️ *{a['ticker']}* {dir_txt} Rp {a['target_price']:,.0f}"
                + (f" — _{a['note']}_" if a["note"] else "")
            )
        lines.append("")

    lines.append("Cara tambah alert:\n/alert BBRI 5000\n/alert TLKM 3200 bawah")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("+ Tambah Alert Baru", callback_data="alert_add")],
        [InlineKeyboardButton("← Menu Utama", callback_data="menu")]
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Format: /alert BBRI 5000
            /alert TLKM 3200 bawah
            /alert list
            /alert hapus 1
    """
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        alerts = get_alerts(chat_id)
        if not alerts:
            await update.message.reply_text(
                "🔔 *Alert Harga*\n\nBelum ada alert.\n\n"
                "Format tambah: /alert BBRI 5000\n"
                "Arah bawah: /alert TLKM 3200 bawah\n"
                "Hapus alert: /alert hapus 1",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        lines = ["🔔 *Alert Aktif Kamu:*\n"]
        for a in alerts:
            dir_txt = "naik ke" if a["direction"] == "above" else "turun ke"
            status = "✅" if a["triggered"] else "🔔"
            lines.append(
                f"{status} ID#{a['id']} *{a['ticker']}* {dir_txt} "
                f"Rp {a['target_price']:,.0f}"
            )
        lines.append("\nHapus: /alert hapus <ID>")
        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard()
        )
        return

    # hapus alert
    if args[0].lower() == "hapus" and len(args) >= 2:
        try:
            alert_id = int(args[1])
            ok = delete_alert(alert_id, chat_id)
            if ok:
                await update.message.reply_text(f"🗑 Alert #{alert_id} dihapus.")
            else:
                await update.message.reply_text(f"❌ Alert #{alert_id} tidak ditemukan.")
        except ValueError:
            await update.message.reply_text("Format: /alert hapus 1")
        return

    # tambah alert
    if len(args) < 2:
        await update.message.reply_text("Format: /alert BBRI 5000")
        return

    ticker = args[0].upper().replace(".JK", "")
    try:
        target = float(args[1].replace(",", ""))
    except ValueError:
        await update.message.reply_text("Harga tidak valid. Contoh: /alert BBRI 5000")
        return

    direction = "below"
    note = None
    if len(args) >= 3:
        if args[2].lower() in ["atas", "above", "naik"]:
            direction = "above"
        elif args[2].lower() in ["bawah", "below", "turun"]:
            direction = "below"
        else:
            note = " ".join(args[2:])

    # Cek harga sekarang untuk otomatis set arah
    curr_price = get_current_price(ticker)
    if curr_price and direction == "below":
        if target > curr_price:
            direction = "above"

    alert_id = add_alert(chat_id, ticker, target, direction, note)
    dir_txt = "naik ke" if direction == "above" else "turun ke"

    await update.message.reply_text(
        f"🔔 *Alert ditambahkan!*\n\n"
        f"Saham: *{ticker}*\n"
        f"Kondisi: harga {dir_txt} Rp {target:,.0f}\n"
        f"ID Alert: #{alert_id}\n\n"
        f"Bot akan notif kamu otomatis saat harga menyentuh target!\n"
        f"_Hapus dengan: /alert hapus {alert_id}_",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )


# ─────────────────────────────────────────────
#  LAPORAN MINGGUAN — Fitur 9
# ─────────────────────────────────────────────

def format_weekly_report(summary: dict) -> str:
    now = datetime.now()
    start = summary["week_start"]
    end = summary["week_end"]

    if summary["total"] == 0:
        return (
            f"📅 *Laporan Minggu Ini*\n"
            f"_{start} — {end}_\n\n"
            "Belum ada sinyal minggu ini.\n"
            "Jalankan /scan setiap hari agar data terekam."
        )

    lines = [
        "📅 *Laporan Sinyal Mingguan*",
        f"_{start} — {end}_\n",
        f"📊 Total sinyal: *{summary['total']}*",
        f"🎯 Rata-rata potensi upside: *+{summary['avg_upside']}%*\n",
    ]

    if summary["top_signals"]:
        lines.append("⭐ *Saham Paling Sering Muncul:*")
        for i, s in enumerate(summary["top_signals"], 1):
            lines.append(
                f"{i}. *{s['ticker']}* — {s['appearances']}x muncul "
                f"(RSI avg: {s['avg_rsi']:.1f})"
            )

    if summary["by_sector"]:
        lines.append("\n🏢 *Sinyal per Sektor:*")
        for sec in summary["by_sector"][:5]:
            lines.append(f"▫️ {sec['sector']}: {sec['cnt']} sinyal")

    lines += [
        "",
        "⚠️ _Data historis. Bukan rekomendasi investasi._"
    ]
    return "\n".join(lines)


async def cmd_weekly(update_or_query, is_query=False):
    now = datetime.now()
    # Minggu ini: Senin sampai hari ini
    days_since_monday = now.weekday()
    week_start = (now - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")
    week_end = now.strftime("%Y-%m-%d")

    summary = get_weekly_summary(week_start, week_end)
    text = format_weekly_report(summary)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("← Menu Utama", callback_data="menu")
    ]])

    if is_query:
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ─────────────────────────────────────────────
#  CALLBACK QUERY
# ─────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "menu":
        await query.edit_message_text(
            "📈 *IDX StockFlow Bot v2*\nPilih menu:",
            parse_mode="Markdown", reply_markup=main_keyboard()
        )

    elif data == "scan":
        await query.edit_message_text("⏳ Scanning saham IDX... mohon tunggu ~30 detik")
        signals, count = scanner.scan_oversold(top_n=5)
        if signals:
            save_signals(signals)
        text = format_signal_message(signals, count)
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=main_keyboard())

    elif data == "top5":
        await query.edit_message_text("⚡ Mencari Top 5 sinyal terkuat...")
        signals, count = scanner.scan_oversold(top_n=5, strict=True)
        if signals:
            save_signals(signals)
        text = format_signal_message(signals, count)
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=main_keyboard())

    elif data == "watchlist":
        await show_watchlist(query, chat_id)

    elif data == "scan_wl":
        wl = get_watchlist(chat_id)
        if not wl:
            await query.edit_message_text("Watchlist kosong.", reply_markup=main_keyboard())
            return
        await query.edit_message_text("⏳ Scanning saham di watchlist kamu...")
        tickers = [w["ticker"] for w in wl]
        signals = []
        for t in tickers:
            result = scanner.analyze(t + ".JK")
            if result:
                signals.append(result)
        count = len(tickers)
        text = format_signal_message(signals, count)
        if signals:
            save_signals(signals)
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=main_keyboard())

    elif data.startswith("wadd_"):
        ticker = data[5:]
        ok = add_watchlist(chat_id, ticker)
        msg = f"✅ *{ticker}* ditambahkan ke watchlist!" if ok else f"ℹ️ *{ticker}* sudah ada di watchlist."
        await query.answer(msg, show_alert=True)

    elif data.startswith("wdel_"):
        ticker = data[5:]
        remove_watchlist(chat_id, ticker)
        await show_watchlist(query, chat_id)

    elif data == "alert_menu":
        await show_alert_menu(query, chat_id)

    elif data == "history":
        await cmd_history(query, chat_id=chat_id, is_query=True)

    elif data == "weekly":
        await cmd_weekly(query, is_query=True)

    elif data == "howto":
        text = (
            "⚙️ *Cara Kerja Bot Oversold IDX*\n\n"
            "Bot scan semua saham IDX dan cari yang memenuhi:\n\n"
            "✅ RSI < 30 — harga oversold\n"
            "✅ MACD bullish crossover\n"
            "✅ Volume spike > 1.5x normal\n"
            "✅ Harga di Bollinger Band bawah\n\n"
            "Sinyal BUY keluar kalau 3-4 kondisi terpenuhi.\n\n"
            "Perintah tersedia:\n"
            "/cek BBRI — analisis satu saham\n"
            "/watchlist — kelola watchlist\n"
            "/alert BBRI 5000 — set price alert\n"
            "/scan — scan semua saham\n"
        )
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=main_keyboard())

    elif data == "status":
        stats = get_signal_stats()
        now_str = datetime.now().strftime("%d %b %Y %H:%M WIB")
        text = (
            f"⚙️ *Status Bot*\n\n"
            f"✅ Bot online\n"
            f"🕐 Waktu server: {now_str}\n"
            f"📅 Scan otomatis: {SCAN_TIME} WIB\n"
            f"📊 Total sinyal tersimpan: {stats['total']}\n"
            f"📈 Sinyal hari ini: {stats['today']}\n"
            f"🔗 Sumber data: Yahoo Finance (delay 15 menit)"
        )
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=main_keyboard())

    elif data.startswith("alstart_"):
        ticker = data[8:]
        await query.edit_message_text(
            f"🔔 Set alert untuk *{ticker}*\n\n"
            f"Kirim perintah:\n"
            f"`/alert {ticker} <harga_target>`\n\n"
            f"Contoh:\n"
            f"`/alert {ticker} 5000` — alert saat naik ke 5000\n"
            f"`/alert {ticker} 4000 bawah` — alert saat turun ke 4000",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Kembali", callback_data="menu")
            ]])
        )


# ─────────────────────────────────────────────
#  JOBS TERJADWAL
# ─────────────────────────────────────────────

async def auto_scan_job(context: ContextTypes.DEFAULT_TYPE):
    """Scan otomatis harian."""
    logger.info("Menjalankan auto scan terjadwal...")
    signals, count = scanner.scan_oversold(top_n=5)
    if signals:
        save_signals(signals)
    text = format_signal_message(signals, count)
    for chat_id in CHAT_ID_LIST:
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        except Exception as e:
            logger.error(f"Gagal kirim ke {chat_id}: {e}")


async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Cek price alert setiap 15 menit."""
    alerts = get_all_active_alerts()
    if not alerts:
        return

    # Kumpulkan ticker unik
    tickers = list(set(a["ticker"] for a in alerts))
    prices = {}
    for t in tickers:
        price = get_current_price(t)
        if price:
            prices[t] = price

    for alert in alerts:
        ticker = alert["ticker"]
        if ticker not in prices:
            continue
        curr = prices[ticker]
        target = alert["target_price"]
        triggered = False

        if alert["direction"] == "above" and curr >= target:
            triggered = True
        elif alert["direction"] == "below" and curr <= target:
            triggered = True

        if triggered:
            trigger_alert(alert["id"])
            dir_txt = "naik ke" if alert["direction"] == "above" else "turun ke"
            msg = (
                f"🔔 *ALERT TERPICU!*\n\n"
                f"Saham *{ticker}* sudah {dir_txt} target!\n\n"
                f"💰 Harga saat ini: Rp {curr:,.0f}\n"
                f"🎯 Target kamu: Rp {target:,.0f}\n"
                + (f"📝 Catatan: {alert['note']}\n" if alert["note"] else "") +
                f"\n_Cek kondisi teknikal sebelum action: /cek {ticker}_"
            )
            try:
                await context.bot.send_message(
                    chat_id=alert["chat_id"], text=msg,
                    parse_mode="Markdown", reply_markup=main_keyboard()
                )
                logger.info(f"Alert #{alert['id']} terpicu: {ticker} @ {curr}")
            except Exception as e:
                logger.error(f"Gagal kirim alert: {e}")


async def weekly_report_job(context: ContextTypes.DEFAULT_TYPE):
    """Kirim laporan mingguan setiap Jumat jam 16:00 WIB."""
    now = datetime.now()
    days_since_monday = now.weekday()
    week_start = (now - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")
    week_end = now.strftime("%Y-%m-%d")
    summary = get_weekly_summary(week_start, week_end)
    text = format_weekly_report(summary)

    for chat_id in CHAT_ID_LIST:
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        except Exception as e:
            logger.error(f"Gagal kirim weekly report ke {chat_id}: {e}")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cek", cmd_cek))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("scan", lambda u, c: u.message.reply_text(
        "Gunakan tombol Scan IDX", reply_markup=main_keyboard())))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Jadwal harian scan — jam 09:15 WIB (02:15 UTC)
    scan_h, scan_m = map(int, SCAN_TIME.split(":"))
    utc_h = (scan_h - 7) % 24
    app.job_queue.run_daily(auto_scan_job, time=time(hour=utc_h, minute=scan_m))

    # Cek price alert setiap 15 menit
    app.job_queue.run_repeating(check_alerts_job, interval=900, first=60)

    # Laporan mingguan tiap Jumat 16:00 WIB (09:00 UTC)
    app.job_queue.run_daily(
        weekly_report_job,
        time=time(hour=9, minute=0),
        days=(4,)  # 4 = Jumat
    )

    logger.info("IDX StockFlow Bot v2 aktif dan berjalan...")
    logger.info(f"Auto scan dijadwalkan: {SCAN_TIME} WIB")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()