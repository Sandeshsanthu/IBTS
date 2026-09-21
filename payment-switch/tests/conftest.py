import sys
from unittest.mock import MagicMock, patch
import pytest

# ── build a reusable mock counter/gauge/histogram ─────────────────────────
def _mock_metric():
    m = MagicMock()
    m.labels.return_value = m
    m.inc.return_value = None
    m.observe.return_value = None
    m.set.return_value = None
    return m

_m = _mock_metric

# ── mock shared.metrics.registry ──────────────────────────────────────────
_registry = MagicMock()
for _attr in [
    "PAYMENT_INITIATED_TOTAL", "PAYMENT_AMOUNT_PAISE",
    "PAYMENT_TOTAL_AMOUNT_PAISE", "PAYMENT_E2E_LATENCY_SECONDS",
    "PAYMENT_ERRORS_TOTAL", "PAYMENT_STATE_CORRUPTION_TOTAL",
    "DUPLICATE_DEBIT_TOTAL", "IDEMPOTENCY_CHECKS_TOTAL",
    "BANK_REQUESTS_TOTAL", "BANK_REQUEST_LATENCY_SECONDS",
    "BANK_FAILURES_TOTAL", "BANK_FALLBACK_USED_TOTAL",
]:
    setattr(_registry, _attr, _m())

# ── mock shared.metrics.dynamo_tracker ────────────────────────────────────
_dynamo_tracker = MagicMock()
_tracked_table  = MagicMock()
_tracked_table.put_item    = MagicMock(return_value={})
_tracked_table.get_item    = MagicMock(return_value={})
_tracked_table.update_item = MagicMock(return_value={})
_tracked_table.scan        = MagicMock(return_value={"Items": []})
_dynamo_tracker.TrackedDynamoTable.return_value = _tracked_table

sys.modules["shared"]                        = MagicMock()
sys.modules["shared.telemetry"]              = MagicMock()
sys.modules["shared.metrics"]                = MagicMock()
sys.modules["shared.metrics.registry"]       = _registry
sys.modules["shared.metrics.middleware"]     = MagicMock()
sys.modules["shared.metrics.dynamo_tracker"] = _dynamo_tracker
sys.modules["shared.metrics.ibts_metrics"]   = MagicMock()

# ── mock boto3 BEFORE dynamo.py is imported (it calls _build_table() ──────
# at module level — boto3.resource() would fail without LocalStack)
import boto3
_mock_boto3_table = MagicMock()
_mock_boto3_table.put_item    = MagicMock(return_value={})
_mock_boto3_table.get_item    = MagicMock(return_value={})
_mock_boto3_table.update_item = MagicMock(return_value={})
_mock_boto3_table.scan        = MagicMock(return_value={"Items": []})

_mock_resource = MagicMock()
_mock_resource.Table.return_value = _mock_boto3_table

with patch("boto3.resource", return_value=_mock_resource):
    import app.dynamo as _dynamo_module
    _dynamo_module._table = _tracked_table   # swap in our controllable mock


# ── fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture
def tracked_table():
    """Return the mock TrackedDynamoTable used by app.dynamo."""
    _tracked_table.reset_mock()
    _tracked_table.put_item.return_value    = {}
    _tracked_table.get_item.return_value    = {}
    _tracked_table.update_item.return_value = {}
    _tracked_table.scan.return_value        = {"Items": []}
    return _tracked_table


@pytest.fixture
def valid_payment_request():
    return {
        "idempotency_key": "idem-key-001-abc",
        "payer_vpa":       "alice@oksbi",
        "payee_vpa":       "bob@okhdfcbank",
        "amount_paise":    10000,
        "remarks":         "test payment",
    }


@pytest.fixture
def sample_txn_record():
    from app.models import TxnRecord
    return TxnRecord(
        idempotency_key = "idem-key-001-abc",
        payer_vpa       = "alice@oksbi",
        payee_vpa       = "bob@okhdfcbank",
        amount_paise    = 10000,
    )