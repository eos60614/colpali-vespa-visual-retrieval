"""
S3 presigned URL generation for PDF downloads.

Generates temporary presigned URLs so the browser can download
the original PDF directly from S3 without storing a second copy.
"""

import logging
from typing import Optional

from backend.config import get, get_env

logger = logging.getLogger(__name__)

_s3_client = None


def _get_s3_client():
    """Lazily initialize and return a boto3 S3 client."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    import boto3

    _s3_client = boto3.client(
        "s3",
        aws_access_key_id=get_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=get_env("AWS_SECRET_ACCESS_KEY"),
        region_name=get_env("AWS_REGION")
        or get("ingestion", "files", "s3_default_region"),
    )
    return _s3_client


def generate_presigned_url(
    s3_key: str,
    bucket: Optional[str] = None,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned S3 URL for downloading a file.

    Args:
        s3_key: The S3 object key (e.g. "company/project/drawings/file.pdf").
        bucket: S3 bucket name. Defaults to S3_BUCKET env var or ki55.toml default.
        expires_in: URL expiry in seconds (default 1 hour).

    Returns:
        A presigned HTTPS URL string.

    Raises:
        RuntimeError: If S3 is not configured or URL generation fails.
    """
    if not s3_key:
        raise ValueError("s3_key is required")

    if bucket is None:
        bucket = get_env("S3_BUCKET") or get("ingestion", "files", "s3_default_bucket")

    client = _get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expires_in,
    )
    return url
