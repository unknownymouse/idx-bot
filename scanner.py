"""
IDX Scanner — Scan saham oversold dengan indikator teknikal
Menggunakan yfinance (gratis, tidak perlu API key)
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Daftar saham IDX (LQ45 + saham aktif)
#  Tambah/kurangi sesuai kebutuhan
# ─────────────────────────────────────────────

IDX_WATCHLIST = [
    # Perbankan
    "BBRI.JK", "BBCA.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK",
    # Energi & Tambang
    "ADRO.JK", "PTBA.JK", "INCO.JK", "ANTM.JK", "MDKA.JK",
    "BYAN.JK", "HRUM.JK", "ITMG.JK",
    # Konsumer
    "UNVR.JK", "ICBP.JK", "INDF.JK", "SIDO.JK", "MYOR.JK",
    "CPIN.JK", "JPFA.JK",
    # Teknologi & Telkom
    "TLKM.JK", "EXCL.JK", "ISAT.JK", "GOTO.JK", "BUKA.JK",
    # Properti
    "BSDE.JK", "SMRA.JK", "CTRA.JK", "PWON.JK",
    # Infrastruktur
    "JSMR.JK", "WIKA.JK", "PTPP.JK", "WSKT.JK",
    # Kesehatan
    "KLBF.JK", "KAEF.JK", "MIKA.JK",
    # Semen & Material
    "SMGR.JK", "INTP.JK", "TPIA.JK",
    # Otomotif
    "ASII.JK", "SMSM.JK",
    # Lain-lain
    "GGRM.JK", "HMSP.JK", "AMRT.JK", "ACES.JK", "MAPI.JK",
    "ERAA.JK", "WIFI.JK", "CYBR.JK", "ASPR.JK",
]

SECTOR_MAP = {
    "BBRI.JK": "Perbankan", "BBCA.JK": "Perbankan", "BMRI.JK": "Perbankan",
    "BBNI.JK": "Perbankan", "BRIS.JK": "Perbankan",
    "ADRO.JK": "Batubara", "PTBA.JK": "Batubara", "BYAN.JK": "Batubara",
    "HRUM.JK": "Batubara", "ITMG.JK": "Batubara",
    "INCO.JK": "Pertambangan", "ANTM.JK": "Pertambangan", "MDKA.JK": "Pertambangan",
    "TLKM.JK": "Telekomunikasi", "EXCL.JK": "Telekomunikasi", "ISAT.JK": "Telekomunikasi",
    "GOTO.JK": "Teknologi", "BUKA.JK": "Teknologi", "CYBR.JK": "Teknologi",
    "UNVR.JK": "Konsumer", "ICBP.JK": "Konsumer", "INDF.JK": "Konsumer",
    "SIDO.JK": "Konsumer", "MYOR.JK": "Konsumer",
    "CPIN.JK": "Peternakan", "JPFA.JK": "Peternakan",
    "BSDE.JK": "Properti", "SMRA.JK": "Properti", "CTRA.JK": "Properti",
    "PWON.JK": "Properti",
    "JSMR.JK": "Infrastruktur", "WIKA.JK": "Konstruksi", "PTPP.JK": "Konstruksi",
    "WSKT.JK": "Konstruksi",
    "KLBF.JK": "Kesehatan", "KAEF.JK": "Farmasi", "MIKA.JK": "Kesehatan",
    "SMGR.JK": "Semen", "INTP.JK": "Semen", "TPIA.JK": "Petrokimia",
    "ASII.JK": "Otomotif", "SMSM.JK": "Otomotif",
    "GGRM.JK": "Rokok", "HMSP.JK": "Rokok",
    "AMRT.JK": "Ritel", "ACES.JK": "Ritel", "MAPI.JK": "Ritel",
    "ERAA.JK": "Elektronik", "WIFI.JK": "Teknologi",
    "ASPR.JK": "Asuransi",
}


# ─────────────────────────────────────────────
#  Indikator Teknikal
# ─────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def calc_bollinger(series: pd.Series, period=20, std=2):
    sma = series.rolling(period).mean()
    std_dev = series.rolling(period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return upper, sma, lower


def calc_stoch_rsi(series: pd.Series, rsi_period=14, stoch_period=14) -> pd.Series:
    rsi = calc_rsi(series, rsi_period)
    stoch = (rsi - rsi.rolling(stoch_period).min()) / \
            (rsi.rolling(stoch_period).max() - rsi.rolling(stoch_period).min() + 1e-10)
    return stoch * 100


# ─────────────────────────────────────────────
#  Main Scanner Class
# ─────────────────────────────────────────────

class IDXScanner:
    def __init__(self):
        self.watchlist = IDX_WATCHLIST

    def fetch_data(self, ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
        try:
            df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
            if df is None or len(df) < 30:
                return None
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df
        except Exception as e:
            logger.debug(f"Gagal fetch {ticker}: {e}")
            return None

    def analyze(self, ticker: str, strict: bool = False) -> Optional[dict]:
        df = self.fetch_data(ticker)
        if df is None or len(df) < 26:
            return None

        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        high = df["High"].squeeze()
        low = df["Low"].squeeze()

        # Hitung indikator
        rsi = calc_rsi(close, 14)
        macd_line, signal_line = calc_macd(close)
        bb_upper, bb_mid, bb_lower = calc_bollinger(close, 20)
        stoch = calc_stoch_rsi(close)

        # Nilai terbaru
        curr_rsi = rsi.iloc[-1]
        curr_price = close.iloc[-1]
        curr_vol = volume.iloc[-1]
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1

        macd_curr = macd_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        sig_curr = signal_line.iloc[-1]
        sig_prev = signal_line.iloc[-2]

        macd_cross = (macd_prev < sig_prev) and (macd_curr >= sig_curr)

        bb_low_val = bb_lower.iloc[-1]
        at_bb_lower = curr_price <= bb_low_val * 1.02  # dalam 2% dari BB bawah

        high_20 = high.rolling(20).max().iloc[-1]
        drawdown = (curr_price - high_20) / high_20 * 100

        curr_stoch = stoch.iloc[-1]
        stoch_prev = stoch.iloc[-2]
        stoch_rising = stoch_prev < curr_stoch

        # Skor sinyal (1 poin per kondisi)
        score = 0
        if curr_rsi < 35:
            score += 2
        if curr_rsi < 30:
            score += 1  # bonus
        if macd_cross:
            score += 2
        if at_bb_lower:
            score += 1
        if vol_ratio > 1.5:
            score += 2
        if curr_stoch < 25 and stoch_rising:
            score += 1
        if drawdown < -10:
            score += 1

        threshold = 5 if strict else 3
        if score < threshold:
            return None

        # Kalkulasi target & stop loss
        resistance = high.rolling(20).max().iloc[-1]
        target = min(resistance, curr_price * 1.15)
        stop_loss = curr_price * 0.95
        upside = (target - curr_price) / curr_price * 100

        # Info perusahaan
        ticker_clean = ticker.replace(".JK", "")
        try:
            info = yf.Ticker(ticker).info
            name = info.get("longName") or info.get("shortName") or ticker_clean
            name = name.replace(" Tbk", "").replace(", PT", "").strip()
        except Exception:
            name = ticker_clean

        return {
            "ticker": ticker_clean,
            "name": name[:25],
            "sector": SECTOR_MAP.get(ticker, "Lain-lain"),
            "price": round(curr_price),
            "change": round(float(close.pct_change().iloc[-1] * 100), 2),
            "volume_b": round(curr_vol / 1e9, 2),
            "vol_ratio": round(vol_ratio, 1),
            "rsi": round(curr_rsi, 1),
            "rsi_period": 14,
            "macd_signal": macd_cross,
            "target": round(target),
            "stop_loss": round(stop_loss),
            "upside": round(upside, 1),
            "score": score,
            "drawdown": round(drawdown, 1),
        }

    def scan_oversold(self, top_n: int = 5, strict: bool = False) -> tuple[list, int]:
        results = []
        total_scanned = 0

        logger.info(f"Mulai scan {len(self.watchlist)} saham IDX...")

        for ticker in self.watchlist:
            total_scanned += 1
            try:
                signal = self.analyze(ticker, strict=strict)
                if signal:
                    results.append(signal)
                    logger.info(f"✅ Sinyal ditemukan: {ticker} (score={signal['score']})")
            except Exception as e:
                logger.debug(f"Error pada {ticker}: {e}")

        # Sort by score tertinggi
        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:top_n]

        logger.info(f"Scan selesai: {total_scanned} saham, {len(results)} sinyal, top {len(top)} ditampilkan")
        return top, total_scanned
