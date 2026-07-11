"""Settings for the stock price-impact orchestrator.

Kept intentionally small; reads from env (and a local .env if present). See
README.md for the prerequisites these map to.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base URL of the running MiroFish Flask backend (../backend, run.py).
    mirofish_base_url: str = "http://localhost:5001"

    # Read-only Postgres holding the stock price history + news. (Shared DB —
    # keep server-side only; never expose the host in any client response.)
    database_url: str = ""

    # Prediction defaults.
    default_horizon_days: int = 5
    # How many news items to fold into the seed digest.
    news_limit: int = 25
    # Trailing price-history window (trading days) for the market report.
    price_window_days: int = 120

    # Long-poll ceilings (seconds) for MiroFish's async graph/sim/report steps.
    graph_build_timeout_s: int = 600
    simulation_timeout_s: int = 1800
    report_timeout_s: int = 900
    poll_interval_s: float = 3.0


settings = Settings()
