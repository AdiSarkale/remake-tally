"""JWT security regression coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token


def test_access_token_contains_required_security_claims():
    token = create_access_token("admin", "Admin", "company-a")
    payload = decode_access_token(token)

    assert payload["company_id"] == "company-a"
    assert payload["sub"] == "admin"
    assert payload["iss"] == get_settings().jwt_issuer
    assert payload["aud"] == get_settings().jwt_audience
    assert payload["jti"]


def test_token_with_wrong_audience_is_rejected():
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "admin",
            "role": "Admin",
            "company_id": "company-a",
            "iat": now,
            "jti": "wrong-audience-test",
            "iss": settings.jwt_issuer,
            "aud": "different-service",
            "exp": now + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(token)
