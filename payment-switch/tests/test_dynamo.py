import pytest
from unittest.mock import MagicMock, patch


class TestWriteTxn:

    def test_write_txn_calls_put_item(self, tracked_table, sample_txn_record):
        from app import dynamo
        dynamo.write_txn(sample_txn_record)
        tracked_table.put_item.assert_called_once()

    def test_write_txn_sets_created_at(self, tracked_table, sample_txn_record):
        from app import dynamo
        dynamo.write_txn(sample_txn_record)
        assert sample_txn_record.created_at != ""

    def test_write_txn_sets_updated_at(self, tracked_table, sample_txn_record):
        from app import dynamo
        dynamo.write_txn(sample_txn_record)
        assert sample_txn_record.updated_at != ""

    def test_write_txn_created_equals_updated_at_on_write(self, tracked_table, sample_txn_record):
        from app import dynamo
        dynamo.write_txn(sample_txn_record)
        assert sample_txn_record.created_at == sample_txn_record.updated_at


class TestGetTxn:

    def test_returns_item_when_found(self, tracked_table):
        from app import dynamo
        tracked_table.get_item.return_value = {
            "Item": {"txn_id": "txn-001", "state": "SUCCESS"}
        }
        result = dynamo.get_txn("txn-001")
        assert result["txn_id"] == "txn-001"
        tracked_table.get_item.assert_called_with(Key={"txn_id": "txn-001"})

    def test_returns_none_when_not_found(self, tracked_table):
        from app import dynamo
        tracked_table.get_item.return_value = {}
        result = dynamo.get_txn("txn-999")
        assert result is None


class TestGetTxnByIdempotencyKey:

    def test_returns_first_matching_item(self, tracked_table):
        from app import dynamo
        tracked_table.scan.return_value = {
            "Items": [{"txn_id": "txn-001", "idempotency_key": "idem-001"}]
        }
        result = dynamo.get_txn_by_idempotency_key("idem-001")
        assert result["txn_id"] == "txn-001"

    def test_returns_none_when_no_match(self, tracked_table):
        from app import dynamo
        tracked_table.scan.return_value = {"Items": []}
        result = dynamo.get_txn_by_idempotency_key("idem-not-found")
        assert result is None


class TestGetTxnByBankRrn:

    def test_returns_first_matching_item(self, tracked_table):
        from app import dynamo
        tracked_table.scan.return_value = {
            "Items": [{"txn_id": "txn-001", "bank_rrn": "SBI-RRN-001"}]
        }
        result = dynamo.get_txn_by_bank_rrn("SBI-RRN-001")
        assert result["txn_id"] == "txn-001"

    def test_returns_none_when_no_match(self, tracked_table):
        from app import dynamo
        tracked_table.scan.return_value = {"Items": []}
        result = dynamo.get_txn_by_bank_rrn("RRN-not-found")
        assert result is None


class TestUpdateState:

    def test_update_state_calls_update_item(self, tracked_table):
        from app import dynamo
        from app.models import TxnState
        dynamo.update_state("txn-001", TxnState.SUCCESS)
        tracked_table.update_item.assert_called_once()

    def test_update_state_with_bank_rrn(self, tracked_table):
        from app import dynamo
        from app.models import TxnState
        dynamo.update_state("txn-001", TxnState.SUCCESS, bank_rrn="SBI-RRN-001")
        call_kwargs = tracked_table.update_item.call_args[1]
        assert ":r" in call_kwargs["ExpressionAttributeValues"]

    def test_update_state_with_error(self, tracked_table):
        from app import dynamo
        from app.models import TxnState
        dynamo.update_state("txn-001", TxnState.FAILED, error="bank timeout")
        call_kwargs = tracked_table.update_item.call_args[1]
        assert ":err" in call_kwargs["ExpressionAttributeValues"]

    def test_update_state_sets_correct_key(self, tracked_table):
        from app import dynamo
        from app.models import TxnState
        dynamo.update_state("txn-abc", TxnState.PROCESSING)
        call_kwargs = tracked_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"txn_id": "txn-abc"}