from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TestbedClient:
    def __init__(
        self,
        api_base_url: str,
        sdn_base_url: str,
        request_timeout_s: float = 20.0,
        sdn_timeout_s: float = 10.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.sdn_base_url = sdn_base_url.rstrip("/")
        self.request_timeout_s = request_timeout_s
        self.sdn_timeout_s = sdn_timeout_s

    def _request_json(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout_s: Optional[float] = None,
    ) -> Tuple[int, Dict[str, Any], float]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=body, headers=headers, method=method)
        start = time.perf_counter()
        try:
            with urlopen(req, timeout=timeout_s or self.request_timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return resp.status, json.loads(raw or "{}"), elapsed_ms
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError:
                parsed = {"detail": raw}
            return exc.code, parsed, elapsed_ms
        except URLError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return 0, {"detail": str(exc.reason)}, elapsed_ms

    def health(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("GET", f"{self.api_base_url}/health")

    def reset(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("POST", f"{self.api_base_url}/orchestrate/reset")

    def set_alert(self, alert: bool) -> Tuple[int, Dict[str, Any], float]:
        value = "true" if alert else "false"
        return self._request_json("POST", f"{self.api_base_url}/orchestrate/alert?alert={value}")

    def orchestrate(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("POST", f"{self.api_base_url}/orchestrate", payload)

    def state(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("GET", f"{self.api_base_url}/orchestrate/state")

    def status(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("GET", f"{self.api_base_url}/orchestrate/status")

    def free(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json("POST", f"{self.api_base_url}/orchestrate/free", payload)

    def steer_status(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json(
            "GET",
            f"{self.sdn_base_url}/steer/status",
            timeout_s=self.sdn_timeout_s,
        )

    def msd_drops(self) -> Tuple[int, Dict[str, Any], float]:
        return self._request_json(
            "GET",
            f"{self.sdn_base_url}/stats/msd_drops",
            timeout_s=self.sdn_timeout_s,
        )

