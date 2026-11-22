"""Minimal client for the Toxiproxy HTTP API."""

from typing import Any

import httpx


class Toxiproxy:
    def __init__(self, base_url: str = "http://127.0.0.1:8474", client: httpx.Client | None = None):
        self._http = client or httpx.Client(base_url=base_url, timeout=10)

    def proxies(self) -> dict[str, Any]:
        resp = self._http.get("/proxies")
        resp.raise_for_status()
        return resp.json()

    def add_toxic(
        self, proxy: str, name: str, type_: str, stream: str, attributes: dict[str, int]
    ) -> None:
        resp = self._http.post(
            f"/proxies/{proxy}/toxics",
            json={
                "name": name,
                "type": type_,
                "stream": stream,
                "toxicity": 1.0,
                "attributes": attributes,
            },
        )
        resp.raise_for_status()

    def reset(self) -> None:
        """Remove every toxic and re-enable every proxy."""
        self._http.post("/reset").raise_for_status()
