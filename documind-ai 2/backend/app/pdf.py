"""Extract bounded text chunks while keeping the original PDF page numbers."""

from io import BytesIO
import re
from pypdf import PdfReader

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 100
MAX_CHARS = 180_000


class DocumentError(ValueError):
    pass


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf(data: bytes) -> tuple[int, list[dict]]:
    if len(data) > MAX_BYTES:
        raise DocumentError("El PDF supera el límite de 8 MB.")
    if not data.startswith(b"%PDF-"):
        raise DocumentError("El archivo no es un PDF válido.")
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise DocumentError("Usa un PDF sin contraseña.")
        if len(reader.pages) > MAX_PAGES:
            raise DocumentError("El máximo es de 100 páginas por documento.")
        chunks, total = [], 0
        for page_number, page in enumerate(reader.pages, start=1):
            # pypdf decodes page content in memory. A bounded decoded stream
            # prevents very large page streams from reaching text extraction.
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 3_000_000:
                raise DocumentError("Una página es demasiado compleja para esta demo.")
            text = normalize(page.extract_text() or "")
            total += len(text)
            if total > MAX_CHARS:
                raise DocumentError(
                    "El documento contiene demasiado texto (máximo 180.000 caracteres)."
                )
            # Overlap keeps context across boundaries. No chunk crosses pages.
            start = 0
            while start < len(text):
                end = min(start + 1000, len(text))
                if end < len(text):
                    boundary = text.rfind(" ", start + 650, end)
                    if boundary > start:
                        end = boundary
                fragment = text[start:end].strip()
                if fragment:
                    chunks.append(
                        {"id": len(chunks), "page": page_number, "text": fragment}
                    )
                if end == len(text):
                    break
                start = max(start + 1, end - 180)
        if not chunks:
            raise DocumentError(
                "No encontramos texto seleccionable. Los PDF escaneados necesitan OCR, que esta versión no incluye."
            )
        return len(reader.pages), chunks
    except DocumentError:
        raise
    except Exception as error:
        raise DocumentError(
            "No se pudo leer el PDF. Comprueba que no esté dañado."
        ) from error
