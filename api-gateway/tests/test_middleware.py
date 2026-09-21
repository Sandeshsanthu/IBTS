import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response


# ── AuthMiddleware ─────────────────────────────────────────────────────────
def _auth_app():
    from fastapi import FastAPI
    from app.middleware.auth_metrics import AuthMiddleware
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/payments")
    def payments():
        return {"ok": True}

    @app.get("/metrics")
    def metrics():
        return {"ok": True}

    return app


class TestAuthMiddleware:

    def test_valid_api_key_passes(self):
        with TestClient(_auth_app()) as client:
            resp = client.get(
                "/payments",
                headers={"x-api-key": "ibts-api-key-dev"}
            )
        assert resp.status_code == 200

    def test_second_valid_key_passes(self):
        with TestClient(_auth_app()) as client:
            resp = client.get(
                "/payments",
                headers={"x-api-key": "ibts-api-key-dev-2"}
            )
        assert resp.status_code == 200

    def test_missing_api_key_returns_401(self):
        with TestClient(_auth_app()) as client:
            resp = client.get("/payments")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self):
        with TestClient(_auth_app()) as client:
            resp = client.get(
                "/payments",
                headers={"x-api-key": "wrong-key"}
            )
        assert resp.status_code == 403

    def test_missing_key_increments_auth_failure_metric(self):
        import app.middleware.auth_metrics as am
        am.AUTH_FAILURES_TOTAL.reset_mock()
        with TestClient(_auth_app()) as client:
            client.get("/payments")
        am.AUTH_FAILURES_TOTAL.labels.assert_called_with(
            service="api-gateway", reason="missing_key"
        )

    def test_invalid_key_increments_auth_failure_metric(self):
        import app.middleware.auth_metrics as am
        am.AUTH_FAILURES_TOTAL.reset_mock()
        with TestClient(_auth_app()) as client:
            client.get("/payments", headers={"x-api-key": "bad"})
        am.AUTH_FAILURES_TOTAL.labels.assert_called_with(
            service="api-gateway", reason="invalid_key"
        )

    def test_metrics_path_skips_auth(self):
        with TestClient(_auth_app()) as client:
            resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_health_path_skips_auth(self):
        from fastapi import FastAPI
        from app.middleware.auth_metrics import AuthMiddleware
        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/health")
        def health():
            return {"status": "UP"}

        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200


# ── RateLimitMiddleware ────────────────────────────────────────────────────
def _rl_app(mock_redis, max_requests: int = 5):
    from fastapi import FastAPI
    from app.middleware.rate_limit_metrics import RateLimitMiddleware
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware,
                       redis_client=mock_redis,
                       max_requests=max_requests)

    @app.get("/payments")
    def payments():
        return {"ok": True}

    @app.get("/metrics")
    def metrics():
        return {"ok": True}

    return app


class TestRateLimitMiddleware:

    def _mock_redis(self, count: int = 1, ttl: int = 30):
        r = MagicMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[count, ttl])
        r.pipeline.return_value = pipe
        r.expire = AsyncMock()
        return r

    def test_under_limit_returns_200(self):
        redis = self._mock_redis(count=1)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            resp = client.get("/payments")
        assert resp.status_code == 200

    def test_over_limit_returns_429(self):
        redis = self._mock_redis(count=6)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            resp = client.get("/payments")
        assert resp.status_code == 429

    def test_429_includes_retry_after_header(self):
        redis = self._mock_redis(count=6, ttl=30)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            resp = client.get("/payments")
        assert "retry-after" in {h.lower() for h in resp.headers}

    def test_under_limit_includes_remaining_header(self):
        redis = self._mock_redis(count=2)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            resp = client.get("/payments")
        assert "x-ratelimit-remaining" in {h.lower() for h in resp.headers}

    def test_metrics_path_skips_rate_limit(self):
        redis = self._mock_redis(count=999)
        with TestClient(_rl_app(redis, max_requests=1)) as client:
            resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_over_limit_increments_metric(self):
        import app.middleware.rate_limit_metrics as rlm
        rlm.RATE_LIMIT_HITS_TOTAL.reset_mock()
        redis = self._mock_redis(count=10)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            client.get("/payments")
        rlm.RATE_LIMIT_HITS_TOTAL.labels.return_value.inc.assert_called()

    def test_negative_ttl_triggers_expire(self):
        """When TTL=-1 (no expiry set), middleware must call expire."""
        redis = self._mock_redis(count=1, ttl=-1)
        with TestClient(_rl_app(redis, max_requests=5)) as client:
            resp = client.get("/payments")
        assert resp.status_code == 200
        redis.expire.assert_called()