"""Seed the DynamoDB demo user explicitly and idempotently.

Run from the repository root after the CloudFormation stack is ready:
    python -m scripts.seed_dynamodb
"""

import argparse

import boto3

from config import load_settings
from seed_data import seed_demo_user
from storage.dynamodb_backend import DynamoDBRepository


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Seed HomeWellness demo data in DynamoDB.")
    parser.add_argument("--table-name", default=settings.dynamodb_table)
    parser.add_argument("--region", default=settings.aws_region)
    parser.add_argument("--user-id", default="user-001")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = boto3.client("dynamodb", region_name=args.region)
    response = client.describe_table(TableName=args.table_name)
    status = response["Table"]["TableStatus"]
    if status != "ACTIVE":
        raise RuntimeError(f"DynamoDB table {args.table_name!r} is {status}, not ACTIVE")

    repository = DynamoDBRepository(table_name=args.table_name, region=args.region)
    seed_demo_user(repository, user_id=args.user_id)
    print(
        f"seeded demo data for {args.user_id} in "
        f"{args.table_name} ({args.region}); rerunning is safe"
    )


if __name__ == "__main__":
    main()
