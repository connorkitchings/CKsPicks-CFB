"""Best-effort, redacted operation-failure notification adapters."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from cks_picks_cfb.ops.contracts import OperationContext


class _NumpySafeEncoder(json.JSONEncoder):
    """Serialize numpy scalar types that the default encoder rejects."""

    def default(self, obj: Any) -> Any:
        try:
            import numpy as np  # noqa: PLC0415

            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def json_dumps(value: Any) -> str:
    return json.dumps(value, cls=_NumpySafeEncoder)


class FailureNotifier(Protocol):
    """Best-effort observer for a durably recorded failed pipeline step."""

    def notify(
        self,
        context: OperationContext,
        step: str,
        *,
        category: str,
        detail: str,
    ) -> None: ...


@dataclass(frozen=True)
class WebhookFailureNotifier:
    """Optional generic JSON webhook notifier configured by environment."""

    url: str
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "WebhookFailureNotifier | None":
        url = os.getenv("CFB_OPS_ALERT_WEBHOOK_URL")
        if not url:
            return None
        try:
            timeout_seconds = float(os.getenv("CFB_OPS_ALERT_TIMEOUT_SECONDS", "5"))
        except ValueError as exc:
            raise ValueError("CFB_OPS_ALERT_TIMEOUT_SECONDS must be numeric") from exc
        if timeout_seconds <= 0:
            raise ValueError("CFB_OPS_ALERT_TIMEOUT_SECONDS must be positive")
        return cls(url=url, timeout_seconds=timeout_seconds)

    def notify(
        self,
        context: OperationContext,
        step: str,
        *,
        category: str,
        detail: str,
    ) -> None:
        payload = {
            "event": "pipeline_step_failed",
            "pipeline_run_id": context.pipeline_run_id,
            "prediction_run_id": context.prediction_run_id,
            "command": context.command,
            "environment": context.environment,
            "season": context.season,
            "week": context.week,
            "step": step,
            "error_category": category,
            "error_detail": detail[:2000],
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        request = Request(
            self.url,
            data=json_dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Webhook returned HTTP {response.status}")
        except (OSError, URLError) as exc:
            raise RuntimeError(f"Webhook delivery failed: {exc}") from exc
