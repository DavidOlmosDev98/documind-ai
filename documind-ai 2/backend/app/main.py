from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from .settings import Settings, ROOT
from .store import Store
from .pdf import extract_pdf, DocumentError, MAX_BYTES
from .ai import AI, ProviderError, EMBEDDING_MODEL
from .retrieval import cosine, demo_answer

REFUSAL = "No encontré información suficiente en este documento para responder a esa pregunta. Prueba con otra pregunta o consulta otro PDF."


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=5, max_length=600)


def create_app(settings: Settings | None = None, ai=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(settings.data_dir, settings.database_url)
        app.state.ai = ai or AI(settings)
        yield

    app = FastAPI(title="Documind API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def get_document(document_id: UUID):
        document = app.state.store.get(str(document_id))
        if not document:
            raise HTTPException(404, "Documento no encontrado.")
        return document

    def public(document):
        return {key: value for key, value in document.items() if key != "chunks"} | {
            "chunk_count": len(document["chunks"])
        }

    def ingest(data: bytes, name: str):
        try:
            pages, chunks = extract_pdf(data)
            if settings.mode == "openai":
                embeddings = app.state.ai.embed([c["text"] for c in chunks])
                for chunk, embedding in zip(chunks, embeddings):
                    chunk["embedding"] = embedding
        except DocumentError as error:
            raise HTTPException(422, str(error)) from error
        except ProviderError as error:
            raise HTTPException(503, str(error)) from error
        document_id = str(uuid4())
        document = {
            "id": document_id,
            "name": name,
            "pages": pages,
            "size": len(data),
            "mode": settings.mode,
            "embedding_model": EMBEDDING_MODEL if settings.mode == "openai" else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chunks": chunks,
        }
        path = settings.data_dir / (document_id + ".pdf")
        try:
            path.write_bytes(data)
            app.state.store.save(document)
        except Exception:
            path.unlink(missing_ok=True)
            logging.exception("No se pudo guardar un documento")
            raise HTTPException(503, "No se pudo guardar el documento.")
        return public(document)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": settings.mode,
            "storage": "postgresql" if settings.database_url else "sqlite",
        }

    @app.get("/api/documents")
    def documents():
        return [public(d) for d in app.state.store.list_documents()]

    @app.post("/api/documents", status_code=201)
    def upload(file: UploadFile = File(...)):
        try:
            data = file.file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, "El PDF supera el límite de 8 MB.")
            name = (
                (file.filename or "documento.pdf")
                .replace("\\", "/")
                .split("/")[-1][:160]
            )
            return ingest(data, name)
        finally:
            file.file.close()

    @app.post("/api/documents/sample", status_code=201)
    def sample():
        path = ROOT / "examples" / "guia-equipo.pdf"
        return ingest(path.read_bytes(), "Guía del equipo · Nébula.pdf")

    @app.get("/api/documents/{document_id}/file")
    def original(document_id: UUID):
        document = get_document(document_id)
        path = settings.data_dir / (str(document_id) + ".pdf")
        if not path.exists():
            raise HTTPException(404, "El archivo original ya no está disponible.")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=document["name"],
            content_disposition_type="inline",
        )

    @app.get("/api/documents/{document_id}/pages/{page}")
    def page_text(document_id: UUID, page: int):
        document = get_document(document_id)
        if page < 1 or page > document["pages"]:
            raise HTTPException(404, "Página no encontrada.")
        # Merge overlapping chunks without duplicating text in the source panel.
        text = ""
        for chunk in [c for c in document["chunks"] if c["page"] == page]:
            overlap = min(180, len(text), len(chunk["text"]))
            while overlap and text[-overlap:] != chunk["text"][:overlap]:
                overlap -= 1
            text += (" " if text and not overlap else "") + chunk["text"][overlap:]
        return {
            "page": page,
            "text": text or "Esta página no contiene texto seleccionable.",
        }

    @app.get("/api/documents/{document_id}/messages")
    def history(document_id: UUID):
        get_document(document_id)
        return app.state.store.history(str(document_id))

    @app.post("/api/documents/{document_id}/questions")
    def ask(document_id: UUID, body: Question):
        document = get_document(document_id)
        if document["mode"] != settings.mode:
            raise HTTPException(
                409,
                "Este documento se indexó en otro modo. Vuelve a subirlo para usar el modo actual.",
            )
        try:
            if settings.mode == "demo":
                result = demo_answer(body.question, document["chunks"])
            else:
                vector = app.state.ai.embed([body.question])[0]
                if settings.database_url:
                    scores = app.state.store.vector_search(str(document_id), vector)
                else:
                    scores = sorted(
                        [
                            (c["id"], cosine(c["embedding"], vector))
                            for c in document["chunks"]
                        ],
                        key=lambda pair: pair[1],
                        reverse=True,
                    )[:5]
                indexed = {c["id"]: c for c in document["chunks"]}
                candidates = [indexed[i] for i, score in scores if score >= 0.25]
                result = app.state.ai.answer(body.question, candidates)
        except ProviderError as error:
            raise HTTPException(503, str(error)) from error
        message = {
            "id": str(uuid4()),
            "document_id": str(document_id),
            "question": body.question,
            "answer": result["answer"] if result else REFUSAL,
            "citations": result["citations"] if result else [],
            "supported": bool(result),
            "mode": settings.mode,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            app.state.store.add_message(message)
        except Exception as error:
            raise HTTPException(
                409,
                "No se pudo guardar la respuesta. Comprueba que el documento siga disponible.",
            ) from error
        return message

    @app.delete("/api/documents/{document_id}", status_code=204)
    def delete(document_id: UUID):
        get_document(document_id)
        app.state.store.delete(str(document_id))
        (settings.data_dir / (str(document_id) + ".pdf")).unlink(missing_ok=True)

    return app


# The factory is used by uvicorn --factory; importing this module has no DB side effects.
