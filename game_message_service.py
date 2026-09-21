"""Runnable service entry point for moderation-reminder delivery triage."""

from __future__ import annotations

import json

from delivery_triage import (
    GameDeliveryMonitor,
    InfraiError,
    InfraiTransport,
    LiveEvent,
    ModerationQueue,
    PlayerAsset,
    ReviewReminder,
)


def example_reminder() -> ReviewReminder:
    return ReviewReminder(
        asset=PlayerAsset("asset-77", "player-12", "Sky Fortress", "pending"),
        event=LiveEvent("event-501", "asset-77", "asset_published"),
        queue=ModerationQueue("ugc-review", "asset-77", "+15550102000", "queued"),
    )


def main() -> None:
    try:
        result = GameDeliveryMonitor(InfraiTransport()).send_and_observe(example_reminder())
    except InfraiError as exc:
        print(json.dumps({"accepted": False, "code": exc.code, "detail": exc.detail}))
        return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
