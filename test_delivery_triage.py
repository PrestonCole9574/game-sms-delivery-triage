from typing import Any

from delivery_triage import (
    GameDeliveryMonitor,
    LiveEvent,
    ModerationQueue,
    PlayerAsset,
    ReviewReminder,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, path, payload))
        if path == "/v1/sms/batch/send":
            return {"message_id": "msg-42"}
        return {"points": []}


def test_published_pending_asset_sends_then_collects_delivery_evidence() -> None:
    transport = RecordingTransport()
    reminder = ReviewReminder(
        PlayerAsset("asset-77", "player-12", "Sky Fortress", "pending"),
        LiveEvent("event-501", "asset-77", "asset_published"),
        ModerationQueue("ugc-review", "asset-77", "+15550102000", "queued"),
    )

    result = GameDeliveryMonitor(transport).send_and_observe(reminder)

    assert result["sent"] is True
    assert result["message_id"] == "msg-42"
    assert [(method, path) for method, path, _ in transport.calls] == [
        ("POST", "/v1/sms/batch/send"),
        ("POST", "/v1/metrics/report"),
        ("GET", "/v1/sms/events/msg-42"),
        ("GET", "/v1/metrics/query"),
    ]
    assert transport.calls[0][2] == {
        "messages": [{"to": "+15550102000", "body": "Review Sky Fortress: asset asset-77 is ready."}],
        "idempotency_key": "event-501",
    }
