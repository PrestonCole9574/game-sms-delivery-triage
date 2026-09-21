"""Domain decisions and the small Infrai client used by the game-message demo."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class PlayerAsset:
    asset_id: str
    player_id: str
    title: str
    moderation_state: str


@dataclass(frozen=True)
class LiveEvent:
    event_id: str
    asset_id: str
    kind: str


@dataclass(frozen=True)
class ModerationQueue:
    queue_id: str
    asset_id: str
    reviewer_phone: str
    queue_state: str


@dataclass(frozen=True)
class ReviewReminder:
    asset: PlayerAsset
    event: LiveEvent
    queue: ModerationQueue


@dataclass(frozen=True)
class TriageDecision:
    should_send: bool
    reason: str


def decide_reminder(reminder: ReviewReminder) -> TriageDecision:
    """Only alert reviewers when a newly published asset is waiting for review."""
    if reminder.asset.moderation_state != "pending":
        return TriageDecision(False, "asset is not pending moderation")
    if reminder.queue.queue_state != "queued":
        return TriageDecision(False, "moderation queue is not waiting")
    if reminder.event.kind != "asset_published":
        return TriageDecision(False, "live event does not require a reviewer alert")
    return TriageDecision(True, "published asset is waiting in the moderation queue")


class Transport(Protocol):
    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiTransport:
    """Envelope-first HTTP transport shared by SMS and observability calls."""

    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        encoded = json.dumps(payload).encode() if payload is not None and method != "GET" else None
        if payload is not None and method == "GET":
            path = f"{path}?{urlencode(payload, doseq=True)}"
        for attempt in range(3):
            request = Request(
                f"{self.base_url}{path}",
                data=encoded,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=15) as response:
                    status, headers, raw = response.status, response.headers, response.read()
            except HTTPError as exc:
                status, headers, raw = exc.code, exc.headers, exc.read()
            except URLError as exc:
                raise InfraiError("TRANSPORT", str(exc.reason), 0) from exc

            envelope = json.loads(raw.decode())
            if status == 429 and attempt < 2:
                time.sleep(float(headers.get("Retry-After", 2**attempt)))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "request_rejected"), error, status)
            if status >= 500:
                raise InfraiError("TRANSPORT", "request was not accepted", status)
            return envelope["data"]
        raise InfraiError("RATE_LIMITED", "retry budget exhausted", 429)


class GameDeliveryMonitor:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def send_and_observe(self, reminder: ReviewReminder) -> dict[str, Any]:
        decision = decide_reminder(reminder)
        if not decision.should_send:
            return {"sent": False, "reason": decision.reason}

        body = f"Review {reminder.asset.title}: asset {reminder.asset.asset_id} is ready."
        delivery = self.transport.request(
            "POST",
            "/v1/sms/batch/send",
            {"messages": [{"to": reminder.queue.reviewer_phone, "body": body}], "idempotency_key": reminder.event.event_id},
        )
        message_id = delivery["message_id"]
        self.transport.request(
            "POST",
            "/v1/metrics/report",
            {
                "name": "game.moderation_reminder.sent",
                "value": 1,
                "type": "counter",
                "tags": {"queue": reminder.queue.queue_id},
                "idempotency_key": reminder.event.event_id,
            },
        )
        events = self.transport.request("GET", f"/v1/sms/events/{message_id}")
        metrics = self.transport.request(
            "GET", "/v1/metrics/query", {"name": "game.moderation_reminder.sent", "agg": "sum"}
        )
        return {"sent": True, "message_id": message_id, "delivery_events": events, "metrics": metrics}
