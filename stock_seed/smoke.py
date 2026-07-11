"""Data-path smoke test (no MiroFish needed): build + print the seed materials.

    DATABASE_URL=... python -m stock_seed.smoke RELIANCE
    (or rely on the local .env)
"""
from __future__ import annotations

import sys

from .db import StockDataReader
from .seed_builder import build_market_report, build_news_digest, simulation_requirement


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "RELIANCE").upper()
    horizon = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    r = StockDataReader()
    meta = r.meta(symbol)
    prices = r.price_history(symbol)
    news = r.related_news(symbol)

    print(f"META: {meta.symbol} / {meta.name} / {meta.sector} / {meta.exchange}")
    print(f"PRICES: {len(prices)} sessions   NEWS: {len(news)} items\n")
    print("========== MARKET REPORT SEED ==========")
    print(build_market_report(meta, prices).content)
    print("\n========== NEWS DIGEST SEED ==========")
    print(build_news_digest(meta, news).content)
    print("\n========== SIMULATION REQUIREMENT ==========")
    print(simulation_requirement(symbol, horizon))


if __name__ == "__main__":
    main()
