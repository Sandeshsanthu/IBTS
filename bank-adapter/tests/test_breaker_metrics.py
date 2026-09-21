import pytest
from unittest.mock import MagicMock
import pybreaker


class TestMakeBreaker:
    """Tests for make_breaker() factory."""

    def test_returns_circuit_breaker_instance(self):
        from app.breaker_metrics import make_breaker
        assert isinstance(make_breaker("HDFC"), pybreaker.CircuitBreaker)

    def test_fail_max_respected(self):
        from app.breaker_metrics import make_breaker
        assert make_breaker("SBI", fail_max=5).fail_max == 5

    def test_reset_timeout_respected(self):
        from app.breaker_metrics import make_breaker
        assert make_breaker("ICICI", reset_timeout=60).reset_timeout == 60

    def test_breaker_has_ibts_listener(self):
        from app.breaker_metrics import make_breaker, IBTSBreakerListener
        breaker = make_breaker("YESBANK")
        assert IBTSBreakerListener in [type(l) for l in breaker.listeners]

    def test_default_fail_max_is_3(self):
        from app.breaker_metrics import make_breaker
        assert make_breaker("HDFC").fail_max == 3

    def test_default_reset_timeout_is_30(self):
        from app.breaker_metrics import make_breaker
        assert make_breaker("HDFC").reset_timeout == 30

    @pytest.mark.parametrize("bank", ["HDFC", "ICICI", "SBI", "YESBANK"])
    def test_all_banks_create_breaker(self, bank):
        from app.breaker_metrics import make_breaker
        breaker = make_breaker(bank)
        assert isinstance(breaker, pybreaker.CircuitBreaker)
        assert breaker.name == bank

    def test_breaker_starts_closed(self):
        from app.breaker_metrics import make_breaker
        assert make_breaker("SBI").current_state == "closed"

    def test_breaker_opens_after_fail_max(self):
        from app.breaker_metrics import make_breaker
        breaker = make_breaker("SBI", fail_max=3, reset_timeout=999)
        for _ in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        assert breaker.current_state == "open"

    def test_failures_isolated_per_bank(self):
        from app.breaker_metrics import make_breaker
        sbi  = make_breaker("SBI",  fail_max=3, reset_timeout=999)
        hdfc = make_breaker("HDFC", fail_max=3, reset_timeout=999)
        for _ in range(3):
            try:
                sbi.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        assert sbi.current_state  == "open"
        assert hdfc.current_state == "closed"


class TestIBTSBreakerListener:
    """Tests for IBTSBreakerListener state/failure/success callbacks."""

    def test_state_change_closed_to_open_calls_state_gauge(self):
        from app.breaker_metrics import IBTSBreakerListener
        import app.breaker_metrics as bm

        bm.CIRCUIT_BREAKER_STATE.reset_mock()

        listener = IBTSBreakerListener("SBI")
        old = MagicMock(); old.name = "closed"
        new = MagicMock(); new.name = "open"
        listener.state_change(MagicMock(), old, new)

        # state_change calls CIRCUIT_BREAKER_STATE.labels(bank_code=...)
        bm.CIRCUIT_BREAKER_STATE.labels.assert_any_call(bank_code="SBI")

    def test_state_change_records_transition_counter(self):
        from app.breaker_metrics import IBTSBreakerListener
        import app.breaker_metrics as bm

        bm.CIRCUIT_BREAKER_TRANSITIONS_TOTAL.reset_mock()

        listener = IBTSBreakerListener("SBI")
        old = MagicMock(); old.name = "closed"
        new = MagicMock(); new.name = "open"
        listener.state_change(MagicMock(), old, new)

        bm.CIRCUIT_BREAKER_TRANSITIONS_TOTAL.labels.assert_any_call(
            bank_code="SBI", transition="closed_to_open"
        )

    def test_failure_callback_updates_fail_count_gauge(self):
        from app.breaker_metrics import IBTSBreakerListener
        import app.breaker_metrics as bm

        bm.CIRCUIT_BREAKER_FAIL_COUNT.reset_mock()

        listener = IBTSBreakerListener("HDFC")
        cb = MagicMock(); cb.fail_counter = 2
        listener.failure(cb, Exception("fail"))

        bm.CIRCUIT_BREAKER_FAIL_COUNT.labels.assert_any_call(bank_code="HDFC")

    def test_success_callback_resets_state_gauge_to_zero(self):
        from app.breaker_metrics import IBTSBreakerListener
        import app.breaker_metrics as bm

        bm.CIRCUIT_BREAKER_STATE.reset_mock()

        listener = IBTSBreakerListener("ICICI")
        cb = MagicMock(); cb.fail_counter = 0
        listener.success(cb)

        bm.CIRCUIT_BREAKER_STATE.labels.assert_any_call(bank_code="ICICI")
        bm.CIRCUIT_BREAKER_STATE.labels.return_value.set.assert_called_with(0)

    def test_open_to_half_open_records_duration(self):
        from app.breaker_metrics import IBTSBreakerListener
        import app.breaker_metrics as bm
        import time

        bm.CIRCUIT_BREAKER_OPEN_DURATION_SECONDS.reset_mock()

        listener = IBTSBreakerListener("SBI")

        old1 = MagicMock(); old1.name = "closed"
        new1 = MagicMock(); new1.name = "open"
        listener.state_change(MagicMock(), old1, new1)

        time.sleep(0.05)

        old2 = MagicMock(); old2.name = "open"
        new2 = MagicMock(); new2.name = "half_open"
        listener.state_change(MagicMock(), old2, new2)

        bm.CIRCUIT_BREAKER_OPEN_DURATION_SECONDS.labels.assert_any_call(
            bank_code="SBI"
        )
        bm.CIRCUIT_BREAKER_OPEN_DURATION_SECONDS.labels.return_value.observe.assert_called_once()