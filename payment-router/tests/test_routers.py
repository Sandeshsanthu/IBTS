import pytest
import json
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


# ── app factories ──────────────────────────────────────────────────────────
def _route_app():
    from fastapi import FastAPI
    from app.routers.route_router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _payment_app():
    from fastapi import FastAPI
    from app.routers.payment_router import router
    app = FastAPI()
    app.include_router(router)
    return app


class TestRouteRouter:

    def _svc(self, mock_repo, mock_redis, route=None):
        from app.services.routing_service import RoutingService
        if route:
            mock_redis.get.return_value = None
            mock_repo.find_by_bank_code.return_value = route
        return RoutingService(mock_repo, mock_redis)

    def test_resolve_vpa_returns_200(self, mock_repo, mock_redis, sbi_route):
        svc = self._svc(mock_repo, mock_redis, sbi_route)
        app = _route_app()

        # ── FastAPI dependency override — the correct way ──────────────────
        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post("/api/v1/route/resolve", json={"vpa": "alice@sbi"})

        assert resp.status_code == 200
        assert resp.json()["bankCode"]     == "SBI"
        assert resp.json()["resolvedFrom"] == "DB"

    def test_resolve_ifsc_returns_200(self, mock_repo, mock_redis, sbi_route):
        svc = self._svc(mock_repo, mock_redis, sbi_route)
        app = _route_app()

        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/route/resolve",
                json={"ifsc": "SBIN0001234"}
            )

        assert resp.status_code == 200
        assert resp.json()["bankCode"] == "SBI"

    def test_resolve_unknown_vpa_returns_404(self, mock_repo, mock_redis):
        svc = self._svc(mock_repo, mock_redis)
        app = _route_app()

        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/route/resolve",
                json={"vpa": "user@unknownbank"}
            )

        assert resp.status_code == 404

    def test_resolve_neither_vpa_nor_ifsc_returns_422(self, mock_repo, mock_redis):
        svc = self._svc(mock_repo, mock_redis)
        app = _route_app()

        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post("/api/v1/route/resolve", json={})

        assert resp.status_code == 422

    def test_resolve_both_vpa_and_ifsc_returns_422(self, mock_repo, mock_redis):
        svc = self._svc(mock_repo, mock_redis)
        app = _route_app()

        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/route/resolve",
                json={"vpa": "alice@sbi", "ifsc": "SBIN0001234"}
            )

        assert resp.status_code == 422

    def test_cache_hit_returns_cache_source(self, mock_repo, mock_redis, sbi_route):
        mock_redis.get.return_value  = json.dumps(sbi_route)
        mock_redis.pttl.return_value = 150_000
        svc = self._svc(mock_repo, mock_redis)
        app = _route_app()

        from app.dependencies import get_routing_service
        app.dependency_overrides[get_routing_service] = lambda: svc

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/route/resolve",
                json={"vpa": "alice@sbi"}
            )

        assert resp.status_code == 200
        assert resp.json()["resolvedFrom"] == "CACHE"


class TestPaymentRouter:

    def _valid_req(self):
        return {
            "transactionId": "txn-001",
            "payerVpa":      "alice@sbi",
            "payeeVpa":      "bob@hdfc",
            "amount":        100.00,
            "currency":      "INR",
            "remarks":       "test",
        }

    def _svc(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route
        return RoutingService(mock_repo, mock_redis)

    @pytest.mark.asyncio
    async def test_initiate_success_returns_bank_response(
        self, mock_repo, mock_redis, sbi_route
    ):
        svc = self._svc(mock_repo, mock_redis, sbi_route)

        bank_resp = MagicMock()
        bank_resp.status_code = 200
        bank_resp.json.return_value = {"status": "SUCCESS", "transactionId": "txn-001"}
        bank_resp.raise_for_status = MagicMock()

        with patch("app.routers.payment_router._get_routing_service",
                   return_value=svc), \
             patch("app.routers.payment_router.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=bank_resp
            )
            with TestClient(_payment_app()) as client:
                resp = client.post(
                    "/api/v1/payment/initiate", json=self._valid_req()
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_initiate_bank_http_error_returns_correct_status(
        self, mock_repo, mock_redis, sbi_route
    ):
        svc = self._svc(mock_repo, mock_redis, sbi_route)
        err_resp = MagicMock()
        err_resp.status_code = 503
        err_resp.text = "Service Unavailable"

        with patch("app.routers.payment_router._get_routing_service",
                   return_value=svc), \
             patch("app.routers.payment_router.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=err_resp
                )
            )
            with TestClient(_payment_app()) as client:
                resp = client.post(
                    "/api/v1/payment/initiate", json=self._valid_req()
                )

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_initiate_bank_unreachable_returns_502(
        self, mock_repo, mock_redis, sbi_route
    ):
        svc = self._svc(mock_repo, mock_redis, sbi_route)

        with patch("app.routers.payment_router._get_routing_service",
                   return_value=svc), \
             patch("app.routers.payment_router.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("unreachable")
            )
            with TestClient(_payment_app()) as client:
                resp = client.post(
                    "/api/v1/payment/initiate", json=self._valid_req()
                )

        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_initiate_unknown_vpa_returns_404(self, mock_repo, mock_redis):
        from app.services.routing_service import RoutingService
        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = None
        svc = RoutingService(mock_repo, mock_redis)

        with patch("app.routers.payment_router._get_routing_service",
                   return_value=svc):
            with TestClient(_payment_app()) as client:
                req = self._valid_req()
                req["payerVpa"] = "user@unknownbank"
                resp = client.post("/api/v1/payment/initiate", json=req)

        assert resp.status_code == 404