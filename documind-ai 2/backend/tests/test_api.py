from io import BytesIO
from pathlib import Path
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from backend.app.main import create_app
from backend.app.settings import Settings, ROOT
from backend.app.ai import AI, ProviderError, DIMENSIONS
from backend.app.pdf import extract_pdf, DocumentError


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(tmp_path))) as test:
        yield test


def sample(client):
    result = client.post("/api/documents/sample")
    assert result.status_code == 201, result.text
    return result.json()


def test_complete_flow_with_verifiable_page_citations(client):
    document = sample(client)
    assert document["pages"] == 2 and document["mode"] == "demo"
    assert "chunks" not in document
    document_id = document["id"]
    response = client.post(
        f"/api/documents/{document_id}/questions",
        json={"question": "¿Cuántos días de vacaciones hay?"},
    )
    assert response.status_code == 200
    message = response.json()
    assert message["supported"] and "22 días" in message["answer"]
    assert message["citations"][0]["page"] == 1
    assert all(reference["page"] == 1 for reference in message["citations"])
    for reference in message["citations"]:
        page = client.get(
            f'/api/documents/{document_id}/pages/{reference["page"]}'
        ).json()
        assert reference["quote"] in page["text"]
    history = client.get(f"/api/documents/{document_id}/messages").json()
    assert history == [message]
    assert client.get(f"/api/documents/{document_id}/file").content.startswith(b"%PDF")
    assert client.get(f"/api/documents/{document_id}/pages/3").status_code == 404


def test_second_page_and_no_answer(client):
    document_id = sample(client)["id"]
    endpoint = f"/api/documents/{document_id}/questions"
    learning = client.post(
        endpoint, json={"question": "¿Cuál es el presupuesto de formación?"}
    ).json()
    assert learning["supported"] and "600 euros" in learning["answer"]
    assert learning["citations"][0]["page"] == 2
    assert all(reference["page"] == 2 for reference in learning["citations"])
    refunds = client.post(
        endpoint, json={"question": "¿Cómo se solicitan los reembolsos?"}
    ).json()
    assert refunds["supported"] and "15 días" in refunds["answer"]
    unknown = client.post(
        endpoint, json={"question": "¿Cuál es la capital de Japón?"}
    ).json()
    assert not unknown["supported"] and unknown["citations"] == []
    assert "información suficiente" in unknown["answer"]


def test_upload_validation_and_invalid_questions(client):
    assert (
        client.post(
            "/api/documents",
            files={"file": ("falso.pdf", b"Not a PDF", "application/pdf")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/documents",
            files={
                "file": (
                    "large.pdf",
                    b"%PDF-" + b"0" * (8 * 1024 * 1024),
                    "application/pdf",
                )
            },
        ).status_code
        == 413
    )
    empty = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(empty)
    assert (
        client.post(
            "/api/documents",
            files={"file": ("empty.pdf", empty.getvalue(), "application/pdf")},
        ).status_code
        == 422
    )
    document_id = sample(client)["id"]
    endpoint = f"/api/documents/{document_id}/questions"
    for question in ["", "   ", "x" * 601]:
        assert client.post(endpoint, json={"question": question}).status_code == 422
    assert client.get("/api/documents/no-uuid/messages").status_code == 422
    assert (
        client.get(
            "/api/documents/00000000-0000-0000-0000-000000000000/messages"
        ).status_code
        == 404
    )


def test_uploaded_pdf_and_document_isolation(client):
    first = sample(client)
    pdf = (ROOT / "examples/guia-equipo.pdf").read_bytes()
    second = client.post(
        "/api/documents", files={"file": ("equipo.pdf", pdf, "application/pdf")}
    ).json()
    client.post(
        f'/api/documents/{first["id"]}/questions',
        json={"question": "¿Cuántos días de vacaciones hay?"},
    )
    assert client.get(f'/api/documents/{second["id"]}/messages').json() == []
    assert len(client.get("/api/documents").json()) == 2


def test_persistence_and_cascading_delete(tmp_path):
    settings = Settings(tmp_path)
    with TestClient(create_app(settings)) as first:
        document = sample(first)
        first.post(
            f'/api/documents/{document["id"]}/questions',
            json={"question": "¿Cuántos días de vacaciones hay?"},
        )
    with TestClient(create_app(settings)) as second:
        document_id = document["id"]
        assert second.get("/api/documents").json()[0]["id"] == document_id
        assert len(second.get(f"/api/documents/{document_id}/messages").json()) == 1
        assert second.delete(f"/api/documents/{document_id}").status_code == 204
        assert not (tmp_path / (document_id + ".pdf")).exists()
        assert second.get("/api/documents").json() == []
        assert second.get(f"/api/documents/{document_id}/messages").status_code == 404


def test_pdf_encrypted_and_page_limits():
    encrypted = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.encrypt("secret")
    writer.write(encrypted)
    with pytest.raises(DocumentError, match="contraseña"):
        extract_pdf(encrypted.getvalue())
    long = BytesIO()
    writer = PdfWriter()
    for _ in range(101):
        writer.add_blank_page(width=300, height=300)
    writer.write(long)
    with pytest.raises(DocumentError, match="100 páginas"):
        extract_pdf(long.getvalue())


def ai_client(tmp_path, payload, status=200):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, json=payload)
    )
    return AI(
        Settings(tmp_path, mode="openai", api_key="test-only"),
        httpx.Client(base_url="https://example.test/", transport=transport),
    )


def chat_payload(data):
    return {"choices": [{"message": {"content": json.dumps(data)}}]}


def test_real_mode_validates_quotes_and_does_not_trust_page_numbers(tmp_path):
    output = {
        "supported": True,
        "answer": "Hay 22 días de vacaciones.",
        "citations": [{"chunk_id": 7, "quote": "Hay 22 días de vacaciones."}],
    }
    ai = ai_client(tmp_path, chat_payload(output))
    answer = ai.answer(
        "¿Vacaciones?",
        [{"id": 7, "page": 3, "text": "Normativa: Hay 22 días de vacaciones."}],
    )
    assert answer["citations"][0]["page"] == 3
    for bad in [
        {"chunk_id": 99, "quote": "Hay 22 días de vacaciones."},
        {"chunk_id": 7, "quote": "Hay 90 días de vacaciones."},
    ]:
        output["citations"] = [bad]
        with pytest.raises(ProviderError, match="cita"):
            ai_client(tmp_path, chat_payload(output)).answer(
                "¿Vacaciones?",
                [{"id": 7, "page": 3, "text": "Hay 22 días de vacaciones."}],
            )


def test_ai_refusal_bad_format_and_provider_outage(tmp_path):
    chunks = [{"id": 0, "page": 1, "text": "Texto de referencia."}]
    assert (
        ai_client(
            tmp_path,
            chat_payload({"supported": False, "answer": "No sé.", "citations": []}),
        ).answer("¿Algo?", chunks)
        is None
    )
    with pytest.raises(ProviderError):
        ai_client(tmp_path, {"wrong": "shape"}).answer("¿Algo?", chunks)
    with pytest.raises(ProviderError):
        ai_client(tmp_path, {"error": "rate limit"}, 429).answer("¿Algo?", chunks)
    with pytest.raises(ProviderError):
        ai_client(
            tmp_path,
            chat_payload({"supported": True, "answer": "Inventada", "citations": []}),
        ).answer("¿Algo?", chunks)


def test_embedding_dimensions_and_indices(tmp_path):
    ai = ai_client(
        tmp_path,
        {"data": [{"index": 0, "embedding": [1.0] + [0.0] * (DIMENSIONS - 1)}]},
    )
    assert len(ai.embed(["sample"])[0]) == DIMENSIONS
    for payload in [
        {"data": [{"index": 0, "embedding": [1, 2]}]},
        {"data": []},
        {"data": [{"index": 1, "embedding": [1] * DIMENSIONS}]},
    ]:
        with pytest.raises(ProviderError):
            ai_client(tmp_path, payload).embed(["sample"])


def test_mode_changes_require_reindexing(tmp_path):
    with TestClient(create_app(Settings(tmp_path))) as demo:
        document = sample(demo)
    with TestClient(create_app(Settings(tmp_path, mode="openai"))) as real:
        assert (
            real.post(
                f'/api/documents/{document["id"]}/questions',
                json={"question": "¿Vacaciones?"},
            ).status_code
            == 409
        )
