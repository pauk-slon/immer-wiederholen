import hashlib
import hmac
from datetime import UTC, datetime


def make_telegram_login_payload(bot_token: str, **overrides: str) -> dict[str, str]:
    """A correctly-signed Telegram Login Widget callback payload — the same
    shape validate_telegram_login() expects, signed for the given bot_token
    so it round-trips through real validation. Overrides apply *before*
    signing (e.g. a stale auth_date), matching what a genuinely different
    payload from Telegram would have looked like — tampering *after*
    signing is what the "rejects a tampered field" tests exercise instead.
    """
    payload = {
        "id": "12345",
        "first_name": "Test",
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        **overrides,
    }
    data_check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    payload["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return payload
