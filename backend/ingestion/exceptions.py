"""
Exception classes for the Procore database ingestion module.
"""


class IngestionError(Exception):
    """Base exception for all ingestion errors."""

    pass


class ConnectionError(IngestionError):
    """Database or Vespa connection error."""

    pass


class SchemaError(IngestionError):
    """Schema discovery or validation error."""

    pass


class TransformError(IngestionError):
    """Record transformation error."""

    pass


class IndexError(IngestionError):
    """Vespa indexing error."""

    pass


class DownloadError(IngestionError):
    """File download error."""

    pass
