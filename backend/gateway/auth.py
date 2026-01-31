"""
Authentication and rate limiting for the Gateway API.

Provides:
- API key validation with source-specific keys
- Rate limiting per source
- Request signing validation (optional HMAC)
"""

import hashlib
import hmac
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple
import secrets

from backend.core.config import get_env
from backend.core.logging_config import get_logger
from backend.gateway.schemas import SourceType

logger = get_logger(__name__)


@dataclass
class APIKey:
    """Represents an API key for a source."""
    key_id: str
    key_hash: str  # SHA-256 hash of the actual key
    source_type: SourceType
    source_id: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    enabled: bool = True
    rate_limit: int = 100  # Requests per minute
    scopes: list = field(default_factory=lambda: ["ingest", "query"])


class APIKeyAuth:
    """
    API key authentication manager.

    Validates API keys and manages source authentication.
    Keys are stored in memory for now; can be extended to use a database.
    """

    def __init__(self):
        self._keys: Dict[str, APIKey] = {}  # key_id -> APIKey
        self._key_lookup: Dict[str, str] = {}  # key_hash -> key_id
        self._load_default_keys()

    def _load_default_keys(self):
        """Load API keys from environment or config."""
        # Load any pre-configured keys from environment
        # Format: GATEWAY_API_KEY_<SOURCE>=<key>
        for source_type in SourceType:
            env_key = f"GATEWAY_API_KEY_{source_type.value.upper()}"
            key_value = get_env(env_key)
            if key_value:
                self.register_key(
                    source_type=source_type,
                    source_id="default",
                    name=f"Default {source_type.value} key",
                    key=key_value,
                )
                logger.info(f"Loaded API key for {source_type.value} from environment")

    def generate_key(self) -> str:
        """Generate a new random API key."""
        return f"gw_{secrets.token_urlsafe(32)}"

    def hash_key(self, key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(key.encode()).hexdigest()

    def register_key(
        self,
        source_type: SourceType,
        source_id: str,
        name: str,
        key: Optional[str] = None,
        rate_limit: int = 100,
        scopes: Optional[list] = None,
    ) -> Tuple[str, str]:
        """
        Register a new API key.

        Returns:
            Tuple of (key_id, actual_key) - actual_key is only returned once!
        """
        if key is None:
            key = self.generate_key()

        key_id = f"key_{secrets.token_hex(8)}"
        key_hash = self.hash_key(key)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            source_type=source_type,
            source_id=source_id,
            name=name,
            created_at=datetime.utcnow(),
            rate_limit=rate_limit,
            scopes=scopes or ["ingest", "query"],
        )

        self._keys[key_id] = api_key
        self._key_lookup[key_hash] = key_id

        logger.info(f"Registered API key {key_id} for {source_type.value}/{source_id}")
        return key_id, key

    def validate_key(self, key: str) -> Optional[APIKey]:
        """
        Validate an API key.

        Returns:
            APIKey if valid, None if invalid
        """
        key_hash = self.hash_key(key)
        key_id = self._key_lookup.get(key_hash)

        if not key_id:
            return None

        api_key = self._keys.get(key_id)
        if not api_key:
            return None

        if not api_key.enabled:
            logger.warning(f"Disabled API key used: {key_id}")
            return None

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {key_id}")
            return None

        return api_key

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id in self._keys:
            api_key = self._keys[key_id]
            api_key.enabled = False
            logger.info(f"Revoked API key: {key_id}")
            return True
        return False

    def has_scope(self, api_key: APIKey, scope: str) -> bool:
        """Check if an API key has a specific scope."""
        return scope in api_key.scopes

    def get_keys_for_source(self, source_type: SourceType) -> list:
        """Get all API keys for a source type."""
        return [k for k in self._keys.values() if k.source_type == source_type]


class RateLimiter:
    """
    Token bucket rate limiter per API key.

    Tracks request counts and enforces rate limits.
    """

    def __init__(self, default_limit: int = 100, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)  # key_id -> [timestamps]

    def _clean_old_requests(self, key_id: str):
        """Remove requests outside the current window."""
        cutoff = time.time() - self.window_seconds
        self._requests[key_id] = [
            ts for ts in self._requests[key_id] if ts > cutoff
        ]

    def check_rate_limit(self, api_key: APIKey) -> Tuple[bool, int, int]:
        """
        Check if a request is within rate limits.

        Returns:
            Tuple of (allowed, remaining, reset_seconds)
        """
        key_id = api_key.key_id
        limit = api_key.rate_limit or self.default_limit

        self._clean_old_requests(key_id)
        current_count = len(self._requests[key_id])

        remaining = max(0, limit - current_count)
        reset_seconds = self.window_seconds

        if current_count >= limit:
            return False, 0, reset_seconds

        return True, remaining - 1, reset_seconds

    def record_request(self, api_key: APIKey):
        """Record a request for rate limiting."""
        self._requests[api_key.key_id].append(time.time())

    def get_usage(self, api_key: APIKey) -> Dict[str, int]:
        """Get current usage stats for an API key."""
        self._clean_old_requests(api_key.key_id)
        count = len(self._requests[api_key.key_id])
        limit = api_key.rate_limit or self.default_limit
        return {
            "requests": count,
            "limit": limit,
            "remaining": max(0, limit - count),
            "window_seconds": self.window_seconds,
        }


class RequestSigner:
    """
    HMAC request signing for enhanced security.

    Optional feature for sources that want to sign their requests.
    """

    @staticmethod
    def sign_request(
        secret: str,
        method: str,
        path: str,
        timestamp: str,
        body: str = "",
    ) -> str:
        """
        Generate HMAC signature for a request.

        Args:
            secret: Shared secret for signing
            method: HTTP method (GET, POST, etc.)
            path: Request path
            timestamp: ISO timestamp
            body: Request body (for POST/PUT)

        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        message = f"{method}\n{path}\n{timestamp}\n{body}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    @staticmethod
    def verify_signature(
        secret: str,
        signature: str,
        method: str,
        path: str,
        timestamp: str,
        body: str = "",
        max_age_seconds: int = 300,
    ) -> bool:
        """
        Verify an HMAC signature.

        Also checks that the timestamp is not too old (replay protection).
        """
        # Check timestamp age
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            age = (datetime.utcnow() - ts.replace(tzinfo=None)).total_seconds()
            if abs(age) > max_age_seconds:
                logger.warning(f"Request signature too old: {age}s")
                return False
        except ValueError:
            logger.warning(f"Invalid timestamp format: {timestamp}")
            return False

        expected = RequestSigner.sign_request(secret, method, path, timestamp, body)
        return hmac.compare_digest(signature, expected)


# Global instances
api_key_auth = APIKeyAuth()
rate_limiter = RateLimiter()
