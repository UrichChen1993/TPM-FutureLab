"""Create the MVP table when CloudFormation is not being used.

Usage: python -m scripts.create_dynamodb_table
"""
import argparse

import boto3
from botocore.exceptions import ClientError

from config import load_settings


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Create the HomeWellness DynamoDB table.")
    parser.add_argument("--table-name", default=settings.dynamodb_table)
    parser.add_argument("--region", default=settings.aws_region)
    return parser.parse_args()


def ensure_table(client, table_name: str) -> bool:
    """Create the table if missing and wait until it can accept traffic."""
    try:
        client.describe_table(TableName=table_name)
        created = False
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        created = True
        client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            SSESpecification={"Enabled": True},
        )

    client.get_waiter("table_exists").wait(TableName=table_name)
    return created


def main() -> None:
    args = parse_args()
    client = boto3.client("dynamodb", region_name=args.region)
    created = ensure_table(client, args.table_name)
    action = "created" if created else "already exists"
    print(f"table {args.table_name} {action} and is ready in {args.region}")


if __name__ == "__main__":
    main()
