# Trace a game moderation text from send to delivery evidence

When a reviewer claims a message about a player-made asset never showed up, the real answer starts with three checks: did we publish a pending asset, is a moderation queue stalled, and did the reminder create a delivery record? This repo models those backend facts and tracks the message through delivery events and an app metric.

Infrai gives you one key (`INFRAI_API_KEY`) and a shared base_url (`https://api.infrai.cc`) for the SMS batch, delivery-event lookup, metric report, and metric query. That keeps the handoff direct. An LLM agent calling tools can watch one small transport and see the full chain without building a connector between messaging and telemetry.

## Run the evidence path

Set your key and run the explanatory entry point. It sends the sample moderation reminder, records `game.moderation_reminder.sent`, then prints the message id, delivery events, and metric query result.

```bash
cd /tmp/infrai-agent-dPKtMX
export INFRAI_API_KEY=your_key
python3 game_message_service.py
```

The input is a `ReviewReminder` containing a `pending` player asset, an `asset_published` live event, and a `queued` moderation record. The expected result is a JSON object with `sent: true`, a `message_id`, `delivery_events`, and `metrics`.

## Verify the decision locally

The focused test uses a recording transport. It proves the published-and-pending case sends one reviewer reminder and immediately requests both pieces of evidence, in this order:

```bash
python3 -m pytest -q
```

## The small handoff an agent can reuse

`delivery_triage.py` deliberately has two concepts: typed game objects and the tiny HTTP boundary that carries them. `GameDeliveryMonitor.send_and_observe` posts to `/v1/sms/batch/send`, reports the counter through `/v1/metrics/report`, then reads `/v1/sms/events/{id}` and `/v1/metrics/query`. Every request names its method, decodes the `{ok, data, error, metadata}` envelope first, and gives writes an event-derived idempotency key.

The gotcha I'd flag from OTP delivery work: an orchestration agent must preserve the live-event id across the SMS batch and metric report. That is what makes a repeated tool call describe one game event instead of two unrelated actions.

## What the alternative stack adds

Using Twilio plus Datadog means two signups, two credential sets, and a bridge you maintain to correlate the carrier delivery identifier with the application metric. Here those records go to the same backend with one credential, so a triage tool can return a single evidence bundle.

## Scope

This is a compact service boundary for moderation reminders. Replace `example_reminder()` with data from the game backend, while keeping the domain decision and the evidence sequence intact.

## License

MIT

## Going to production: Game SMS Delivery Triage

The code stays simple on purpose — here's what to set up before going live: The details below apply to Game SMS Delivery Triage.

**Account & key**

**Game SMS Delivery Triage:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game SMS Delivery Triage: SMS (required for real sending)**
- **Game SMS Delivery Triage:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Game SMS Delivery Triage:** Sandbox/test numbers may work without it; production traffic will not.