import pytest


class TestVpaResolver:

    @pytest.mark.parametrize("vpa,expected", [
        ("alice@sbi",        "SBI"),
        ("alice@oksbi",      "SBI"),
        ("bob@icici",        "ICICI"),
        ("bob@okicici",      "ICICI"),
        ("charlie@hdfcbank", "HDFC"),
        ("charlie@okhdfcbank","HDFC"),
        ("dave@axisbank",    "AXIS"),
        ("dave@okaxis",      "AXIS"),
        ("eve@ybl",          "YESBANK"),
        ("frank@ibl",        "INDUSIND"),
        ("grace@paytm",      "PAYTM"),
        ("harry@kotak",      "KOTAK"),
        ("harry@kmbl",       "KOTAK"),
        ("ivan@pnb",         "PNB"),
        ("jack@boi",         "BOI"),
        ("kate@cnrb",        "CANARA"),
        ("liz@federal",      "FEDERAL"),
        ("liz@fbl",          "FEDERAL"),
        ("test@ibts",        "YESBANK"),
        ("upi@upi",          "NPCI"),
    ])
    def test_known_handles_map_correctly(self, vpa, expected):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa(vpa) == expected

    def test_unknown_handle_returns_none(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa("user@unknownbank") is None

    def test_no_at_sign_returns_none(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa("invalidsbi") is None

    def test_empty_string_returns_none(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa("") is None

    def test_none_returns_none(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa(None) is None

    def test_handle_case_insensitive(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        assert resolve_vpa("alice@SBI") == "SBI"
        assert resolve_vpa("alice@OKSBI") == "SBI"

    def test_multiple_at_signs_uses_last_part(self):
        from app.resolvers.vpa_resolver import resolve_vpa
        # split("@", 1) — takes everything after first @
        result = resolve_vpa("alice@extra@sbi")
        # "extra@sbi" is the handle — not in map, returns None
        assert result is None


class TestIfscResolver:

    @pytest.mark.parametrize("ifsc,expected", [
        ("SBIN0001234", "SBI"),
        ("ICIC0005678", "ICICI"),
        ("HDFC0009012", "HDFC"),
        ("UTIB0003456", "AXIS"),
        ("YESB0007890", "YESBANK"),
        ("INDB0001111", "INDUSIND"),
        ("PYTM0002222", "PAYTM"),
        ("KKBK0003333", "KOTAK"),
        ("PUNB0004444", "PNB"),
        ("BKID0005555", "BOI"),
        ("CNRB0006666", "CANARA"),
        ("FDRL0007777", "FEDERAL"),
        ("BARB0008888", "BOB"),
        ("UBIN0009999", "UBI"),
        ("IOBA0001010", "IOB"),
    ])
    def test_known_prefixes_map_correctly(self, ifsc, expected):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc(ifsc) == expected

    def test_unknown_prefix_returns_none(self):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc("ZZZZ0001234") is None

    def test_too_short_returns_none(self):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc("SBI") is None

    def test_empty_string_returns_none(self):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc("") is None

    def test_none_returns_none(self):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc(None) is None

    def test_prefix_case_insensitive(self):
        from app.resolvers.ifsc_resolver import resolve_ifsc
        assert resolve_ifsc("sbin0001234") == "SBI"
        assert resolve_ifsc("Sbin0001234") == "SBI"