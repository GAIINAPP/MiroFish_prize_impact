"""End-to-end: symbol → seeds → MiroFish pipeline → prediction report."""
from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .db import StockDataReader
from .mirofish_client import MiroFishClient
from .seed_builder import build_market_report, build_news_digest, simulation_requirement


@dataclass
class PricePrediction:
    symbol: str
    horizon_days: int
    project_id: str
    simulation_id: str
    report: dict  # MiroFish report payload (direction / drivers / confidence / …)


def predict_price_impact(symbol: str, horizon_days: int | None = None) -> PricePrediction:
    symbol = symbol.strip().upper()
    horizon = horizon_days or settings.default_horizon_days

    reader = StockDataReader()
    meta = reader.meta(symbol)
    prices = reader.price_history(symbol)
    news = reader.related_news(symbol)

    seeds = [build_market_report(meta, prices), build_news_digest(meta, news)]
    requirement = simulation_requirement(symbol, horizon)

    mf = MiroFishClient()
    project = mf.generate_ontology(
        seeds=seeds,
        simulation_requirement=requirement,
        project_name=f"{symbol} price-impact {horizon}d",
    )
    project_id = project["project_id"]

    graph = mf.build_graph(project_id)
    simulation_id = mf.run_simulation(
        project_id=project_id, graph_id=graph.get("graph_id")
    )
    report = mf.generate_report(simulation_id)

    return PricePrediction(
        symbol=symbol,
        horizon_days=horizon,
        project_id=project_id,
        simulation_id=simulation_id,
        report=report,
    )


@dataclass
class StockProject:
    symbol: str
    name: str | None
    horizon_days: int
    project_id: str
    ontology: dict
    price_points: int
    news_count: int


def create_stock_project(symbol: str, horizon_days: int | None = None) -> StockProject:
    """Fast path for the UI: build the stock's seed materials and create a
    MiroFish project (ontology step only). The user then watches the graph /
    simulation / report in the embedded MiroFish frontend, which owns the rich
    visualisation. Cheaper than a full synchronous prediction."""
    symbol = symbol.strip().upper()
    horizon = horizon_days or settings.default_horizon_days

    reader = StockDataReader()
    meta = reader.meta(symbol)
    prices = reader.price_history(symbol)
    news = reader.related_news(symbol)

    seeds = [build_market_report(meta, prices), build_news_digest(meta, news)]
    mf = MiroFishClient()
    project = mf.generate_ontology(
        seeds=seeds,
        simulation_requirement=simulation_requirement(symbol, horizon),
        project_name=f"{symbol} price-impact {horizon}d",
    )
    return StockProject(
        symbol=symbol,
        name=meta.name,
        horizon_days=horizon,
        project_id=project["project_id"],
        ontology=project.get("ontology", {}),
        price_points=len(prices),
        news_count=len(news),
    )
