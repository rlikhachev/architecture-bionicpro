import boto3
from botocore.exceptions import ClientError

from .config import settings


class S3Store:
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=settings.s3_bucket, Key=key)
            return True
        except ClientError:
            return False

    def put_json(self, key: str, payload: str) -> None:
        self._client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=payload.encode("utf-8"),
            ContentType="application/json",
        )


s3_store = S3Store()
