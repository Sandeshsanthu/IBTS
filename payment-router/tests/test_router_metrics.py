import pytest


class TestRecordResolution:

    def test_success_increments_resolution_total(self):
        import app.router_metrics as rm
        rm.VPA_RESOLUTION_TOTAL.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("SBI", "DB", True, 0.05)
        rm.VPA_RESOLUTION_TOTAL.labels.assert_called_with(
            bank_code="SBI", resolved_from="DB", success="true"
        )
        rm.VPA_RESOLUTION_TOTAL.labels.return_value.inc.assert_called_once()

    def test_latency_observed(self):
        import app.router_metrics as rm
        rm.VPA_RESOLUTION_LATENCY_SECONDS.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("HDFC", "CACHE", True, 0.01)
        rm.VPA_RESOLUTION_LATENCY_SECONDS.labels.return_value.observe.assert_called_once()

    def test_unknown_handle_increments_vpa_unknown(self):
        import app.router_metrics as rm
        rm.VPA_UNKNOWN_TOTAL.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("UNKNOWN", "DB", False, 0.02, handle_suffix="xyz")
        rm.VPA_UNKNOWN_TOTAL.labels.assert_called_with(handle_suffix="xyz")

    def test_success_no_unknown_increment(self):
        import app.router_metrics as rm
        rm.VPA_UNKNOWN_TOTAL.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("SBI", "DB", True, 0.05, handle_suffix="sbi")
        rm.VPA_UNKNOWN_TOTAL.labels.return_value.inc.assert_not_called()

    def test_cache_hit_updates_hit_ratio(self):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_HIT_RATIO.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("SBI", "CACHE", True, 0.001)
        rm.ROUTE_CACHE_HIT_RATIO.labels.return_value.set.assert_called()

    def test_db_miss_updates_hit_ratio(self):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_HIT_RATIO.reset_mock()
        from app.router_metrics import record_resolution
        record_resolution("SBI", "DB", True, 0.05)
        rm.ROUTE_CACHE_HIT_RATIO.labels.return_value.set.assert_called()


class TestRecordCacheOp:

    def test_hit_increments_cache_ops(self):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_OPS_TOTAL.reset_mock()
        from app.router_metrics import record_cache_op
        record_cache_op("SBI", "hit")
        rm.ROUTE_CACHE_OPS_TOTAL.labels.assert_called_with(
            bank_code="SBI", operation="hit"
        )

    def test_miss_increments_cache_ops(self):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_OPS_TOTAL.reset_mock()
        from app.router_metrics import record_cache_op
        record_cache_op("HDFC", "miss")
        rm.ROUTE_CACHE_OPS_TOTAL.labels.assert_called_with(
            bank_code="HDFC", operation="miss"
        )

    def test_set_increments_cache_ops(self):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_OPS_TOTAL.reset_mock()
        from app.router_metrics import record_cache_op
        record_cache_op("ICICI", "set")
        rm.ROUTE_CACHE_OPS_TOTAL.labels.assert_called_with(
            bank_code="ICICI", operation="set"
        )

    @pytest.mark.parametrize("op", ["hit", "miss"])
    def test_hit_and_miss_update_ratio(self, op):
        import app.router_metrics as rm
        rm.ROUTE_CACHE_HIT_RATIO.reset_mock()
        from app.router_metrics import record_cache_op
        record_cache_op("SBI", op)
        rm.ROUTE_CACHE_HIT_RATIO.labels.return_value.set.assert_called()