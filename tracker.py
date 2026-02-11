import time

import boto3

from config import AWS_REGION, DYNAMODB_TABLE

_dynamo_table = None


def _get_dynamo_table():
    global _dynamo_table
    if _dynamo_table is not None:
        return _dynamo_table

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

    client = boto3.client("dynamodb", region_name=AWS_REGION)
    existing = [t for t in client.list_tables()["TableNames"] if t == DYNAMODB_TABLE]
    if not existing:
        print(f"  Creating DynamoDB table '{DYNAMODB_TABLE}'...")
        client.create_table(
            TableName=DYNAMODB_TABLE,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMODB_TABLE)
        print(f"  Table '{DYNAMODB_TABLE}' created.")

    _dynamo_table = dynamodb.Table(DYNAMODB_TABLE)
    return _dynamo_table


def load_seen_jobs():
    table = _get_dynamo_table()
    seen = []
    response = table.scan(ProjectionExpression="job_id")
    seen.extend(item["job_id"] for item in response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ProjectionExpression="job_id",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        seen.extend(item["job_id"] for item in response.get("Items", []))
    return seen


def filter_new_jobs(jobs, seen_jobs):
    seen_set = set(seen_jobs)
    return [job for job in jobs if job["job_id"] not in seen_set]


def mark_jobs_seen(new_jobs, seen_jobs):
    table = _get_dynamo_table()
    ts = int(time.time())
    with table.batch_writer() as batch:
        for job in new_jobs:
            batch.put_item(Item={"job_id": job["job_id"], "seen_at": ts})
    seen_jobs.extend(job["job_id"] for job in new_jobs)
    return seen_jobs
