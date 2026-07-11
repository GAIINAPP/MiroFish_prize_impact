"""HTTP client for the vendored MiroFish Flask backend.

Drives the four-step pipeline documented in ../backend/app/api:
    1. POST /api/graph/ontology/generate   (multipart: files[], simulation_requirement)
    2. POST /api/graph/build                (build the GraphRAG; async → poll task)
    3. POST /api/simulation/create          (JSON: project_id [, graph_id])
    4. POST /api/report/generate            (JSON: simulation_id)

Each async step exposes a status/task route we poll until terminal. Routes that
still need verifying against ../backend are marked TODO.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .config import settings


@dataclass
class SeedFile:
    filename: str
    content: str
    content_type: str = "text/markdown"


class MiroFishError(RuntimeError):
    pass


class MiroFishClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.mirofish_base_url).rstrip("/")

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout)

    @staticmethod
    def _data(resp: httpx.Response) -> dict:
        body = resp.json()
        if not resp.is_success or not body.get("success", True):
            raise MiroFishError(body.get("error") or f"MiroFish {resp.status_code}")
        return body.get("data", body)

    # 1) Seeds + requirement → project + ontology --------------------------------
    def generate_ontology(
        self,
        *,
        seeds: list[SeedFile],
        simulation_requirement: str,
        project_name: str,
        additional_context: str = "",
    ) -> dict:
        files = [
            ("files", (s.filename, s.content.encode("utf-8"), s.content_type))
            for s in seeds
        ]
        form = {
            "simulation_requirement": simulation_requirement,
            "project_name": project_name,
            "additional_context": additional_context,
        }
        with self._client(120) as c:
            return self._data(c.post("/api/graph/ontology/generate", data=form, files=files))

    # 2) Build the GraphRAG ------------------------------------------------------
    def build_graph(self, project_id: str) -> dict:
        with self._client(60) as c:
            data = self._data(c.post("/api/graph/build", json={"project_id": project_id}))
        task_id = data.get("task_id")
        if task_id:
            self._poll_task(task_id, settings.graph_build_timeout_s)
        return data

    def _poll_task(self, task_id: str, timeout_s: int) -> dict:
        # TODO: confirm terminal statuses / payload shape of /api/graph/task/<id>.
        deadline = time.monotonic() + timeout_s
        with self._client(30) as c:
            while time.monotonic() < deadline:
                data = self._data(c.get(f"/api/graph/task/{task_id}"))
                status = str(data.get("status", "")).lower()
                if status in {"completed", "graph_completed", "success", "done"}:
                    return data
                if status in {"failed", "error"}:
                    raise MiroFishError(data.get("error") or "graph build failed")
                time.sleep(settings.poll_interval_s)
        raise MiroFishError("graph build timed out")

    # 3) Run the OASIS simulation ------------------------------------------------
    def run_simulation(self, *, project_id: str, graph_id: str | None = None) -> str:
        payload = {"project_id": project_id}
        if graph_id:
            payload["graph_id"] = graph_id
        with self._client(60) as c:
            data = self._data(c.post("/api/simulation/create", json=payload))
        simulation_id = data.get("simulation_id")
        if not simulation_id:
            raise MiroFishError("no simulation_id returned")
        # TODO: confirm whether /create auto-runs or needs a /start, and the
        # status route to poll to completion before report generation.
        self._poll_simulation(simulation_id)
        return simulation_id

    def _poll_simulation(self, simulation_id: str) -> None:
        # TODO: implement against the real simulation status route.
        deadline = time.monotonic() + settings.simulation_timeout_s
        with self._client(30) as c:
            while time.monotonic() < deadline:
                data = self._data(c.get(f"/api/simulation/{simulation_id}/status"))
                status = str(data.get("status", "")).lower()
                if status in {"completed", "success", "done"}:
                    return
                if status in {"failed", "error"}:
                    raise MiroFishError(data.get("error") or "simulation failed")
                time.sleep(settings.poll_interval_s)
        raise MiroFishError("simulation timed out")

    # 4) Generate the prediction report -----------------------------------------
    def generate_report(self, simulation_id: str) -> dict:
        with self._client(settings.report_timeout_s) as c:
            return self._data(
                c.post("/api/report/generate", json={"simulation_id": simulation_id})
            )
