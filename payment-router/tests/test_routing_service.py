import pytest
import json
from unittest.mock import MagicMock
from fastapi import HTTPException


class TestRoutingServiceCacheHit:

    def test_cache_hit_returns_route_from_redis(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value  = json.dumps(sbi_route)
        mock_redis.pttl.return_value = 250_000

        svc    = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert result.bankCode      == "SBI"
        assert result.resolvedFrom  == "CACHE"
        assert result.ttlRemainingMs == 250_000
        mock_repo.find_by_bank_code.assert_not_called()

    def test_cache_hit_does_not_write_to_dynamo(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = json.dumps(sbi_route)
        mock_redis.pttl.return_value = 200_000

        svc = RoutingService(mock_repo, mock_redis)
        svc.resolve(RouteRequest(vpa="alice@sbi"))

        mock_repo.find_by_bank_code.assert_not_called()


class TestRoutingServiceCacheMiss:

    def test_cache_miss_reads_dynamo(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc    = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert result.bankCode     == "SBI"
        assert result.resolvedFrom == "DB"
        mock_repo.find_by_bank_code.assert_called_once_with("SBI")

    def test_cache_miss_writes_to_redis(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc = RoutingService(mock_repo, mock_redis)
        svc.resolve(RouteRequest(vpa="alice@sbi"))

        mock_redis.setex.assert_called_once()

    def test_cache_miss_no_dynamo_record_raises_404(self, mock_repo, mock_redis):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = None

        svc = RoutingService(mock_repo, mock_redis)
        with pytest.raises(HTTPException) as exc_info:
            svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert exc_info.value.status_code == 404

    def test_redis_write_failure_does_not_raise(self, mock_repo, mock_redis, sbi_route):
        """Cache write failure must never block the response."""
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value  = None
        mock_redis.setex.side_effect = Exception("Redis down")
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc    = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert result.bankCode == "SBI"   # still returns despite Redis failure


class TestRoutingServiceExtractBankCode:

    def test_vpa_path_resolves_correctly(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc = RoutingService(mock_repo, mock_redis)
        svc.resolve(RouteRequest(vpa="alice@sbi"))
        mock_repo.find_by_bank_code.assert_called_with("SBI")

    def test_ifsc_path_resolves_correctly(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc = RoutingService(mock_repo, mock_redis)
        svc.resolve(RouteRequest(ifsc="SBIN0001234"))
        mock_repo.find_by_bank_code.assert_called_with("SBI")

    def test_unknown_vpa_raises_404(self, mock_repo, mock_redis):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        svc = RoutingService(mock_repo, mock_redis)
        with pytest.raises(HTTPException) as exc_info:
            svc.resolve(RouteRequest(vpa="user@unknownbank"))
        assert exc_info.value.status_code == 404

    def test_unknown_ifsc_raises_404(self, mock_repo, mock_redis):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        svc = RoutingService(mock_repo, mock_redis)
        with pytest.raises(HTTPException) as exc_info:
            svc.resolve(RouteRequest(ifsc="ZZZZ0001234"))
        assert exc_info.value.status_code == 404

    @pytest.mark.parametrize("vpa,expected_bank", [
        ("user@oksbi",      "SBI"),
        ("user@okhdfcbank", "HDFC"),
        ("user@okicici",    "ICICI"),
        ("user@ybl",        "YESBANK"),
        ("user@okaxis",     "AXIS"),
    ])
    def test_all_major_vpa_handles_resolve(
        self, vpa, expected_bank, mock_repo, mock_redis
    ):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = {
            "bankCode":         expected_bank,
            "bankName":         f"{expected_bank} Bank",
            "primaryEndpoint":  f"https://api.{expected_bank.lower()}.com",
            "fallbackEndpoint": f"https://fallback.{expected_bank.lower()}.com",
            "active": True,
        }
        svc = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa=vpa))
        assert result.bankCode == expected_bank


class TestBuildResponse:

    def test_db_source_returns_config_ttl(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest
        from app.config import settings

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc    = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert result.ttlRemainingMs == settings.cache_ttl_seconds * 1000

    def test_response_contains_all_required_fields(self, mock_repo, mock_redis, sbi_route):
        from app.services.routing_service import RoutingService
        from app.models import RouteRequest

        mock_redis.get.return_value = None
        mock_repo.find_by_bank_code.return_value = sbi_route

        svc    = RoutingService(mock_repo, mock_redis)
        result = svc.resolve(RouteRequest(vpa="alice@sbi"))

        assert result.bankCode         == "SBI"
        assert result.bankName         == "State Bank of India"
        assert result.primaryEndpoint  == "https://upi.sbi.co.in/txn"
        assert result.fallbackEndpoint == "https://upi2.sbi.co.in/txn"