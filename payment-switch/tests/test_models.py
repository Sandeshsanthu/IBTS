import pytest
from pydantic import ValidationError


class TestPaymentRequest:

    def _valid(self):
        return {
            "idempotency_key": "idem-key-001-abc",
            "payer_vpa":       "alice@oksbi",
            "payee_vpa":       "bob@okhdfcbank",
            "amount_paise":    10000,
        }

    def test_valid_request_parses(self):
        from app.models import PaymentRequest
        req = PaymentRequest(**self._valid())
        assert req.amount_paise == 10000
        assert req.payer_vpa    == "alice@oksbi"

    def test_missing_idempotency_key_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); del data["idempotency_key"]
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_short_idempotency_key_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["idempotency_key"] = "short"
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_zero_amount_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["amount_paise"] = 0
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_negative_amount_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["amount_paise"] = -100
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_exceeds_upi_limit_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["amount_paise"] = 100_000_01
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_max_upi_limit_accepted(self):
        from app.models import PaymentRequest
        data = self._valid(); data["amount_paise"] = 100_000_00
        req = PaymentRequest(**data)
        assert req.amount_paise == 100_000_00

    def test_invalid_payer_vpa_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["payer_vpa"] = "not-a-vpa"
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_invalid_payee_vpa_raises(self):
        from app.models import PaymentRequest
        data = self._valid(); data["payee_vpa"] = "no-at-sign"
        with pytest.raises(ValidationError):
            PaymentRequest(**data)

    def test_remarks_is_optional(self):
        from app.models import PaymentRequest
        req = PaymentRequest(**self._valid())
        assert req.remarks is None

    @pytest.mark.parametrize("vpa", [
        "alice@oksbi", "bob@okhdfcbank", "charlie@okicici",
        "user.name@ybl", "user-1@axisbank",
    ])
    def test_valid_vpa_formats(self, vpa):
        from app.models import PaymentRequest
        data = self._valid()
        data["payer_vpa"] = vpa
        req = PaymentRequest(**data)
        assert req.payer_vpa == vpa


class TestTxnState:

    def test_all_states_exist(self):
        from app.models import TxnState
        assert TxnState.INITIATED  == "INITIATED"
        assert TxnState.PROCESSING == "PROCESSING"
        assert TxnState.SUCCESS    == "SUCCESS"
        assert TxnState.FAILED     == "FAILED"

    def test_state_is_string_enum(self):
        from app.models import TxnState
        assert isinstance(TxnState.SUCCESS, str)


class TestTxnRecord:

    def test_txn_id_auto_generated(self):
        from app.models import TxnRecord
        r = TxnRecord(
            idempotency_key="idem-abc-001",
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=5000,
        )
        assert r.txn_id != ""
        assert len(r.txn_id) == 36    # UUID4

    def test_two_records_have_different_txn_ids(self):
        from app.models import TxnRecord
        base = dict(
            idempotency_key="idem-abc-001",
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=5000,
        )
        r1 = TxnRecord(**base)
        r2 = TxnRecord(**base)
        assert r1.txn_id != r2.txn_id

    def test_default_state_is_initiated(self):
        from app.models import TxnRecord, TxnState
        r = TxnRecord(
            idempotency_key="idem-abc-001",
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=5000,
        )
        assert r.state == TxnState.INITIATED