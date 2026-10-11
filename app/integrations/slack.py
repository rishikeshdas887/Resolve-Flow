"""Optional Slack adapter.

Implemented: request-signature verification (HMAC-SHA256 per Slack docs) and
a notification sender. Live Slack delivery requires SLACK_SIGNING_SECRET /
SLACK_BOT_TOKEN and is NOT exercised without credentials — unit tests cover
signature verification and payload construction only.
"""
import hashlib
import hmac
import time
from dataclasses import dataclass

import httpx

SLACK_API_BASE = "https://slack.com/api"
SIGNATURE_TOLERANCE_SECONDS = 60 * 5


def verify_slack_signature(
    signing_secret: str, timestamp: str, body: bytes, signature: str
) -> bool:
    """Verify X-Slack-Signature per Slack's signing-secret scheme."""
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    basestring = b"v0:" + str(ts).encode() + b":" + body
    expected = "v0=" + hmac.new(
        signing_secret.encode(), basestring, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass
class SlackNotifier:
    bot_token: str
    base_url: str = SLACK_API_BASE
    timeout: float = 10.0

    @property
    def configured(self) -> bool:
        return bool(self.bot_token)

    def post_message(self, channel: str, text: str) -> dict:
        """Post a message. Raises on transport or API failure — callers must
        not treat a failed send as delivered."""
        if not self.bot_token:
            raise RuntimeError("Slack bot token not configured")
        resp = httpx.post(
            f"{self.base_url}/chat.postMessage",
            headers={"Authorization": f"Bearer {self.bot_token}"},
            json={"channel": channel, "text": text[:3000]},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        return data


def notifier_from_env() -> SlackNotifier:
    import os

    return SlackNotifier(bot_token=os.environ.get("SLACK_BOT_TOKEN", ""))
