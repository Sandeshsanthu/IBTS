import pytest


class TestRecordIdemCheck:

    def test_new_increments_checks_total(self):
        import app.idem_metrics as im
        im.IDEMPOTENCY_CHECKS_TOTAL.reset_mock()
        from app.idem_metrics import record_idem_check
        record_idem_check("NEW")
        im.IDEMPOTENCY_CHECKS_TOTAL.labels.assert_called_with(
            service="idempotency-service", idem_result="NEW"
        )
        im.IDEMPOTENCY_CHECKS_TOTAL.labels.return_value.inc.assert_called_once()

    def test_cached_increments_checks_total(self):
        import app.idem_metrics as im
        im.IDEMPOTENCY_CHECKS_TOTAL.reset_mock()
        from app.idem_metrics import record_idem_check
        record_idem_check("CACHED")
        im.IDEMPOTENCY_CHECKS_TOTAL.labels.assert_called_with(
            service="idempotency-service", idem_result="CACHED"
        )

    def test_stale_processing_increments_both_counters(self):
        import app.idem_metrics as im
        im.IDEMPOTENCY_CHECKS_TOTAL.reset_mock()
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.reset_mock()
        from app.idem_metrics import record_idem_check
        record_idem_check("STALE_PROCESSING")
        im.IDEMPOTENCY_CHECKS_TOTAL.labels.return_value.inc.assert_called_once()
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.labels.return_value.inc.assert_called_once()

    def test_new_does_not_increment_stale_counter(self):
        import app.idem_metrics as im
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.reset_mock()
        from app.idem_metrics import record_idem_check
        record_idem_check("NEW")
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.labels.return_value.inc.assert_not_called()

    def test_cached_does_not_increment_stale_counter(self):
        import app.idem_metrics as im
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.reset_mock()
        from app.idem_metrics import record_idem_check
        record_idem_check("CACHED")
        im.IDEMPOTENCY_STALE_PROCESSING_TOTAL.labels.return_value.inc.assert_not_called()