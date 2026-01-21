"""
PDF processing for database-ingested files.

Integrates the ColPali PDF processing system with the database ingestion pipeline.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from backend.ingestion.file_detector import DetectedFile


@dataclass
class PDFProcessingResult:
    """Result of processing a single PDF."""

    file: DetectedFile
    success: bool
    pages_indexed: int = 0
    error: Optional[str] = None


class PDFProcessor:
    """Process PDFs downloaded from database ingestion with ColPali.

    Lazy-loads the ColPali model on first use to avoid loading 3B+ parameters
    at startup when PDF processing may not be needed.
    """

    def __init__(
        self,
        vespa_app: Any,
        logger: Optional[logging.Logger] = None,
        batch_size: int = 4,
    ):
        """Initialize PDF processor.

        Args:
            vespa_app: Vespa application instance
            logger: Optional logger instance
            batch_size: Batch size for embedding generation
        """
        self._vespa = vespa_app
        self._logger = logger or logging.getLogger(__name__)
        self._batch_size = batch_size

        # Lazy-loaded model components
        self._model = None
        self._processor = None
        self._device = None

    def _load_model(self) -> None:
        """Load ColPali model on first use."""
        if self._model is not None:
            return

        self._logger.info("Loading ColPali model for PDF processing...")

        import torch
        from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

        # Determine device
        if torch.cuda.is_available():
            self._device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        self._logger.info(f"Using device: {self._device}")

        # Load model and processor
        model_name = "tsystems/colqwen2.5-3b-multilingual-v1.0"
        self._model = ColQwen2_5.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16 if self._device != "cpu" else torch.float32,
            device_map=self._device,
        ).eval()
        self._processor = ColQwen2_5_Processor.from_pretrained(model_name)

        self._logger.info("ColPali model loaded successfully")

    def _build_metadata(self, file: DetectedFile) -> tuple[list[str], str]:
        """Build tags and description from DetectedFile metadata.

        Args:
            file: DetectedFile with source metadata

        Returns:
            Tuple of (tags list, description string)
        """
        tags = []
        description_parts = []

        # Add source table as tag
        if file.source_table:
            tags.append(file.source_table)
            description_parts.append(f"Source: {file.source_table}")

        # Add record ID as tag
        if file.source_record_id:
            tags.append(f"record:{file.source_record_id}")
            if description_parts:
                description_parts[0] += f" (record {file.source_record_id})"
            else:
                description_parts.append(f"Record: {file.source_record_id}")

        # Add source column as tag
        if file.source_column:
            tags.append(f"column:{file.source_column}")

        # Build description
        description = " | ".join(description_parts) if description_parts else ""

        return tags, description

    def process_pdf(
        self,
        file: DetectedFile,
        local_path: Path,
    ) -> PDFProcessingResult:
        """Process a single PDF file with ColPali and index to Vespa.

        Args:
            file: DetectedFile with metadata
            local_path: Path to the downloaded PDF file

        Returns:
            PDFProcessingResult with processing outcome
        """
        # Lazy load model
        self._load_model()

        # Import ingest function
        from backend.ingest import ingest_pdf

        # Read PDF file
        try:
            file_bytes = local_path.read_bytes()
        except Exception as e:
            self._logger.error(f"Failed to read PDF file {local_path}: {e}")
            return PDFProcessingResult(
                file=file,
                success=False,
                error=f"Failed to read file: {e}",
            )

        # Build metadata from DetectedFile
        tags, description = self._build_metadata(file)
        filename = file.filename or local_path.name
        title = Path(filename).stem if filename else None

        # Process with ingest_pdf
        try:
            success, message, pages_indexed = ingest_pdf(
                file_bytes=file_bytes,
                filename=filename,
                vespa_app=self._vespa,
                model=self._model,
                processor=self._processor,
                device=self._device,
                title=title,
                description=description,
                tags=tags,
                batch_size=self._batch_size,
            )

            if success:
                self._logger.debug(
                    f"Indexed PDF {filename}: {pages_indexed} pages "
                    f"(source: {file.source_table}:{file.source_record_id})"
                )
            else:
                self._logger.warning(f"Failed to index PDF {filename}: {message}")

            return PDFProcessingResult(
                file=file,
                success=success,
                pages_indexed=pages_indexed,
                error=None if success else message,
            )

        except Exception as e:
            self._logger.error(f"Error processing PDF {filename}: {e}")
            return PDFProcessingResult(
                file=file,
                success=False,
                error=str(e),
            )

    def process_batch(
        self,
        files_with_paths: list[tuple[DetectedFile, Path]],
    ) -> list[PDFProcessingResult]:
        """Process a batch of PDF files.

        Args:
            files_with_paths: List of (DetectedFile, local_path) tuples

        Returns:
            List of PDFProcessingResult for each file
        """
        if not files_with_paths:
            return []

        self._logger.info(f"Processing batch of {len(files_with_paths)} PDFs...")

        results = []
        for file, local_path in files_with_paths:
            result = self.process_pdf(file, local_path)
            results.append(result)

        successful = sum(1 for r in results if r.success)
        total_pages = sum(r.pages_indexed for r in results)

        self._logger.info(
            f"Batch complete: {successful}/{len(results)} PDFs processed, "
            f"{total_pages} pages indexed"
        )

        return results

    @property
    def model_loaded(self) -> bool:
        """Check if the model has been loaded."""
        return self._model is not None
