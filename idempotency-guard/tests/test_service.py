import pytest
from unittest.mock import MagicMock, patch
from app.models import CheckRequest, CompleteRequest


class TestCheckNew:

    def test_new_key_returns_not_duplicate(self):
        from app import service
        with patch("app.service.store.find_by_key",    return_value=None), \
             patch("app.service.store.insert_if_absent", return_value=True):
            result = service.check(
                "idem-new-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.duplicate is False
        assert result.status    == "PROCESSING"

    def test_new_key_transaction_id_matches_key(self):
        from app import service
        with patch("app.service.store.find_by_key",     return_value=None), \
             patch("app.service.store.insert_if_absent", return_value=True):
            result = service.check(
                "idem-new-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.transactionId == "idem-new-001"

    def test_new_key_response_payload_is_none(self):
        from app import service
        with patch("app.service.store.find_by_key",     return_value=None), \
             patch("app.service.store.insert_if_absent", return_value=True):
            result = service.check(
                "idem-new-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.responsePayload is None


class TestCheckDuplicate:

    def _existing(self, status="SUCCESS", payload='{"txn_id":"txn-001"}'):
        return {
            "idempotencyKey":  "idem-dup-001",
            "status":          status,
            "responsePayload": payload,
        }

    def test_duplicate_key_returns_duplicate_true(self):
        from app import service
        with patch("app.service.store.find_by_key", return_value=self._existing()):
            result = service.check(
                "idem-dup-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.duplicate is True

    def test_duplicate_returns_existing_status(self):
        from app import service
        with patch("app.service.store.find_by_key", return_value=self._existing(status="SUCCESS")):
            result = service.check(
                "idem-dup-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.status == "SUCCESS"

    def test_duplicate_returns_existing_payload(self):
        from app import service
        with patch("app.service.store.find_by_key",
                   return_value=self._existing(payload='{"txn_id":"txn-001"}')):
            result = service.check(
                "idem-dup-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.responsePayload == '{"txn_id":"txn-001"}'

    def test_duplicate_does_not_call_insert(self):
        from app import service
        mock_insert = MagicMock()
        with patch("app.service.store.find_by_key", return_value=self._existing()), \
             patch("app.service.store.insert_if_absent", mock_insert):
            service.check(
                "idem-dup-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        mock_insert.assert_not_called()


class TestCheckRaceCondition:

    def test_race_condition_returns_duplicate(self):
        """insert_if_absent returns False — another thread won the race."""
        from app import service
        existing = {
            "idempotencyKey":  "idem-race-001",
            "status":          "PROCESSING",
            "responsePayload": None,
        }
        with patch("app.service.store.find_by_key",     side_effect=[None, existing]), \
             patch("app.service.store.insert_if_absent", return_value=False):
            result = service.check(
                "idem-race-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.duplicate is True
        assert result.status    == "PROCESSING"

    def test_race_condition_returns_processing_when_record_missing(self):
        """Extremely rare: lost race but record still not visible (eventual consistency)."""
        from app import service
        with patch("app.service.store.find_by_key",     side_effect=[None, None]), \
             patch("app.service.store.insert_if_absent", return_value=False):
            result = service.check(
                "idem-race-001", "payment-switch",
                CheckRequest(transactionRefId="txn-ref-001")
            )
        assert result.duplicate is True
        assert result.status    == "PROCESSING"


class TestComplete:

    def test_complete_calls_store_complete(self):
        from app import service
        mock_complete = MagicMock()
        with patch("app.service.store.complete", mock_complete):
            service.complete(CompleteRequest(
                transactionId="txn-001",
                finalStatus="SUCCESS",
                responsePayload='{"txn_id":"txn-001"}',
            ))
        mock_complete.assert_called_once_with(
            "txn-001", "SUCCESS", '{"txn_id":"txn-001"}'
        )

    def test_complete_passes_none_payload(self):
        from app import service
        mock_complete = MagicMock()
        with patch("app.service.store.complete", mock_complete):
            service.complete(CompleteRequest(
                transactionId="txn-001",
                finalStatus="FAILED",
            ))
        mock_complete.assert_called_once_with("txn-001", "FAILED", None)