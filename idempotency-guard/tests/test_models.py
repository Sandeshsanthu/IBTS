import pytest
from pydantic import ValidationError


class TestCheckRequest:

    def test_valid_check_request(self):
        from app.models import CheckRequest
        req = CheckRequest(transactionRefId="txn-ref-001")
        assert req.transactionRefId == "txn-ref-001"

    def test_missing_transaction_ref_id_raises(self):
        from app.models import CheckRequest
        with pytest.raises(ValidationError):
            CheckRequest()


class TestCompleteRequest:

    def test_valid_complete_request(self):
        from app.models import CompleteRequest
        req = CompleteRequest(transactionId="txn-001", finalStatus="SUCCESS")
        assert req.transactionId  == "txn-001"
        assert req.finalStatus    == "SUCCESS"
        assert req.responsePayload is None

    def test_with_response_payload(self):
        from app.models import CompleteRequest
        req = CompleteRequest(
            transactionId="txn-001",
            finalStatus="SUCCESS",
            responsePayload='{"status":"SUCCESS"}'
        )
        assert req.responsePayload == '{"status":"SUCCESS"}'

    def test_missing_transaction_id_raises(self):
        from app.models import CompleteRequest
        with pytest.raises(ValidationError):
            CompleteRequest(finalStatus="SUCCESS")

    def test_missing_final_status_raises(self):
        from app.models import CompleteRequest
        with pytest.raises(ValidationError):
            CompleteRequest(transactionId="txn-001")


class TestCheckResponse:

    def test_valid_new_response(self):
        from app.models import CheckResponse
        resp = CheckResponse(
            duplicate=False,
            status="PROCESSING",
            transactionId="txn-001",
        )
        assert resp.duplicate    is False
        assert resp.status       == "PROCESSING"
        assert resp.responsePayload is None

    def test_valid_duplicate_response(self):
        from app.models import CheckResponse
        resp = CheckResponse(
            duplicate=True,
            status="SUCCESS",
            transactionId="txn-001",
            responsePayload='{"txn_id":"txn-001"}',
        )
        assert resp.duplicate        is True
        assert resp.responsePayload  == '{"txn_id":"txn-001"}'

    def test_missing_required_fields_raises(self):
        from app.models import CheckResponse
        with pytest.raises(ValidationError):
            CheckResponse(duplicate=True)