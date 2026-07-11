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
    #
    # NOTE: the OASIS simulation is a multi-step lifecycle in the backend —
    #   /simulation/create  → /simulation/prepare  (poll /prepare/status)
    #   → /simulation/start  (poll /<id>/run-status) → then the report.
    # The MiroFish FRONTEND drives these interactively at /process/:projectId,
    # which is the primary (embedded) UI path. This headless orchestration is
    # for the /predict endpoint; the prepare/start request bodies (config knobs)
    # still need confirming against a booted backend — marked TODO.
    def run_simulation(self, *, project_id: str, graph_id: str | None = None) -> str:
        payload = {"project_id": project_id}
        if graph_id:
            payload["graph_id"] = graph_id
        with self._client(60) as c:
            sim = self._data(c.post("/api/simulation/create", json=payload))
            simulation_id = sim.get("simulation_id")
            if not simulation_id:
                raise MiroFishError("no simulation_id returned")

            # TODO: prepare/start likely take config params the LLM generates;
            # confirm the exact bodies. Statuses polled below are best-effort.
            c.post("/api/simulation/prepare", json={"simulation_id": simulation_id})
        self._poll(
            "/api/simulation/prepare/status",
            {"simulation_id": simulation_id},
            settings.simulation_timeout_s,
            method="post",
        )
        with self._client(60) as c:
            c.post("/api/simulation/start", json={"simulation_id": simulation_id})
        self._poll(
            f"/api/simulation/{simulation_id}/run-status",
            None,
            settings.simulation_timeout_s,
            method="get",
        )
        return simulation_id

    def _poll(self, path: str, body: dict | None, timeout_s: int, *, method: str) -> dict:
        deadline = time.monotonic() + timeout_s
        with self._client(30) as c:
            while time.monotonic() < deadline:
                resp = c.post(path, json=body) if method == "post" else c.get(path)
                data = self._data(resp)
                status = str(data.get("status", "")).lower()
                if status in {"completed", "success", "done", "finished"}:
                    return data
                if status in {"failed", "error"}:
                    raise MiroFishError(data.get("error") or f"{path} failed")
                time.sleep(settings.poll_interval_s)
        raise MiroFishError(f"{path} timed out")

    # 4) Generate the prediction report -----------------------------------------
    def generate_report(self, simulation_id: str) -> dict:
        with self._client(60) as c:
            self._data(
                c.post("/api/report/generate", json={"simulation_id": simulation_id})
            )
        # Report generation is async — poll, then fetch the finished report.
        self._poll(
            "/api/report/generate/status",
            {"simulation_id": simulation_id},
            settings.report_timeout_s,
            method="post",
        )
        with self._client(60) as c:
            return self._data(c.get(f"/api/report/by-simulation/{simulation_id}"))
