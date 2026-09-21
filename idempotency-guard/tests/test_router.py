import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.models import CheckResponse


def _app():
    from fastapi import FastAPI
    from app.router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _new_response():
    return CheckResponse(
        duplicate=False, status="PROCESSING", transactionId="idem-001"
    )


def _dup_response(payload='{"txn_id":"txn-001","status":"SUCCESS"}'):
    return CheckResponse(
        duplicate=True, status="SUCCESS",
        transactionId="idem-001", responsePayload=payload,
    )


VALID_HEADERS = {
    "X-Idempotency-Key": "idem-key-001",
    "X-Caller-Service":  "payment-switch",
}


class TestCheckEndpoint:

    def test_new_request_returns_200(self):
        with patch("app.router.service.check", return_value=_new_response()):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/check",
                    json={"transactionRefId": "txn-ref-001"},
                    headers=VALID_HEADERS,
                )
        assert resp.status_code == 200
        assert resp.json()["duplicate"] is False

    def test_duplicate_request_returns_409(self):
        with patch("app.router.service.check", return_value=_dup_response()):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/check",
                    json={"transactionRefId": "txn-ref-001"},
                    headers=VALID_HEADERS,
                )
        assert resp.status_code == 409
        assert resp.json()["duplicate"] is True

    def test_duplicate_response_contains_payload(self):
        with patch("app.router.service.check", return_value=_dup_response()):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/check",
                    json={"transactionRefId": "txn-ref-001"},
                    headers=VALID_HEADERS,
                )
        assert resp.json()["responsePayload"] is not None

    def test_missing_idempotency_key_header_returns_422(self):
        with TestClient(_app()) as client:
            resp = client.post(
                "/api/v1/idempotency/check",
                json={"transactionRefId": "txn-ref-001"},
                headers={"X-Caller-Service": "payment-switch"},
            )
        assert resp.status_code == 422

    def test_missing_caller_service_header_returns_422(self):
        with TestClient(_app()) as client:
            resp = client.post(
                "/api/v1/idempotency/check",
                json={"transactionRefId": "txn-ref-001"},
                headers={"X-Idempotency-Key": "idem-key-001"},
            )
        assert resp.status_code == 422

    def test_missing_body_returns_422(self):
        with TestClient(_app()) as client:
            resp = client.post(
                "/api/v1/idempotency/check",
                json={},
                headers=VALID_HEADERS,
            )
        assert resp.status_code == 422

    def test_new_response_status_is_processing(self):
        with patch("app.router.service.check", return_value=_new_response()):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/check",
                    json={"transactionRefId": "txn-ref-001"},
                    headers=VALID_HEADERS,
                )
        assert resp.json()["status"] == "PROCESSING"


class TestCompleteEndpoint:

    def test_complete_returns_204(self):
        with patch("app.router.service.complete", return_value=None):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/complete",
                    json={
                        "transactionId": "txn-001",
                        "finalStatus":   "SUCCESS",
                    },
                )
        assert resp.status_code == 204

    def test_complete_calls_service_complete(self):
        mock_complete = MagicMock(return_value=None)
        with patch("app.router.service.complete", mock_complete):
            with TestClient(_app()) as client:
                client.post(
                    "/api/v1/idempotency/complete",
                    json={
                        "transactionId": "txn-001",
                        "finalStatus":   "SUCCESS",
                    },
                )
        mock_complete.assert_called_once()

    def test_complete_missing_transaction_id_returns_422(self):
        with TestClient(_app()) as client:
            resp = client.post(
                "/api/v1/idempotency/complete",
                json={"finalStatus": "SUCCESS"},
            )
        assert resp.status_code == 422

    def test_complete_with_payload(self):
        with patch("app.router.service.complete", return_value=None):
            with TestClient(_app()) as client:
                resp = client.post(
                    "/api/v1/idempotency/complete",
                    json={
                        "transactionId":   "txn-001",
                        "finalStatus":     "SUCCESS",
                        "responsePayload": '{"txn_id":"txn-001"}',
                    },
                )
        assert resp.status_code == 204


class TestDebugEndpoint:

    def test_debug_records_returns_200(self, dynamo_table):
        dynamo_table.scan.return_value = {
            "Items": [{"idempotencyKey": "idem-001"}]
        }
        with TestClient(_app()) as client:
            resp = client.get("/api/v1/idempotency/debug/records")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)