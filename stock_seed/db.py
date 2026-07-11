"""Read stock price history + related news from the shared Postgres DB.

The exact tables/columns are TBD (see README prereq #3) — the queries below are
placeholders keyed on what we already know (`akshay.stock_master` for the master;
the news table the frontend `/api/news` reads). Fill the SQL once confirmed.
"""
from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from .config import settings


@dataclass
class PricePoint:
    date: str
    close: float
    volume: float | None = None


@dataclass
class NewsItem:
    published_at: str
    headline: str
    summary: str
    source: str | None = None


class StockDataReader:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or settings.database_url

    def _conn(self) -> psycopg.Connection:
        if not self.dsn:
            raise RuntimeError("database_url is not configured")
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def price_history(self, symbol: str, window_days: int | None = None) -> list[PricePoint]:
        window = window_days or settings.price_window_days
        # TODO: point at the real OHLCV table + column names.
        sql = """
            SELECT date, close, volume
            FROM   <price_table>
            WHERE  symbol = %(symbol)s
            ORDER  BY date DESC
            LIMIT  %(window)s
        """
        raise NotImplementedError("wire up the price-history query (README prereq #3)")

    def related_news(self, symbol: str, limit: int | None = None) -> list[NewsItem]:
        lim = limit or settings.news_limit
        # TODO: mirror the frontend /api/news stock filter (SYM = ANY(stocks_affected)
        # OR brand ILIKE headline/description).
        sql = """
            SELECT published_at, headline, summary, source
            FROM   <news_table>
            WHERE  %(symbol)s = ANY(stocks_affected)
            ORDER  BY published_at DESC
            LIMIT  %(limit)s
        """
        raise NotImplementedError("wire up the related-news query (README prereq #3)")
