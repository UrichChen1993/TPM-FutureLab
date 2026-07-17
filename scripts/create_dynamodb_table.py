"""Run once, after AWS credentials are available, to create the MVP table.

Usage: python scripts/create_dynamodb_table.py
"""
import boto3

from config import load_settings


def main() -> None:
    settings = load_settings()
    client = boto3.client("dynamodb", region_name=settings.aws_region)
    client.create_table(
        TableName=settings.dynamodb_table,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"created table {settings.dynamodb_table} in {settings.aws_region}")


if __name__ == "__main__":
    main()
