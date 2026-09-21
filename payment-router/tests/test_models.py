import pytest
from pydantic import ValidationError


class TestRouteRequest:

    def test_vpa_only_valid(self):
        from app.models import RouteRequest
        req = RouteRequest(vpa="alice@sbi")
        assert req.vpa == "alice@sbi"
        assert req.ifsc is None

    def test_ifsc_only_valid(self):
        from app.models import RouteRequest
        req = RouteRequest(ifsc="SBIN0001234")
        assert req.ifsc == "SBIN0001234"
        assert req.vpa is None

    def test_both_provided_raises(self):
        from app.models import RouteRequest
        with pytest.raises(ValidationError):
            RouteRequest(vpa="alice@sbi", ifsc="SBIN0001234")

    def test_neither_provided_raises(self):
        from app.models import RouteRequest
        with pytest.raises(ValidationError):
            RouteRequest()

    def test_empty_vpa_with_no_ifsc_raises(self):
        from app.models import RouteRequest
        with pytest.raises(ValidationError):
            RouteRequest(vpa="   ")

    def test_whitespace_vpa_treated_as_empty(self):
        from app.models import RouteRequest
        with pytest.raises(ValidationError):
            RouteRequest(vpa="  ", ifsc=None)


class TestRouteResponse:

    def test_valid_route_response(self):
        from app.models import RouteResponse
        resp = RouteResponse(
            bankCode         = "SBI",
            bankName         = "State Bank of India",
            primaryEndpoint  = "https://upi.sbi.co.in/txn",
            fallbackEndpoint = "https://upi2.sbi.co.in/txn",
            resolvedFrom     = "DB",
            ttlRemainingMs   = 300000,
        )
        assert resp.bankCode      == "SBI"
        assert resp.resolvedFrom  == "DB"
        assert resp.ttlRemainingMs == 300000

    def test_cache_resolved_from(self):
        from app.models import RouteResponse
        resp = RouteResponse(
            bankCode="HDFC", bankName="HDFC Bank",
            primaryEndpoint="https://p", fallbackEndpoint="https://f",
            resolvedFrom="CACHE", ttlRemainingMs=120000,
        )
        assert resp.resolvedFrom == "CACHE"