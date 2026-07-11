"""FastAPI entry for the price-impact orchestrator.

    uvicorn stock_seed.api:app --reload --port 8090
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import settings
from .orchestrator import predict_price_impact

app = FastAPI(title="Stock price-impact (MiroFish)", version="0.0.1")


class PredictRequest(BaseModel):
    symbol: str
    horizon_days: int | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "stock_seed", "mirofish": settings.mirofish_base_url}


@app.post("/predict")
def predict(req: PredictRequest) -> dict:
    try:
        result = predict_price_impact(req.symbol, req.horizon_days)
    except NotImplementedError as exc:  # scaffold: DB queries not wired yet
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface engine errors to the caller
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "symbol": result.symbol,
        "horizon_days": result.horizon_days,
        "project_id": result.project_id,
        "simulation_id": result.simulation_id,
        "report": result.report,
    }
