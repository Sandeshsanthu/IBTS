import pytest
from unittest.mock import MagicMock, patch


class TestBankFromVpa:
    """_bank_from_vpa() VPA handle → bank code mapping."""

    @pytest.mark.parametrize("vpa,expected_bank", [
        ("alice@oksbi",      "SBI"),
        ("alice@sbi",        "SBI"),
        ("bob@okhdfcbank",   "HDFC"),
        ("bob@hdfc",         "HDFC"),
        ("charlie@okicici",  "ICICI"),
        ("dave@ybl",         "YESBANK"),
        ("eve@okaxis",       "AXIS"),
        ("eve@axisbank",     "AXIS"),
        ("frank@paytm",      "PAYTM"),
        ("frank@apl",        "PAYTM"),
        ("unknown@xyz",      "XYZ"),
        ("fallback@newbank", "NEWBANK"),
    ])
    def test_known_handles_map_correctly(self, vpa, expected_bank):
        from app.payment_metrics import _bank_from_vpa
        assert _bank_from_vpa(vpa) == expected_bank

    def test_no_at_sign_returns_unknown(self):
        from app.payment_metrics import _bank_from_vpa
        assert _bank_from_vpa("invalidsbi") == "UNKNOWN"

    def test_empty_string_returns_unknown(self):
        from app.payment_metrics import _bank_from_vpa
        assert _bank_from_vpa("") == "UNKNOWN"

    def test_uppercase_vpa_normalised(self):
        from app.payment_metrics import _bank_from_vpa
        # handle lookup is lowercase — uppercase suffix should still work
        result = _bank_from_vpa("alice@OKSBI")
        assert result == "SBI"


class TestRecordIdempotency:

    def test_new_increments_counter(self):
        import app.payment_metrics as pm
        pm.IDEMPOTENCY_CHECKS_TOTAL.reset_mock()
        from app.payment_metrics import record_idempotency
        record_idempotency("payment-switch", "NEW")
        pm.IDEMPOTENCY_CHECKS_TOTAL.labels.assert_called_with(
            service="payment-switch", idem_result="NEW"
        )
        pm.IDEMPOTENCY_CHECKS_TOTAL.labels.return_value.inc.assert_called_once()

    def test_cached_increments_counter(self):
        import app.payment_metrics as pm
        pm.IDEMPOTENCY_CHECKS_TOTAL.reset_mock()
        from app.payment_metrics import record_idempotency
        record_idempotency("payment-switch", "CACHED")
        pm.IDEMPOTENCY_CHECKS_TOTAL.labels.assert_called_with(
            service="payment-switch", idem_result="CACHED"
        )


class TestRecordPayment:

    def test_success_increments_initiated_total(self):
        import app.payment_metrics as pm
        pm.PAYMENT_INITIATED_TOTAL.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            status="SUCCESS",
            idem_result="NEW",
            duration_s=0.5,
        )
        pm.PAYMENT_INITIATED_TOTAL.labels.assert_called_with(
            payer_bank="SBI",
            payee_bank="HDFC",
            status="SUCCESS",
            idem_result="NEW",
        )

    def test_success_increments_total_amount_paise(self):
        import app.payment_metrics as pm
        pm.PAYMENT_TOTAL_AMOUNT_PAISE.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=50000,
            status="SUCCESS",
            idem_result="NEW",
        )
        pm.PAYMENT_TOTAL_AMOUNT_PAISE.labels.return_value.inc.assert_called_with(50000)

    def test_failed_does_not_increment_total_amount(self):
        import app.payment_metrics as pm
        pm.PAYMENT_TOTAL_AMOUNT_PAISE.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=50000,
            status="FAILED",
            idem_result="NEW",
            error_kind="bank_error",
        )
        pm.PAYMENT_TOTAL_AMOUNT_PAISE.labels.return_value.inc.assert_not_called()

    def test_failed_with_error_kind_increments_errors_total(self):
        import app.payment_metrics as pm
        pm.PAYMENT_ERRORS_TOTAL.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            status="FAILED",
            idem_result="NEW",
            error_kind="bank_error",
        )
        pm.PAYMENT_ERRORS_TOTAL.labels.assert_called_with(
            payee_bank="HDFC",
            error_kind="bank_error",
        )

    def test_success_does_not_increment_errors_total(self):
        import app.payment_metrics as pm
        pm.PAYMENT_ERRORS_TOTAL.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            status="SUCCESS",
            idem_result="NEW",
        )
        pm.PAYMENT_ERRORS_TOTAL.labels.return_value.inc.assert_not_called()

    def test_duration_records_latency(self):
        import app.payment_metrics as pm
        pm.PAYMENT_E2E_LATENCY_SECONDS.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            status="SUCCESS",
            idem_result="NEW",
            duration_s=1.2,
        )
        pm.PAYMENT_E2E_LATENCY_SECONDS.labels.return_value.observe.assert_called_once()

    def test_zero_duration_skips_latency(self):
        import app.payment_metrics as pm
        pm.PAYMENT_E2E_LATENCY_SECONDS.reset_mock()
        from app.payment_metrics import record_payment
        record_payment(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            status="SUCCESS",
            idem_result="NEW",
            duration_s=0.0,
        )
        pm.PAYMENT_E2E_LATENCY_SECONDS.labels.return_value.observe.assert_not_called()


class TestPaymentTimer:

    @pytest.mark.asyncio
    async def test_success_context_records_success(self):
        import app.payment_metrics as pm
        pm.PAYMENT_INITIATED_TOTAL.reset_mock()
        from app.payment_metrics import payment_timer

        async with payment_timer(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            idem_result="NEW",
        ) as ctx:
            ctx.status     = "SUCCESS"
            ctx.error_kind = None

        pm.PAYMENT_INITIATED_TOTAL.labels.assert_called_with(
            payer_bank="SBI", payee_bank="HDFC",
            status="SUCCESS", idem_result="NEW",
        )

    @pytest.mark.asyncio
    async def test_exception_sets_failed_and_reraises(self):
        from app.payment_metrics import payment_timer

        with pytest.raises(ValueError, match="boom"):
            async with payment_timer(
                payer_vpa="alice@oksbi",
                payee_vpa="bob@okhdfcbank",
                amount_paise=10000,
                idem_result="NEW",
            ) as ctx:
                raise ValueError("boom")

        assert ctx.status == "FAILED"

    @pytest.mark.asyncio
    async def test_default_status_is_failed_if_not_set(self):
        import app.payment_metrics as pm
        pm.PAYMENT_INITIATED_TOTAL.reset_mock()
        from app.payment_metrics import payment_timer

        async with payment_timer(
            payer_vpa="alice@oksbi",
            payee_vpa="bob@okhdfcbank",
            amount_paise=10000,
            idem_result="NEW",
        ) as ctx:
            pass   # never set ctx.status

        pm.PAYMENT_INITIATED_TOTAL.labels.assert_called_with(
            payer_bank="SBI", payee_bank="HDFC",
            status="FAILED", idem_result="NEW",
        )


class TestRecordBankRequest:

    def test_success_call_increments_requests_total(self):
        import app.payment_metrics as pm
        pm.BANK_REQUESTS_TOTAL.reset_mock()
        from app.payment_metrics import record_bank_request
        record_bank_request("SBI", "primary", "200", 0.3)
        pm.BANK_REQUESTS_TOTAL.labels.assert_called_with(
            bank_code="SBI", endpoint_type="primary", http_code="200"
        )

    def test_failed_call_increments_failures_total(self):
        import app.payment_metrics as pm
        pm.BANK_FAILURES_TOTAL.reset_mock()
        from app.payment_metrics import record_bank_request
        record_bank_request("SBI", "primary", "timeout", 3.0,
                            failed=True, fail_type="timeout")
        pm.BANK_FAILURES_TOTAL.labels.assert_called_with(
            bank_code="SBI", failure_type="timeout"
        )

    def test_fallback_used_increments_fallback_counter(self):
        import app.payment_metrics as pm
        pm.BANK_FALLBACK_USED_TOTAL.reset_mock()
        from app.payment_metrics import record_bank_request
        record_bank_request("SBI", "fallback", "200", 0.5, fallback_used=True)
        pm.BANK_FALLBACK_USED_TOTAL.labels.assert_called_with(bank_code="SBI")

    def test_no_failure_does_not_increment_failures(self):
        import app.payment_metrics as pm
        pm.BANK_FAILURES_TOTAL.reset_mock()
        from app.payment_metrics import record_bank_request
        record_bank_request("SBI", "primary", "200", 0.3, failed=False)
        pm.BANK_FAILURES_TOTAL.labels.return_value.inc.assert_not_called()