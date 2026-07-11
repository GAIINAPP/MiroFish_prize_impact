"""Turn stock data + news into MiroFish seed files and the prediction ask."""
from __future__ import annotations

from .db import NewsItem, PricePoint
from .mirofish_client import SeedFile


def build_market_report(symbol: str, prices: list[PricePoint]) -> SeedFile:
    """A compact market-report seed: recent price action + simple derived stats
    (trend, range, latest close, volume). Kept as markdown MiroFish can ingest."""
    asc = list(reversed(prices))  # oldest → newest for readability
    latest = asc[-1] if asc else None
    lines = [f"# {symbol} — Market report", ""]
    if latest:
        first = asc[0].close
        change = ((latest.close - first) / first * 100) if first else 0.0
        lines += [
            f"- Latest close: {latest.close}",
            f"- Window: {asc[0].date} → {latest.date} ({len(asc)} sessions)",
            f"- Window change: {change:+.2f}%",
            "",
            "## Recent closes (oldest → newest)",
            "",
            *[f"- {p.date}: {p.close}" + (f"  (vol {p.volume})" if p.volume else "") for p in asc],
        ]
    # TODO: enrich with indicators the analyzer already computes (RSI, trend
    # label, support/resistance) so the agents reason on richer signals.
    return SeedFile(filename=f"{symbol}_market_report.md", content="\n".join(lines))


def build_news_digest(symbol: str, news: list[NewsItem]) -> SeedFile:
    """A news-digest seed: related headlines + summaries, newest first."""
    lines = [f"# {symbol} — Related news digest", ""]
    for n in news:
        lines += [
            f"## {n.headline}",
            f"_{n.published_at}" + (f" · {n.source}" if n.source else "") + "_",
            "",
            n.summary or "",
            "",
        ]
    return SeedFile(filename=f"{symbol}_news_digest.md", content="\n".join(lines))


def simulation_requirement(symbol: str, horizon_days: int) -> str:
    return (
        f"Predict the likely price impact and direction of {symbol} over the next "
        f"{horizon_days} trading days, given its recent price action and the "
        f"related news in the seed materials. Deduce: overall direction "
        f"(up / down / flat), a rough magnitude band, the key drivers behind the "
        f"move, and a confidence level. Reason as a population of market "
        f"participants reacting to the news and price context."
    )
