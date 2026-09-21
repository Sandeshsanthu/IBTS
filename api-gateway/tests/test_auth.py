import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException


def _mock_request(headers: dict, client_host: str = "127.0.0.1"):
    req = MagicMock()
    req.headers = headers
    req.client  = MagicMock()
    req.client.host = client_host
    return req


class TestVerifyJwt:

    def test_valid_token_returns_claims(self, valid_jwt_token):
        from app.auth import _verify_jwt
        claims = _verify_jwt(valid_jwt_token)
        assert claims["sub"] == "user-001"

    def test_expired_token_raises_401(self, expired_jwt_token):
        from app.auth import _verify_jwt
        with pytest.raises(HTTPException) as exc:
            _verify_jwt(expired_jwt_token)
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_invalid_token_raises_401(self):
        from app.auth import _verify_jwt
        with pytest.raises(HTTPException) as exc:
            _verify_jwt("not.a.valid.token")
        assert exc.value.status_code == 401

    def test_tampered_token_raises_401(self, valid_jwt_token):
        from app.auth import _verify_jwt
        tampered = valid_jwt_token + "tampered"
        with pytest.raises(HTTPException) as exc:
            _verify_jwt(tampered)
        assert exc.value.status_code == 401


class TestVerifyAuthApiKey:

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_claims(self):
        from app.auth import verify_auth
        from app.config import settings
        req = _mock_request({"X-API-Key": settings.API_KEY})
        claims = await verify_auth(req)
        assert claims["auth_method"] == "api_key"
        assert claims["sub"]         == "api-key-client"

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self):
        from app.auth import verify_auth
        req = _mock_request({"X-API-Key": "wrong-key"})
        with pytest.raises(HTTPException) as exc:
            await verify_auth(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_takes_priority_over_jwt(self, valid_jwt_token):
        from app.auth import verify_auth
        from app.config import settings
        req = _mock_request({
            "X-API-Key":     settings.API_KEY,
            "Authorization": f"Bearer {valid_jwt_token}",
        })
        claims = await verify_auth(req)
        assert claims["auth_method"] == "api_key"


class TestVerifyAuthJwt:

    @pytest.mark.asyncio
    async def test_valid_jwt_bearer_returns_claims(self, valid_jwt_token):
        from app.auth import verify_auth
        req = _mock_request({"Authorization": f"Bearer {valid_jwt_token}"})
        claims = await verify_auth(req)
        assert claims["sub"] == "user-001"

    @pytest.mark.asyncio
    async def test_missing_auth_header_raises_401(self):
        from app.auth import verify_auth
        req = _mock_request({})
        with pytest.raises(HTTPException) as exc:
            await verify_auth(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_raises_401(self, valid_jwt_token):
        from app.auth import verify_auth
        req = _mock_request({"Authorization": f"Basic {valid_jwt_token}"})
        with pytest.raises(HTTPException) as exc:
            await verify_auth(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_jwt_raises_401(self, expired_jwt_token):
        from app.auth import verify_auth
        req = _mock_request({"Authorization": f"Bearer {expired_jwt_token}"})
        with pytest.raises(HTTPException) as exc:
            await verify_auth(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_401(self):
        from app.auth import verify_auth
        req = _mock_request({"Authorization": "Bearer bad.token.here"})
        with pytest.raises(HTTPException) as exc:
            await verify_auth(req)
        assert exc.value.status_code == 401