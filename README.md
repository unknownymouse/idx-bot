# 📈 IDX StockFlow Bot

Bot Telegram untuk sinyal saham oversold IDX secara otomatis.
Menggunakan yfinance (gratis, tanpa API key berbayar).

---

## 🚀 Cara Instalasi

### 1. Persiapan
Pastikan sudah install **Python 3.10+**

### 2. Clone / Download Project
```bash
# Download semua file ke satu folder, lalu masuk ke folder:
cd idx_bot
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Buat File .env
```bash
# Salin template
cp .env.example .env

# Edit file .env dengan text editor
# Isi BOT_TOKEN dari @BotFather
# Isi CHAT_ID_LIST dengan chat ID kamu
```

### 5. Cara Dapat Telegram Bot Token
1. Buka Telegram → cari **@BotFather**
2. Ketik `/newbot`
3. Ikuti instruksi, beri nama & username bot
4. Salin token yang diberikan ke `.env`

### 6. Cara Dapat Chat ID
Setelah bot dibuat:
1. Kirim pesan apapun ke bot kamu
2. Buka browser, akses URL:
   `https://api.telegram.org/bot<TOKEN_KAMU>/getUpdates`
3. Cari nilai `"id"` di dalam `"chat"` → itu Chat ID kamu
4. Masukkan ke `.env` di `CHAT_ID_LIST`

### 7. Jalankan Bot
```bash
python bot.py
```

---

## 📋 Perintah Bot

| Perintah | Fungsi |
|----------|--------|
| `/start` | Tampilkan menu utama |
| `/scan`  | Scan saham oversold sekarang |
| `/top5`  | Tampilkan 5 sinyal terkuat |
| `/cara`  | Penjelasan cara kerja |

---

## ⏰ Auto Scan

Bot akan otomatis scan dan kirim sinyal setiap hari pukul **09:15 WIB**
(15 menit setelah market IDX buka).

Ubah jam di `.env`:
```
SCAN_TIME=09:15
```

---

## 📊 Indikator yang Digunakan

| Indikator | Kondisi Sinyal |
|-----------|---------------|
| RSI 14    | < 30 (oversold) |
| MACD      | Bullish crossover |
| Bollinger Band | Harga di bawah band bawah |
| Volume    | > 1.5x rata-rata 20 hari |
| Stochastic RSI | < 25 dan mulai naik |

---

## 🖥️ Deploy ke Server (24 jam)

### Opsi A: Railway.app (Gratis)
1. Push code ke GitHub
2. Login ke [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Tambah environment variables dari `.env`
5. Deploy → bot berjalan 24 jam

### Opsi B: VPS (DigitalOcean/Linode ~$4/bulan)
```bash
# Install screen untuk background process
sudo apt install screen

# Jalankan bot di background
screen -S idxbot
python bot.py
# Tekan Ctrl+A lalu D untuk detach
```

---

## ⚠️ Disclaimer

Bot ini adalah tools analisis teknikal otomatis, bukan rekomendasi
investasi resmi. Investasi selalu mengandung risiko. DYOR.
