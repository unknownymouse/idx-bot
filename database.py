"""
Database module — SQLite untuk historis sinyal, watchlist, dan price alerts
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = "idx_bot.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """Buat semua tabel kalau belum ada."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            name        TEXT,
            sector      TEXT,
            price       REAL,
            change_pct  REAL,
            rsi         REAL,
            volume_b    REAL,
            vol_ratio   REAL,
            target      REAL,
            stop_loss   REAL,
            upside      REAL,
            score       INTEGER,
            scan_date   TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS signal_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id   INTEGER REFERENCES signals(id),
            ticker      TEXT NOT NULL,
            entry_price REAL,
            exit_price  REAL,
            exit_date   TEXT,
            profit_pct  REAL,
            status      TEXT DEFAULT 'open',
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            ticker      TEXT NOT NULL,
            added_at    TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(chat_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS price_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            ticker      TEXT NOT NULL,
            target_price REAL NOT NULL,
            direction   TEXT NOT NULL,
            note        TEXT,
            triggered   INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            triggered_at TEXT
        );

        CREATE TABLE IF NOT EXISTS weekly_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start  TEXT NOT NULL,
            week_end    TEXT NOT NULL,
            total_signals INTEGER DEFAULT 0,
            profitable  INTEGER DEFAULT 0,
            avg_profit  REAL DEFAULT 0,
            best_ticker TEXT,
            best_profit REAL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
        """)
    logger.info("Database diinisialisasi.")


# ─────────────────────────────────────────────
#  SIGNALS
# ─────────────────────────────────────────────

def save_signals(signals: list, scan_date: str = None) -> list:
    """Simpan sinyal hasil scan. Return list ID yang disimpan."""
    if scan_date is None:
        scan_date = datetime.now().strftime("%Y-%m-%d")
    ids = []
    with get_conn() as conn:
        for s in signals:
            cur = conn.execute(
                """INSERT INTO signals
                   (ticker,name,sector,price,change_pct,rsi,volume_b,vol_ratio,
                    target,stop_loss,upside,score,scan_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (s["ticker"], s["name"], s["sector"], s["price"], s["change"],
                 s["rsi"], s["volume_b"], s["vol_ratio"], s["target"],
                 s["stop_loss"], s["upside"], s["score"], scan_date)
            )
            ids.append(cur.lastrowid)
    return ids


def get_signals_history(days: int = 30, ticker: str = None) -> list:
    """Ambil historis sinyal N hari terakhir."""
    with get_conn() as conn:
        if ticker:
            rows = conn.execute(
                """SELECT * FROM signals WHERE ticker=?
                   ORDER BY scan_date DESC LIMIT 50""",
                (ticker.upper(),)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM signals
                   WHERE scan_date >= date('now',?)
                   ORDER BY scan_date DESC, score DESC""",
                (f"-{days} days",)
            ).fetchall()
        return [dict(r) for r in rows]


def get_signal_stats() -> dict:
    """Statistik sinyal secara keseluruhan."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE scan_date=date('now','localtime')"
        ).fetchone()[0]
        top_ticker = conn.execute(
            """SELECT ticker, COUNT(*) as cnt FROM signals
               GROUP BY ticker ORDER BY cnt DESC LIMIT 1"""
        ).fetchone()
        return {
            "total": total,
            "today": today,
            "top_ticker": dict(top_ticker) if top_ticker else None
        }


# ─────────────────────────────────────────────
#  WATCHLIST
# ─────────────────────────────────────────────

def add_watchlist(chat_id: int, ticker: str) -> bool:
    """Tambah saham ke watchlist. Return True kalau berhasil."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist (chat_id, ticker) VALUES (?,?)",
                (chat_id, ticker.upper())
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_watchlist(chat_id: int, ticker: str) -> bool:
    """Hapus saham dari watchlist. Return True kalau ada yang dihapus."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE chat_id=? AND ticker=?",
            (chat_id, ticker.upper())
        )
        return cur.rowcount > 0


def get_watchlist(chat_id: int) -> list:
    """Ambil daftar watchlist user."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticker, added_at FROM watchlist WHERE chat_id=? ORDER BY added_at DESC",
            (chat_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_watchlist_tickers() -> list:
    """Ambil semua ticker unik dari semua watchlist (untuk cek alert)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM watchlist"
        ).fetchall()
        return [r["ticker"] for r in rows]


# ─────────────────────────────────────────────
#  PRICE ALERTS
# ─────────────────────────────────────────────

def add_alert(chat_id: int, ticker: str, target_price: float,
              direction: str, note: str = None) -> int:
    """Tambah price alert. Return ID alert."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO price_alerts (chat_id, ticker, target_price, direction, note)
               VALUES (?,?,?,?,?)""",
            (chat_id, ticker.upper(), target_price, direction, note)
        )
        return cur.lastrowid


def get_alerts(chat_id: int, only_active: bool = True) -> list:
    """Ambil semua alert milik user."""
    with get_conn() as conn:
        q = "SELECT * FROM price_alerts WHERE chat_id=?"
        if only_active:
            q += " AND triggered=0"
        q += " ORDER BY created_at DESC"
        rows = conn.execute(q, (chat_id,)).fetchall()
        return [dict(r) for r in rows]


def get_all_active_alerts() -> list:
    """Ambil semua alert aktif dari semua user (untuk job checker)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_alerts WHERE triggered=0"
        ).fetchall()
        return [dict(r) for r in rows]


def trigger_alert(alert_id: int):
    """Tandai alert sebagai sudah triggered."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE price_alerts SET triggered=1,
               triggered_at=datetime('now','localtime')
               WHERE id=?""",
            (alert_id,)
        )


def delete_alert(alert_id: int, chat_id: int) -> bool:
    """Hapus alert milik user tertentu."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM price_alerts WHERE id=? AND chat_id=?",
            (alert_id, chat_id)
        )
        return cur.rowcount > 0


# ─────────────────────────────────────────────
#  WEEKLY REPORT
# ─────────────────────────────────────────────

def get_weekly_signals(week_start: str, week_end: str) -> list:
    """Ambil sinyal dalam rentang satu minggu."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE scan_date BETWEEN ? AND ?
               ORDER BY score DESC""",
            (week_start, week_end)
        ).fetchall()
        return [dict(r) for r in rows]


def get_weekly_summary(week_start: str, week_end: str) -> dict:
    """Ringkasan statistik sinyal minggu ini."""
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE scan_date BETWEEN ? AND ?",
            (week_start, week_end)
        ).fetchone()[0]

        by_sector = conn.execute(
            """SELECT sector, COUNT(*) as cnt FROM signals
               WHERE scan_date BETWEEN ? AND ?
               GROUP BY sector ORDER BY cnt DESC""",
            (week_start, week_end)
        ).fetchall()

        top_signals = conn.execute(
            """SELECT ticker, name, MAX(score) as score, AVG(rsi) as avg_rsi,
               COUNT(*) as appearances
               FROM signals WHERE scan_date BETWEEN ? AND ?
               GROUP BY ticker ORDER BY appearances DESC, score DESC LIMIT 5""",
            (week_start, week_end)
        ).fetchall()

        avg_upside = conn.execute(
            "SELECT AVG(upside) FROM signals WHERE scan_date BETWEEN ? AND ?",
            (week_start, week_end)
        ).fetchone()[0]

        return {
            "total": total,
            "by_sector": [dict(r) for r in by_sector],
            "top_signals": [dict(r) for r in top_signals],
            "avg_upside": round(avg_upside or 0, 1),
            "week_start": week_start,
            "week_end": week_end,
        }
