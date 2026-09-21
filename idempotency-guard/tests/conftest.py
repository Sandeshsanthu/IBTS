import sys
from unittest.mock import MagicMock, patch
import pytest

# ── mock shared BEFORE any app import ─────────────────────────────────────
def _m():
    m = MagicMock()
    m.labels.return_value = m
    return m

_registry = MagicMock()
for _attr in ["IDEMPOTENCY_CHECKS_TOTAL", "IDEMPOTENCY_STALE_PROCESSING_TOTAL"]:
    setattr(_registry, _attr, _m())

sys.modules["shared"]                    = MagicMock()
sys.modules["shared.telemetry"]          = MagicMock()
sys.modules["shared.metrics"]            = MagicMock()
sys.modules["shared.metrics.registry"]   = _registry
sys.modules["shared.metrics.middleware"] = MagicMock()
sys.modules["prometheus_fastapi_instrumentator"] = MagicMock()

# ── DynamoDB mock ──────────────────────────────────────────────────────────
_mock_table = MagicMock()
_mock_resource = MagicMock()
_mock_resource.Table.return_value = _mock_table
_mock_client  = MagicMock()
_mock_client.get_waiter.return_value = MagicMock()


def _reset_table():
    """
    Full reset between tests.
    reset_mock() clears call counts but NOT side_effect — must be done
    explicitly, otherwise a side_effect set in one test bleeds into the next.
    """
    _mock_table.reset_mock()
    _mock_table.side_effect          = None   # ← clear any raised exception
    _mock_table.get_item.reset_mock()
    _mock_table.get_item.side_effect  = None
    _mock_table.get_item.return_value = {}
    _mock_table.put_item.reset_mock()
    _mock_table.put_item.side_effect  = None
    _mock_table.put_item.return_value = {}
    _mock_table.update_item.reset_mock()
    _mock_table.update_item.side_effect  = None
    _mock_table.update_item.return_value = {}
    _mock_table.scan.reset_mock()
    _mock_table.scan.side_effect  = None
    _mock_table.scan.return_value = {"Items": []}


# ── autouse: patch boto3 + clean table state for every test ───────────────
@pytest.fixture(autouse=True)
def _patch_boto3():
    _reset_table()
    with patch("boto3.resource", return_value=_mock_resource), \
         patch("boto3.client",   return_value=_mock_client):
        yield _mock_table


@pytest.fixture
def dynamo_table():
    """Explicit handle for tests that need to customise return values."""
    return _mock_table