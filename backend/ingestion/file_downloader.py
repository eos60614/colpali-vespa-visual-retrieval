"""
File download from S3 and URLs for indexing.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiohttp

from backend.ingestion.exceptions import DownloadError
from backend.ingestion.file_detector import DetectedFile


class DownloadStrategy(Enum):
    """Strategy for downloading files."""

    PROCORE_URL = "procore_url"  # Use signed URL from database
    DIRECT_S3 = "direct_s3"  # Use boto3 with AWS credentials


@dataclass
class DownloadResult:
    """Result of a file download operation."""

    s3_key: str
    success: bool
    local_path: Optional[Path] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    status: str = "pending"  # pending, success, failed, skipped


class FileDownloader:
    """Download files from S3/URLs for indexing."""

    # Supported file types for visual retrieval
    SUPPORTED_TYPES = {"pdf", "jpg", "jpeg", "png", "gif", "tiff"}

    # Maximum file size (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024

    def __init__(
        self,
        download_dir: Path,
        strategy: DownloadStrategy = DownloadStrategy.PROCORE_URL,
        logger: Optional[logging.Logger] = None,
        aws_config: Optional[dict[str, str]] = None,
    ):
        """Initialize file downloader.

        Args:
            download_dir: Directory to store downloaded files
            strategy: Download strategy to use
            logger: Optional logger instance
            aws_config: AWS configuration for direct S3 access
        """
        self._download_dir = download_dir
        self._strategy = strategy
        self._logger = logger or logging.getLogger(__name__)
        self._aws_config = aws_config or {}

        # Create download directory
        self._download_dir.mkdir(parents=True, exist_ok=True)

        # S3 client (lazy initialized)
        self._s3_client = None

    async def download(self, file: DetectedFile) -> DownloadResult:
        """Download a single file.

        Args:
            file: DetectedFile to download

        Returns:
            DownloadResult with status and local path
        """
        # Check if should skip
        should_skip, reason = self.should_skip(file)
        if should_skip:
            return DownloadResult(
                s3_key=file.s3_key or file.url or "",
                success=False,
                error=reason,
                status="skipped",
            )

        # Determine download method
        if file.url and self._strategy == DownloadStrategy.PROCORE_URL:
            return await self.download_from_url(file)
        elif file.s3_key and self._strategy == DownloadStrategy.DIRECT_S3:
            return await self.download_from_s3(file)
        elif file.url:
            return await self.download_from_url(file)
        elif file.s3_key:
            # Fall back to S3 if URL not available
            return await self.download_from_s3(file)
        else:
            return DownloadResult(
                s3_key="",
                success=False,
                error="No URL or S3 key available",
                status="failed",
            )

    async def download_batch(
        self,
        files: list[DetectedFile],
        workers: int = 2,
    ) -> AsyncIterator[DownloadResult]:
        """Download files in parallel, yielding results.

        Args:
            files: List of files to download
            workers: Number of parallel workers

        Yields:
            DownloadResult for each file
        """
        semaphore = asyncio.Semaphore(workers)

        async def download_with_semaphore(file: DetectedFile) -> DownloadResult:
            async with semaphore:
                return await self.download(file)

        tasks = [download_with_semaphore(f) for f in files]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result

    async def download_from_url(self, file: DetectedFile) -> DownloadResult:
        """Download file from Procore signed URL.

        Args:
            file: DetectedFile with URL

        Returns:
            DownloadResult with status and local path
        """
        if not file.url:
            return DownloadResult(
                s3_key=file.s3_key,
                success=False,
                error="No URL available",
                status="failed",
            )

        # Generate local file path
        filename = file.filename or f"{file.source_table}_{file.source_record_id}"
        local_path = self._download_dir / file.source_table / filename

        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file.url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status != 200:
                        return DownloadResult(
                            s3_key=file.s3_key,
                            success=False,
                            error=f"HTTP {response.status}",
                            status="failed",
                        )

                    # Check content length
                    content_length = response.content_length
                    if content_length and content_length > self.MAX_FILE_SIZE:
                        return DownloadResult(
                            s3_key=file.s3_key,
                            success=False,
                            error=f"File too large: {content_length} bytes",
                            status="skipped",
                        )

                    # Download to file
                    with open(local_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

                    file_size = local_path.stat().st_size

                    return DownloadResult(
                        s3_key=file.s3_key,
                        success=True,
                        local_path=local_path,
                        file_size=file_size,
                        status="success",
                    )

        except asyncio.TimeoutError:
            return DownloadResult(
                s3_key=file.s3_key,
                success=False,
                error="Download timeout",
                status="failed",
            )
        except Exception as e:
            return DownloadResult(
                s3_key=file.s3_key,
                success=False,
                error=str(e),
                status="failed",
            )

    async def download_from_s3(self, file: DetectedFile) -> DownloadResult:
        """Download file directly from S3 using boto3.

        Args:
            file: DetectedFile with S3 key

        Returns:
            DownloadResult with status and local path
        """
        if not file.s3_key:
            return DownloadResult(
                s3_key="",
                success=False,
                error="No S3 key available",
                status="failed",
            )

        # Initialize S3 client if needed
        if self._s3_client is None:
            try:
                import boto3

                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=self._aws_config.get("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=self._aws_config.get("AWS_SECRET_ACCESS_KEY"),
                    region_name=self._aws_config.get("AWS_REGION", "us-east-1"),
                )
            except Exception as e:
                return DownloadResult(
                    s3_key=file.s3_key,
                    success=False,
                    error=f"Failed to initialize S3 client: {e}",
                    status="failed",
                )

        # Generate local file path
        filename = file.filename or file.s3_key.rsplit("/", 1)[-1]
        local_path = self._download_dir / file.source_table / filename

        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Extract bucket and key from S3 key
            # Assuming S3 key format: bucket/path/to/file or just path/to/file
            bucket = self._aws_config.get("S3_BUCKET", "procore-files")
            key = file.s3_key

            # Download file
            self._s3_client.download_file(bucket, key, str(local_path))

            file_size = local_path.stat().st_size

            return DownloadResult(
                s3_key=file.s3_key,
                success=True,
                local_path=local_path,
                file_size=file_size,
                status="success",
            )

        except Exception as e:
            return DownloadResult(
                s3_key=file.s3_key,
                success=False,
                error=str(e),
                status="failed",
            )

    def should_skip(self, file: DetectedFile) -> tuple[bool, str]:
        """Check if file should be skipped.

        Args:
            file: DetectedFile to check

        Returns:
            Tuple of (should_skip, reason)
        """
        # Check file size if known
        if file.file_size and file.file_size > self.MAX_FILE_SIZE:
            return True, f"File too large: {file.file_size} bytes"

        # Check file type
        file_type = file.file_type
        if file_type and file_type not in self.SUPPORTED_TYPES:
            return True, f"Unsupported file type: {file_type}"

        return False, ""

    @property
    def supported_types(self) -> set[str]:
        """File extensions supported for visual retrieval."""
        return self.SUPPORTED_TYPES

    @property
    def max_file_size(self) -> int:
        """Maximum file size in bytes."""
        return self.MAX_FILE_SIZE
