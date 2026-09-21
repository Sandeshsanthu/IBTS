import pytest
from pydantic import ValidationError


class TestAdapterRequest:
    """Tests for AdapterRequest model validation."""

    def _valid(self):
        return {
            "transactionId":    "txn-001",
            "bankCode":         "SBI",
            "primaryEndpoint":  "https://api.sbi.com/upi/pay",
            "fallbackEndpoint": "https://fallback.sbi.com/upi/pay",
            "amount":           100.00,
            "payerVpa":         "alice@hdfc",
            "payeeVpa":         "bob@sbi",
        }

    def test_valid_request_parses(self):
        from app.models import AdapterRequest
        req = AdapterRequest(**self._valid())
        assert req.transactionId == "txn-001"
        assert req.bankCode      == "SBI"
        assert req.currency      == "INR"   # default

    def test_missing_transaction_id_raises(self):
        from app.models import AdapterRequest
        data = self._valid()
        del data["transactionId"]
        with pytest.raises(ValidationError):
            AdapterRequest(**data)

    def test_missing_bank_code_raises(self):
        from app.models import AdapterRequest
        data = self._valid()
        del data["bankCode"]
        with pytest.raises(ValidationError):
            AdapterRequest(**data)

    def test_missing_amount_raises(self):
        from app.models import AdapterRequest
        data = self._valid()
        del data["amount"]
        with pytest.raises(ValidationError):
            AdapterRequest(**data)

    def test_currency_defaults_to_inr(self):
        from app.models import AdapterRequest
        req = AdapterRequest(**self._valid())
        assert req.currency == "INR"

    def test_remarks_defaults_to_empty_string(self):
        from app.models import AdapterRequest
        req = AdapterRequest(**self._valid())
        assert req.remarks == ""


class TestAdapterResponse:
    """Tests for AdapterResponse model validation."""

    def _valid(self):
        return {
            "transactionId":   "txn-001",
            "bankCode":        "SBI",
            "status":          "SUCCESS",
            "resolvedVia":     "PRIMARY",
            "attempts":        1,
            "responseTimeMs":  320,
        }

    def test_valid_success_response(self):
        from app.models import AdapterResponse
        resp = AdapterResponse(**self._valid())
        assert resp.status      == "SUCCESS"
        assert resp.resolvedVia == "PRIMARY"

    def test_valid_failed_response(self):
        from app.models import AdapterResponse
        data = self._valid()
        data["status"]      = "FAILED"
        data["resolvedVia"] = "NONE"
        resp = AdapterResponse(**data)
        assert resp.status == "FAILED"

    def test_invalid_status_raises(self):
        from app.models import AdapterResponse
        data = self._valid()
        data["status"] = "UNKNOWN"       # not in Literal["SUCCESS","FAILED"]
        with pytest.raises(ValidationError):
            AdapterResponse(**data)

    def test_invalid_resolved_via_raises(self):
        from app.models import AdapterResponse
        data = self._valid()
        data["resolvedVia"] = "INVALID"
        with pytest.raises(ValidationError):
            AdapterResponse(**data)

    @pytest.mark.parametrize("status",       ["SUCCESS", "FAILED"])
    @pytest.mark.parametrize("resolved_via", ["PRIMARY", "FALLBACK", "NONE"])
    def test_all_valid_combinations(self, status, resolved_via):
        from app.models import AdapterResponse
        data = self._valid()
        data["status"]      = status
        data["resolvedVia"] = resolved_via
        resp = AdapterResponse(**data)
        assert resp.status      == status
        assert resp.resolvedVia == resolved_via