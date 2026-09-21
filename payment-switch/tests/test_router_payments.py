import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import httpx


# ── helpers ────────────────────────────────────────────────────────────────
def _app():
    """Build FastAPI app with all shared deps already mocked by conftest."""
    from fastapi import FastAPI
    from app.routers.payments import router
    app = FastAPI()
    app.include_router(router)
    return app


def _valid_req():
    return {
        "idempotency_key": "idem-key-12345678",
        "payer_vpa":       "alice@oksbi",
        "payee_vpa":       "bob@okhdfcbank",
        "amount_paise":    10000,
        "remarks":         "test payment",
    }


def _route_resp():
    return {
        "bankCode":         "SBI",
        "primaryEndpoint":  "https://api.sbi.com/upi/pay",
        "fallbackEndpoint": "https://fallback.sbi.com/upi/pay",
    }


def _bank_resp(status="SUCCESS", rrn="SBI-RRN-001"):
    return {
        "transactionId":   "txn-001",
        "status":          status,
        "bankReferenceId": rrn,
        "errorMessage":    None,
    }


# ── idempotency + routing + bank mocks ─────────────────────────────────────
IDM_NEW    = {"duplicate": False}
IDM_CACHED = {
    "duplicate": True,
    "responsePayload": '{"txn_id":"txn-cached","status":"SUCCESS","bank_rrn":"SBI-001","message":"SUCCESS","source":"CACHED"}'
}


class TestInitiatePaymentSuccess:
    """Happy path — new payment, bank returns SUCCESS."""

    @pytest.mark.asyncio
    async def test_new_payment_returns_200(self):
        app = _app()
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",new=AsyncMock(return_value=_bank_resp())), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"), \
             patch("app.routers.payments.dynamo.get_txn_by_bank_rrn", return_value=None), \
             patch("app.routers.payments.idm_client.complete",    new=AsyncMock()), \
             patch("app.routers.payments.sqs.emit_settlement_event"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"]   == "SUCCESS"
        assert body["source"]   == "NEW"
        assert body["bank_rrn"] == "SBI-RRN-001"

    @pytest.mark.asyncio
    async def test_new_payment_writes_txn_to_dynamo(self):
        app = _app()
        mock_write = MagicMock()
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",new=AsyncMock(return_value=_bank_resp())), \
             patch("app.routers.payments.dynamo.write_txn",       mock_write), \
             patch("app.routers.payments.dynamo.update_state"), \
             patch("app.routers.payments.dynamo.get_txn_by_bank_rrn", return_value=None), \
             patch("app.routers.payments.idm_client.complete",    new=AsyncMock()), \
             patch("app.routers.payments.sqs.emit_settlement_event"):

            with TestClient(app) as client:
                client.post("/api/v1/payments/initiate", json=_valid_req())

        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_payment_updates_state_to_processing_then_success(self):
        app = _app()
        mock_update = MagicMock()
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",new=AsyncMock(return_value=_bank_resp())), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state",    mock_update), \
             patch("app.routers.payments.dynamo.get_txn_by_bank_rrn", return_value=None), \
             patch("app.routers.payments.idm_client.complete",    new=AsyncMock()), \
             patch("app.routers.payments.sqs.emit_settlement_event"):

            with TestClient(app) as client:
                client.post("/api/v1/payments/initiate", json=_valid_req())

        states = [call.args[1].value for call in mock_update.call_args_list]
        assert "PROCESSING" in states
        assert "SUCCESS"    in states

    @pytest.mark.asyncio
    async def test_bank_failed_returns_502(self):
        app = _app()
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",new=AsyncMock(return_value=_bank_resp(status="FAILED", rrn=None))), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"), \
             patch("app.routers.payments.dynamo.get_txn_by_bank_rrn", return_value=None), \
             patch("app.routers.payments.idm_client.complete",    new=AsyncMock()), \
             patch("app.routers.payments.sqs.emit_settlement_event"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 502


class TestInitiatePaymentIdempotency:
    """Duplicate / cached request paths."""

    @pytest.mark.asyncio
    async def test_cached_request_returns_200_from_payload(self):
        app = _app()
        with patch("app.routers.payments.idm_client.check", new=AsyncMock(return_value=IDM_CACHED)):
            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"]  == "CACHED"
        assert body["txn_id"]  == "txn-cached"

    @pytest.mark.asyncio
    async def test_cached_request_does_not_call_bank(self):
        app = _app()
        mock_bank = AsyncMock()
        with patch("app.routers.payments.idm_client.check",        new=AsyncMock(return_value=IDM_CACHED)), \
             patch("app.routers.payments.adp_client.send_payment", mock_bank):

            with TestClient(app) as client:
                client.post("/api/v1/payments/initiate", json=_valid_req())

        mock_bank.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_no_payload_falls_back_to_dynamo(self):
        app = _app()
        idm_no_payload = {"duplicate": True, "responsePayload": None}
        dynamo_record  = {
            "txn_id":   "txn-dynamo",
            "state":    "SUCCESS",
            "bank_rrn": "SBI-001",
        }
        with patch("app.routers.payments.idm_client.check",
                   new=AsyncMock(return_value=idm_no_payload)), \
             patch("app.routers.payments.dynamo.get_txn_by_idempotency_key",
                   return_value=dynamo_record):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 200
        assert resp.json()["txn_id"] == "txn-dynamo"

    @pytest.mark.asyncio
    async def test_cached_no_payload_no_dynamo_record_returns_500(self):
        app = _app()
        idm_no_payload = {"duplicate": True, "responsePayload": None}
        with patch("app.routers.payments.idm_client.check",
                   new=AsyncMock(return_value=idm_no_payload)), \
             patch("app.routers.payments.dynamo.get_txn_by_idempotency_key",
                   return_value=None):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 500


class TestInitiatePaymentErrors:
    """Downstream failure paths."""

    @pytest.mark.asyncio
    async def test_idempotency_guard_down_returns_503(self):
        app = _app()
        with patch("app.routers.payments.idm_client.check",
                   new=AsyncMock(side_effect=Exception("guard down"))):
            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_router_down_returns_503(self):
        app = _app()
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(side_effect=Exception("router down"))), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_vpa_unresolvable_returns_http_error_code(self):
        app = _app()
        mock_resp = MagicMock(); mock_resp.status_code = 404
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa",
                   new=AsyncMock(side_effect=httpx.HTTPStatusError(
                       "404", request=MagicMock(), response=mock_resp
                   ))), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_bank_adapter_timeout_returns_504(self):
        app = _app()
        import asyncio
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",
                   new=AsyncMock(side_effect=asyncio.TimeoutError())), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 504

    @pytest.mark.asyncio
    async def test_bank_adapter_http_error_returns_502(self):
        app = _app()
        mock_resp = MagicMock(); mock_resp.status_code = 503
        with patch("app.routers.payments.idm_client.check",       new=AsyncMock(return_value=IDM_NEW)), \
             patch("app.routers.payments.rtr_client.resolve_vpa", new=AsyncMock(return_value=_route_resp())), \
             patch("app.routers.payments.adp_client.send_payment",
                   new=AsyncMock(side_effect=httpx.HTTPStatusError(
                       "503", request=MagicMock(), response=mock_resp
                   ))), \
             patch("app.routers.payments.dynamo.write_txn"), \
             patch("app.routers.payments.dynamo.update_state"):

            with TestClient(app) as client:
                resp = client.post("/api/v1/payments/initiate", json=_valid_req())

        assert resp.status_code == 502


class TestGetPayment:
    """GET /api/v1/payments/{txn_id}"""

    @pytest.mark.asyncio
    async def test_get_existing_txn_returns_200(self):
        app = _app()
        dynamo_record = {
            "txn_id":   "txn-001",
            "state":    "SUCCESS",
            "bank_rrn": "SBI-001",
            "error":    None,
        }
        with patch("app.routers.payments.dynamo.get_txn", return_value=dynamo_record):
            with TestClient(app) as client:
                resp = client.get("/api/v1/payments/txn-001")

        assert resp.status_code == 200
        assert resp.json()["txn_id"] == "txn-001"
        assert resp.json()["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_get_nonexistent_txn_returns_404(self):
        app = _app()
        with patch("app.routers.payments.dynamo.get_txn", return_value=None):
            with TestClient(app) as client:
                resp = client.get("/api/v1/payments/txn-not-found")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_failed_txn_returns_error_message(self):
        app = _app()
        dynamo_record = {
            "txn_id": "txn-002",
            "state":  "FAILED",
            "error":  "bank timeout",
        }
        with patch("app.routers.payments.dynamo.get_txn", return_value=dynamo_record):
            with TestClient(app) as client:
                resp = client.get("/api/v1/payments/txn-002")

        assert resp.status_code == 200
        assert resp.json()["message"] == "bank timeout"