"""
Webhook notification system for the Gateway API.

Sends callbacks to sources when:
- Ingestion jobs complete (success or failure)
- Batch operations finish
- Errors occur
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import httpx

from backend.core.logging_config import get_logger
from backend.gateway.schemas import SourceType

logger = get_logger(__name__)


@dataclass
class WebhookPayload:
    """Webhook notification payload."""
    event: str  # job.completed, job.failed, batch.completed, etc.
    job_id: str
    source_type: SourceType
    source_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "job_id": self.job_id,
            "source": {
                "type": self.source_type.value,
                "id": self.source_id,
            },
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""
    webhook_url: str
    payload: WebhookPayload
    attempt: int = 1
    max_attempts: int = 3
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    delivered_at: Optional[datetime] = None
    success: bool = False


class WebhookNotifier:
    """
    Sends webhook notifications to sources.

    Features:
    - Async delivery with retries
    - HMAC signature for security
    - Delivery logging
    """

    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._pending: List[WebhookDelivery] = []
        self._history: List[WebhookDelivery] = []
        self._running = False

    def sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for a webhook payload.

        The signature should be verified by the receiver.
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    async def send(
        self,
        webhook_url: str,
        payload: WebhookPayload,
        secret: Optional[str] = None,
    ) -> WebhookDelivery:
        """
        Send a webhook notification.

        Args:
            webhook_url: URL to send the webhook to
            payload: Webhook payload
            secret: Optional secret for HMAC signing

        Returns:
            WebhookDelivery record
        """
        delivery = WebhookDelivery(
            webhook_url=webhook_url,
            payload=payload,
        )

        payload_dict = payload.to_dict()
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": payload.event,
            "X-Webhook-Timestamp": payload.timestamp.isoformat(),
        }

        if secret:
            signature = self.sign_payload(payload_dict, secret)
            headers["X-Webhook-Signature"] = signature

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                delivery.attempt = attempt
                try:
                    response = await client.post(
                        webhook_url,
                        json=payload_dict,
                        headers=headers,
                    )
                    delivery.status_code = response.status_code
                    delivery.response_body = response.text[:1000]  # Truncate
                    delivery.delivered_at = datetime.utcnow()

                    if response.is_success:
                        delivery.success = True
                        logger.info(
                            f"Webhook delivered to {webhook_url} "
                            f"(job: {payload.job_id}, status: {response.status_code})"
                        )
                        break
                    else:
                        logger.warning(
                            f"Webhook failed to {webhook_url} "
                            f"(status: {response.status_code}, attempt: {attempt})"
                        )

                except httpx.TimeoutException:
                    delivery.error = "Timeout"
                    logger.warning(
                        f"Webhook timeout to {webhook_url} (attempt: {attempt})"
                    )

                except httpx.RequestError as e:
                    delivery.error = str(e)
                    logger.warning(
                        f"Webhook error to {webhook_url}: {e} (attempt: {attempt})"
                    )

                # Wait before retry
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)

        self._history.append(delivery)
        return delivery

    async def notify_job_completed(
        self,
        webhook_url: str,
        job_id: str,
        source_type: SourceType,
        source_id: str,
        result: Dict[str, Any],
        secret: Optional[str] = None,
    ):
        """Send notification when a job completes successfully."""
        payload = WebhookPayload(
            event="job.completed",
            job_id=job_id,
            source_type=source_type,
            source_id=source_id,
            data={
                "status": "success",
                "result": result,
            },
        )
        return await self.send(webhook_url, payload, secret)

    async def notify_job_failed(
        self,
        webhook_url: str,
        job_id: str,
        source_type: SourceType,
        source_id: str,
        error: str,
        secret: Optional[str] = None,
    ):
        """Send notification when a job fails."""
        payload = WebhookPayload(
            event="job.failed",
            job_id=job_id,
            source_type=source_type,
            source_id=source_id,
            data={
                "status": "failed",
                "error": error,
            },
        )
        return await self.send(webhook_url, payload, secret)

    async def notify_batch_completed(
        self,
        webhook_url: str,
        batch_id: str,
        source_type: SourceType,
        source_id: str,
        summary: Dict[str, Any],
        secret: Optional[str] = None,
    ):
        """Send notification when a batch operation completes."""
        payload = WebhookPayload(
            event="batch.completed",
            job_id=batch_id,
            source_type=source_type,
            source_id=source_id,
            data={
                "status": "completed",
                "summary": summary,
            },
        )
        return await self.send(webhook_url, payload, secret)

    def get_delivery_history(
        self,
        job_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WebhookDelivery]:
        """Get webhook delivery history."""
        history = self._history[-limit:]
        if job_id:
            history = [d for d in history if d.payload.job_id == job_id]
        return history


# Global webhook notifier instance
webhook_notifier = WebhookNotifier()
