"""Read stock price history + related news from the shared Postgres DB.

Live queries against:
  • akshay.stock_prices_daily  (daily OHLCV)
  • news.market_news           (headline/description + stocks_affected[] + sentiment/impact)
  • akshay.stock_master        (name/sector for context)

The DB host is internal infra — this module runs server-side only; never surface
the DSN/host anywhere client-facing.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from .config import settings


@dataclass
class PricePoint:
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None = None


@dataclass
class NewsItem:
    published_at: str
    headline: str
    summary: str
    source: str | None = None
    sentiment: str | None = None
    impact: int | None = None


@dataclass
class StockMeta:
    symbol: str
    name: str | None = None
    sector: str | None = None
    exchange: str | None = None


class StockDataReader:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or settings.database_url

    def _conn(self) -> psycopg.Connection:
        if not self.dsn:
            raise RuntimeError("database_url is not configured")
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def meta(self, symbol: str) -> StockMeta:
        sql = """
            SELECT symbol, name, sector, exchange
            FROM   akshay.stock_master
            WHERE  symbol = %(symbol)s
            LIMIT  1
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, {"symbol": symbol})
            row = cur.fetchone()
        if not row:
            return StockMeta(symbol=symbol)
        return StockMeta(
            symbol=row["symbol"], name=row["name"],
            sector=row["sector"], exchange=row["exchange"],
        )

    def price_history(self, symbol: str, window_days: int | None = None) -> list[PricePoint]:
        window = window_days or settings.price_window_days
        # A symbol can be dual-listed (NSE + BSE) → one row per exchange per
        # date. Keep the higher-volume (primary/liquid) listing per date.
        sql = """
            SELECT DISTINCT ON (date) date, open, high, low, close, volume
            FROM   akshay.stock_prices_daily
            WHERE  symbol = %(symbol)s
            ORDER  BY date DESC, volume DESC NULLS LAST
            LIMIT  %(window)s
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, {"symbol": symbol, "window": window})
            rows = cur.fetchall()
        # Return oldest → newest for readable seeds.
        return [
            PricePoint(
                date=str(r["date"]),
                open=_f(r["open"]), high=_f(r["high"]), low=_f(r["low"]),
                close=_f(r["close"]) or 0.0, volume=r["volume"],
            )
            for r in reversed(rows)
        ]

    def related_news(self, symbol: str, limit: int | None = None) -> list[NewsItem]:
        lim = limit or settings.news_limit
        sql = """
            SELECT published_at, headline, description, source_name, sentiment, impact
            FROM   news.market_news
            WHERE  %(symbol)s = ANY(stocks_affected)
            ORDER  BY published_at DESC NULLS LAST
            LIMIT  %(limit)s
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, {"symbol": symbol, "limit": lim})
            rows = cur.fetchall()
        return [
            NewsItem(
                published_at=str(r["published_at"]),
                headline=r["headline"] or "",
                summary=r["description"] or "",
                source=r["source_name"],
                sentiment=r["sentiment"],
                impact=r["impact"],
            )
            for r in rows
        ]


def _f(v) -> float | None:
    return float(v) if v is not None else None
