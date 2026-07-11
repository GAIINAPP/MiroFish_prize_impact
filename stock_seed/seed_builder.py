"""Turn stock data + news into MiroFish seed files and the prediction ask."""
from __future__ import annotations

from .db import NewsItem, PricePoint, StockMeta
from .mirofish_client import SeedFile


def build_market_report(meta: StockMeta, prices: list[PricePoint]) -> SeedFile:
    """A compact market-report seed: recent price action + simple derived stats
    (window change, range, latest close, average volume). Markdown MiroFish can
    ingest and the agents can reason over."""
    sym = meta.symbol
    title = f"{sym}" + (f" — {meta.name}" if meta.name else "")
    lines = [f"# {title} — Market report", ""]
    if meta.sector:
        lines.append(f"- Sector: {meta.sector}")
    if prices:
        first, last = prices[0], prices[-1]
        change = ((last.close - first.close) / first.close * 100) if first.close else 0.0
        highs = [p.high for p in prices if p.high is not None]
        lows = [p.low for p in prices if p.low is not None]
        vols = [p.volume for p in prices if p.volume is not None]
        lines += [
            f"- Latest close: {last.close} ({last.date})",
            f"- Window: {first.date} → {last.date} ({len(prices)} sessions)",
            f"- Window change: {change:+.2f}%",
            f"- Period high / low: {max(highs) if highs else '—'} / {min(lows) if lows else '—'}",
            f"- Avg daily volume: {int(sum(vols) / len(vols)) if vols else '—'}",
            "",
            "## Daily OHLC (oldest → newest)",
            "",
            "| Date | Open | High | Low | Close | Volume |",
            "| --- | --- | --- | --- | --- | --- |",
            *[
                f"| {p.date} | {p.open} | {p.high} | {p.low} | {p.close} | {p.volume or ''} |"
                for p in prices
            ],
        ]
    else:
        lines.append("- No price history available.")
    return SeedFile(filename=f"{sym}_market_report.md", content="\n".join(lines))


def build_news_digest(meta: StockMeta, news: list[NewsItem]) -> SeedFile:
    """A news-digest seed: related headlines + summaries (newest first), with the
    pre-computed sentiment/impact so agents weigh each item."""
    lines = [f"# {meta.symbol} — Related news digest", ""]
    if not news:
        lines.append("- No related news found.")
    for n in news:
        tags = []
        if n.sentiment:
            tags.append(f"sentiment: {n.sentiment}")
        if n.impact is not None:
            tags.append(f"impact: {n.impact}")
        meta_line = f"_{n.published_at}"
        if n.source:
            meta_line += f" · {n.source}"
        if tags:
            meta_line += f" · {' · '.join(tags)}"
        meta_line += "_"
        lines += [f"## {n.headline}", meta_line, "", n.summary or "", ""]
    return SeedFile(filename=f"{meta.symbol}_news_digest.md", content="\n".join(lines))


def simulation_requirement(symbol: str, horizon_days: int) -> str:
    return (
        f"Predict the likely price impact and direction of {symbol} over the next "
        f"{horizon_days} trading days, given its recent price action and the "
        f"related news in the seed materials. Deduce: overall direction "
        f"(up / down / flat), a rough magnitude band, the key drivers behind the "
        f"move, and a confidence level. Reason as a population of market "
        f"participants (retail traders, institutions, analysts, news readers) "
        f"reacting to the news and the price context."
    )
