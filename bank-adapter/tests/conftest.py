import sys
from unittest.mock import MagicMock
import pytest

# ── mock entire shared package before any app import ──────────────────────
# shared.metrics.registry exports counters/histograms — mock them all
_mock_counter   = MagicMock()
_mock_counter.labels.return_value = _mock_counter

_registry_mock = MagicMock()
_registry_mock.BANK_REQUESTS_TOTAL              = _mock_counter
_registry_mock.BANK_REQUEST_LATENCY_SECONDS     = _mock_counter
_registry_mock.BANK_FAILURES_TOTAL              = _mock_counter
_registry_mock.BANK_FALLBACK_USED_TOTAL         = _mock_counter
_registry_mock.CIRCUIT_BREAKER_REJECTED_TOTAL   = _mock_counter
_registry_mock.CIRCUIT_BREAKER_STATE            = _mock_counter
_registry_mock.CIRCUIT_BREAKER_FAIL_COUNT       = _mock_counter
_registry_mock.CIRCUIT_BREAKER_TRANSITIONS_TOTAL= _mock_counter
_registry_mock.CIRCUIT_BREAKER_OPEN_DURATION_SECONDS = _mock_counter

sys.modules["shared"]                   = MagicMock()
sys.modules["shared.metrics"]           = MagicMock()
sys.modules["shared.metrics.registry"]  = _registry_mock
sys.modules["shared.metrics.middleware"]= MagicMock()
sys.modules["shared.telemetry"]         = MagicMock()


@pytest.fixture
def sample_request():
    return {
        "transactionId":   "txn-001",
        "bankCode":        "SBI",
        "primaryEndpoint": "https://api.sbi.com/upi/pay",
        "fallbackEndpoint":"https://fallback.sbi.com/upi/pay",
        "amount":          100.00,
        "currency":        "INR",
        "payerVpa":        "alice@hdfc",
        "payeeVpa":        "bob@sbi",
    }