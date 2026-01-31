"""Unit tests for backend.s3 presigned URL generation."""

from unittest.mock import MagicMock, patch

import pytest

from backend.connectors.storage.s3 import generate_presigned_url
import backend.s3 as s3_mod


@pytest.fixture(autouse=True)
def _reset_s3_client():
    """Reset the module-level S3 client singleton between tests."""
    s3_mod._s3_client = None
    yield
    s3_mod._s3_client = None


def test_generate_presigned_url_returns_url():
    """generate_presigned_url returns the URL produced by boto3."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed"

    with patch.object(s3_mod, "_get_s3_client", return_value=mock_client):
        url = generate_presigned_url("path/to/file.pdf", bucket="test-bucket")

    assert url == "https://s3.example.com/signed"
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "path/to/file.pdf"},
        ExpiresIn=3600,
    )


def test_generate_presigned_url_empty_key_raises():
    """generate_presigned_url raises ValueError for empty key."""
    with pytest.raises(ValueError, match="s3_key must be a non-empty string"):
        generate_presigned_url("")


def test_generate_presigned_url_none_key_raises():
    """generate_presigned_url raises ValueError for None key."""
    with pytest.raises(ValueError, match="s3_key must be a non-empty string"):
        generate_presigned_url(None)


def test_generate_presigned_url_default_bucket(monkeypatch):
    """generate_presigned_url uses S3_BUCKET env var when bucket not specified."""
    monkeypatch.setenv("S3_BUCKET", "env-bucket")

    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed"

    with patch.object(s3_mod, "_get_s3_client", return_value=mock_client):
        generate_presigned_url("some/key.pdf")

    call_params = mock_client.generate_presigned_url.call_args[1]["Params"]
    assert call_params["Bucket"] == "env-bucket"


def test_s3_client_initialized_once():
    """_get_s3_client returns the same client on subsequent calls (singleton)."""
    mock_client = MagicMock()

    # Pre-set the singleton to simulate an already-initialized client
    s3_mod._s3_client = mock_client

    client1 = s3_mod._get_s3_client()
    client2 = s3_mod._get_s3_client()

    assert client1 is mock_client
    assert client2 is mock_client
    assert client1 is client2
