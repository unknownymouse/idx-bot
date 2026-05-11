"""
Konfigurasi IDX StockFlow Bot
Edit file ini sesuai kebutuhan kamu
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── WAJIB DIISI ───────────────────────────────────────────────────────────────

# Token dari @BotFather di Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "MASUKKAN_TOKEN_BOT_KAMU_DI_SINI")

# Chat ID yang akan menerima sinyal otomatis
# Cara cari Chat ID: kirim pesan ke bot, lalu buka:
# https://api.telegram.org/bot<TOKEN>/getUpdates
# Bisa berupa list: [123456789, -100987654321]
CHAT_ID_LIST = [
    int(x) for x in os.getenv("CHAT_ID_LIST", "0").split(",") if x.strip() != "0"
]

# ─── OPSIONAL ──────────────────────────────────────────────────────────────────

# Jam scan otomatis (format: "HH:MM" WIB)
SCAN_TIME = os.getenv("SCAN_TIME", "09:15")

# Jumlah sinyal maksimum yang ditampilkan
MAX_SIGNALS = int(os.getenv("MAX_SIGNALS", "5"))
