import sys
import json
from unittest.mock import MagicMock, patch
import pytest

# ── metric mock factory ────────────────────────────────────────────────────
def _m():
    m = MagicMock()
    m.labels.return_value = m
    return m

# ── registry mock ──────────────────────────────────────────────────────────
_registry = MagicMock()
for _attr in [
    "VPA_RESOLUTION_TOTAL", "VPA_RESOLUTION_LATENCY_SECONDS",
    "ROUTE_CACHE_OPS_TOTAL", "ROUTE_CACHE_HIT_RATIO",
    "VPA_UNKNOWN_TOTAL", "REDIS_OP_LATENCY_SECONDS", "REDIS_ERRORS_TOTAL",
]:
    setattr(_registry, _attr, _m())

sys.modules["shared"]                    = MagicMock()
sys.modules["shared.telemetry"]          = MagicMock()
sys.modules["shared.metrics"]            = MagicMock()
sys.modules["shared.metrics.registry"]   = _registry
sys.modules["shared.metrics.middleware"] = MagicMock()

# ── reusable DynamoDB table mock ───────────────────────────────────────────
_mock_ddb_table = MagicMock()
_mock_ddb_table.get_item.return_value  = {}
_mock_ddb_table.scan.return_value      = {"Items": []}
_mock_ddb_table.put_item.return_value  = {}
_mock_ddb_table.wait_until_exists      = MagicMock()

_mock_ddb_resource = MagicMock()
_mock_ddb_resource.Table.return_value  = _mock_ddb_table
_mock_ddb_resource.create_table.return_value = MagicMock()
_mock_ddb_resource.meta.client.exceptions.ResourceInUseException = Exception

# ── reusable Redis mock ────────────────────────────────────────────────────
_mock_redis_instance = MagicMock()
_mock_redis_instance.get.return_value   = None
_mock_redis_instance.setex.return_value = True
_mock_redis_instance.pttl.return_value  = 300_000


# ── autouse fixture — patches boto3 AND redis.Redis for every test ─────────
@pytest.fixture(autouse=True)
def _patch_infra():
    """
    Keeps both boto3.resource and redis.Redis mocked for the lifetime of
    every test.  Without this any code that instantiates RoutingRepository()
    or redis.Redis() at test-run time (not just import-time) would try to
    connect to localstack:4566 / redis:6379.
    """
    with patch("boto3.resource",  return_value=_mock_ddb_resource), \
         patch("redis.Redis",     return_value=_mock_redis_instance):
        yield


# ── per-test fixtures ──────────────────────────────────────────────────────
@pytest.fixture
def mock_repo():
    from app.repository.routing_repository import RoutingRepository
    repo = MagicMock(spec=RoutingRepository)
    repo.find_by_bank_code.return_value = None
    repo.find_all.return_value          = []
    return repo


@pytest.fixture
def mock_redis():
    """Fresh redis mock per test — reset between tests."""
    r = MagicMock()
    r.get.return_value    = None
    r.setex.return_value  = True
    r.pttl.return_value   = 300_000
    return r


@pytest.fixture
def sbi_route():
    return {
        "bankCode":         "SBI",
        "bankName":         "State Bank of India",
        "primaryEndpoint":  "https://upi.sbi.co.in/txn",
        "fallbackEndpoint": "https://upi2.sbi.co.in/txn",
        "active":           True,
    }