"""Local, constrained document-to-Markdown conversion.

Raw uploads and Drive downloads are converted only inside the ShieldAI process.
The converter deliberately accepts a small extension allow-list, does not load
MarkItDown plugins, does not invoke an LLM, and deletes its temporary copy as
soon as conversion completes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


class DocumentConversionError(ValueError):
    """Safe error message for an invalid or unsupported local document."""


@dataclass(frozen=True)
class ConvertedDocument:
    """Markdown created locally from a validated file."""

    filename: str
    extension: str
    markdown: str


class LocalDocumentConverter:
    """Convert approved local document bytes with Microsoft MarkItDown."""

    # Archive, email, media and URL inputs are intentionally excluded. They
    # expand the attack surface and are not necessary for the MVP workflow.
    SUPPORTED_EXTENSIONS = frozenset({
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".txt", ".md",
        ".csv", ".json",
    })
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    MAX_MARKDOWN_CHARS = 500_000

    def __init__(self, staging_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.staging_dir = staging_dir or root / "data" / "staging"

    @classmethod
    def validate_upload(cls, filename: str, content: bytes) -> tuple[str, str]:
        safe_name = Path(filename).name.strip()
        if not safe_name or safe_name in {".", ".."}:
            raise DocumentConversionError("A valid local file name is required.")
        if len(safe_name) > 180:
            raise DocumentConversionError("The file name is too long.")
        if not content:
            raise DocumentConversionError("The selected file is empty.")
        if len(content) > cls.MAX_UPLOAD_BYTES:
            raise DocumentConversionError("Files larger than 10 MB are not accepted by the local converter.")
        extension = Path(safe_name).suffix.lower()
        if extension not in cls.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(cls.SUPPORTED_EXTENSIONS))
            raise DocumentConversionError(f"Unsupported file type. Use one of: {supported}.")
        return safe_name, extension

    @staticmethod
    def _markitdown() -> object:
        try:
            from markitdown import MarkItDown
        except ImportError as exc:
            raise DocumentConversionError(
                "MarkItDown is not installed. Run: python -m pip install -r requirements.txt"
            ) from exc
        # Plugins can add arbitrary conversion behavior. The privacy gateway
        # uses only MarkItDown's local built-in converters.
        return MarkItDown(enable_plugins=False)

    def convert_bytes(self, filename: str, content: bytes) -> ConvertedDocument:
        """Write a validated local copy, convert it, and remove it immediately."""
        safe_name, extension = self.validate_upload(filename, content)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="shieldai-convert-", dir=self.staging_dir) as temporary_dir:
            local_file = Path(temporary_dir) / f"document{extension}"
            local_file.write_bytes(content)
            try:
                # `convert_local` prevents MarkItDown from interpreting the
                # value as a URL or retrieving anything from the network.
                result = self._markitdown().convert_local(local_file)  # type: ignore[attr-defined]
            except DocumentConversionError:
                raise
            except Exception as exc:  # Converter-specific parse errors vary by format.
                raise DocumentConversionError("The document could not be converted locally.") from exc

        markdown = str(getattr(result, "text_content", "") or getattr(result, "markdown", "")).strip()
        if not markdown:
            raise DocumentConversionError("No readable text was found in the document.")
        if len(markdown) > self.MAX_MARKDOWN_CHARS:
            raise DocumentConversionError("The converted document is too large for a single protected request.")
        return ConvertedDocument(filename=safe_name, extension=extension, markdown=markdown)
