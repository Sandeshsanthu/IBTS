import time
import logging
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)


def _get_resource():
    return boto3.resource(
        "dynamodb",
        region_name=settings.AWS_DEFAULT_REGION,
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _get_table():
    return _get_resource().Table(settings.DYNAMODB_TABLE_NAME)


def ensure_table_exists():
    """Idempotent bootstrap — safe to call on every startup."""
    client = boto3.client(
        "dynamodb",
        region_name=settings.AWS_DEFAULT_REGION,
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    try:
        client.create_table(
            TableName=settings.DYNAMODB_TABLE_NAME,
            AttributeDefinitions=[
                {"AttributeName": "idempotencyKey", "AttributeType": "S"}
            ],
            KeySchema=[
                {"AttributeName": "idempotencyKey", "KeyType": "HASH"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        logger.info("Table '%s' created.", settings.DYNAMODB_TABLE_NAME)
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=settings.DYNAMODB_TABLE_NAME)
        client.update_time_to_live(
            TableName=settings.DYNAMODB_TABLE_NAME,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "expiresAt"},
        )
        logger.info("TTL enabled on '%s'.", settings.DYNAMODB_TABLE_NAME)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            logger.info("Table '%s' already exists — skipping.", settings.DYNAMODB_TABLE_NAME)
        else:
            logger.error("Failed to bootstrap table: %s", e)
            raise


def insert_if_absent(record: dict) -> bool:
    """Atomic conditional write. Returns True if new, False if duplicate."""
    table = _get_table()
    expires_at = int(time.time()) + (settings.IDEMPOTENCY_TTL_HOURS * 3600)
    record["expiresAt"] = expires_at
    try:
        table.put_item(
            Item=record,
            ConditionExpression="attribute_not_exists(idempotencyKey)",
        )
        logger.info("Insert success key=%s", record["idempotencyKey"])
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("Duplicate detected key=%s", record["idempotencyKey"])
            return False
        logger.error("Insert error: %s", e)
        raise


def find_by_key(idempotency_key: str) -> dict | None:
    """Strongly consistent point read."""
    table = _get_table()
    response = table.get_item(
        Key={"idempotencyKey": idempotency_key},
        ConsistentRead=True,
    )
    return response.get("Item")


def complete(idempotency_key: str, final_status: str, response_payload: str | None):
    """Conditional update — only transitions from PROCESSING."""
    table = _get_table()
    try:
        table.update_item(
            Key={"idempotencyKey": idempotency_key},
            UpdateExpression="SET #st = :status, responsePayload = :payload, updatedAt = :ts",
            ConditionExpression=Attr("status").eq("PROCESSING"),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": final_status,
                ":payload": response_payload or "",
                ":ts": int(time.time() * 1000),
            },
        )
        logger.info("Complete success key=%s status=%s", idempotency_key, final_status)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning("Complete skipped — not PROCESSING key=%s", idempotency_key)
        else:
            logger.error("Complete error: %s", e)
            raise


def scan_all() -> list:
    return _get_table().scan().get("Items", [])