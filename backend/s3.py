"""
S3 presigned URL generation for original PDF downloads.

Provides a lazy-initialized boto3 client and a function to generate
time-limited presigned download URLs from S3 object keys.
"""

import os

from backend.config import get
from backend.logging_config import get_logger

logger = get_logger(__name__)

_s3_client = None


def _get_s3_client():
    """Lazy-initialize and return the boto3 S3 client singleton."""
    global _s3_client
    if _s3_client is None:
        import boto3

        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", get("ingestion", "files", "s3_default_region")),
        )
    return _s3_client


def generate_presigned_url(s3_key: str, bucket: str | None = None) -> str:
    """Generate a temporary presigned URL for downloading an S3 object.

    Args:
        s3_key: The S3 object key.
        bucket: S3 bucket name. Defaults to S3_BUCKET env var or config default.

    Returns:
        A presigned URL string valid for the configured expiry period.

    Raises:
        ValueError: If s3_key is empty or None.
    """
    if not s3_key:
        raise ValueError("s3_key must be a non-empty string")

    if bucket is None:
        bucket = os.environ.get("S3_BUCKET", get("ingestion", "files", "s3_default_bucket"))

    expiry = get("s3", "presigned_url_expiry_seconds")
    client = _get_s3_client()

    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expiry,
    )
    logger.debug(f"Generated presigned URL for s3://{bucket}/{s3_key}")
    return url
