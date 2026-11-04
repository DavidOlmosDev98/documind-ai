"""Browser acceptance test. Creates its own database and starts/stops its servers."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.request import build_opener, ProxyHandler
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "test-results"
OUTPUT.mkdir(parents=True, exist_ok=True)
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
BASE, API = "http://127.0.0.1:45175", "http://127.0.0.1:48001"
results = []


@contextmanager
def step(name):
    start = time.monotonic()
    record = {"step": name, "status": "PASS"}
    try:
        yield
    except Exception as error:
        record.update(status="FAIL", error=str(error))
        raise
    finally:
        record["seconds"] = round(time.monotonic() - start, 2)
        results.append(record)
        print(record["status"] + ": " + name, flush=True)


def ready(url, process):
    opener = build_opener(ProxyHandler({}))
    until = time.monotonic() + 25
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError("Server stopped before startup; check test logs.")
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError(url)


def run():
    servers = []
    with tempfile.TemporaryDirectory(prefix="documind-e2e-") as directory:
        environment = dict(
            os.environ,
            DATA_DIR=directory,
            DATABASE_URL="",
            AI_MODE="demo",
            OPENAI_API_KEY="",
            WEB_ORIGIN=BASE,
            API_PROXY_TARGET=API,
        )
        with (OUTPUT / "api.log").open("w") as api_log, (OUTPUT / "web.log").open(
            "w"
        ) as web_log:
            try:
                servers.append(
                    subprocess.Popen(
                        [
                            str(PYTHON),
                            "-m",
                            "uvicorn",
                            "backend.app.main:create_app",
                            "--factory",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "48001",
                        ],
                        cwd=ROOT,
                        env=environment,
                        stdout=api_log,
                        stderr=subprocess.STDOUT,
                    )
                )
                servers.append(
                    subprocess.Popen(
                        [
                            "node",
                            str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "45175",
                            "--strictPort",
                        ],
                        cwd=ROOT / "frontend",
                        env=environment,
                        stdout=web_log,
                        stderr=subprocess.STDOUT,
                    )
                )
                with step("Arranque aislado con SQLite temporal"):
                    ready(API + "/api/health", servers[0])
                    ready(BASE, servers[1])
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1000}
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    try:
                        with step("Pantalla inicial y documento de ejemplo"):
                            page.goto(BASE)
                            expect(
                                page.get_by_role(
                                    "heading", name="Menos buscar. Más comprender."
                                )
                            ).to_be_visible()
                            page.screenshot(
                                path=str(OUTPUT / "welcome.png"), full_page=True
                            )
                            page.get_by_role(
                                "button", name="Prueba con nuestra guía de ejemplo"
                            ).click()
                            expect(
                                page.get_by_role(
                                    "heading", name="Guía del equipo · Nébula"
                                )
                            ).to_be_visible()
                            expect(
                                page.get_by_role(
                                    "button", name="¿Cuántos días de vacaciones hay?"
                                )
                            ).to_be_enabled()
                        with step(
                            "Respuesta con cita verificable en la primera página"
                        ):
                            page.get_by_role(
                                "button", name="¿Cuántos días de vacaciones hay?"
                            ).click()
                            expect(page.locator(".answer")).to_contain_text("22 días")
                            page.get_by_role(
                                "button", name="Ver fuente 1, página 1"
                            ).click()
                            expect(page.locator(".source-paper mark")).to_contain_text(
                                "22 días"
                            )
                        with step("Segunda página y resaltado de su fragmento"):
                            page.get_by_label("Pregunta sobre el documento").fill(
                                "¿Cuál es el presupuesto de formación?"
                            )
                            page.get_by_role("button", name="Enviar pregunta").click()
                            expect(page.locator(".answer").last).to_contain_text(
                                "600 euros"
                            )
                            page.get_by_role(
                                "button", name="Ver fuente 1, página 2"
                            ).click()
                            expect(page.locator(".source-paper mark")).to_contain_text(
                                "600 euros"
                            )
                            page.screenshot(
                                path=str(OUTPUT / "conversation.png"), full_page=True
                            )
                        with step(
                            "Pregunta sin respaldo: negativa sin citas inventadas"
                        ):
                            page.get_by_label("Pregunta sobre el documento").fill(
                                "¿Cuál es la capital de Japón?"
                            )
                            page.get_by_role("button", name="Enviar pregunta").click()
                            expect(page.locator(".answer").last).to_contain_text(
                                "información suficiente"
                            )
                            expect(
                                page.locator(".exchange").last.locator(".citation-list")
                            ).to_have_count(0)
                        with step("Historial persistente después de recargar"):
                            page.reload()
                            expect(page.locator(".exchange")).to_have_count(3)
                            expect(page.locator(".answer").first).to_contain_text(
                                "22 días"
                            )
                        with step("Móvil: abrir y cerrar la fuente sin desbordamiento"):
                            page.set_viewport_size({"width": 390, "height": 844})
                            expect(
                                page.get_by_role("button", name="Fuente", exact=True)
                            ).to_be_visible()
                            page.get_by_role(
                                "button", name="Ver fuente 1, página 1"
                            ).click()
                            expect(page.locator(".source-panel")).to_be_visible()
                            expect(page.locator(".source-paper mark")).to_contain_text(
                                "22 días"
                            )
                            page.screenshot(
                                path=str(OUTPUT / "mobile-source.png"), full_page=True
                            )
                            page.get_by_role("button", name="Cerrar fuente").click()
                            expect(page.locator(".source-panel")).to_be_hidden()
                            assert page.evaluate(
                                "document.documentElement.scrollWidth<=innerWidth"
                            )
                            page.screenshot(
                                path=str(OUTPUT / "mobile.png"), full_page=True
                            )
                        with step(
                            "Carga real de un PDF y aislamiento entre documentos"
                        ):
                            page.set_viewport_size({"width": 1440, "height": 1000})
                            page.get_by_label("Seleccionar PDF").set_input_files(
                                ROOT / "examples/guia-equipo.pdf"
                            )
                            expect(
                                page.get_by_role("heading", name="guia-equipo")
                            ).to_be_visible()
                            expect(page.locator(".exchange")).to_have_count(0)
                        with step("Eliminación del documento y conservación del otro"):
                            page.get_by_role(
                                "button", name="Eliminar documento", exact=True
                            ).click()
                            page.get_by_role("dialog").get_by_role(
                                "button", name="Eliminar documento", exact=True
                            ).click()
                            expect(
                                page.get_by_role(
                                    "heading", name="Menos buscar. Más comprender."
                                )
                            ).to_be_visible()
                            assert (
                                len(context.request.get(API + "/api/documents").json())
                                == 1
                            )
                            assert not errors, errors
                    except Exception:
                        page.screenshot(
                            path=str(OUTPUT / "failure.png"), full_page=True
                        )
                        raise
                    finally:
                        context.close()
                        browser.close()
            finally:
                for server in reversed(servers):
                    if server.poll() is None:
                        server.terminate()
                        try:
                            server.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait()


if __name__ == "__main__":
    failure = None
    try:
        run()
    except Exception:
        failure = traceback.format_exc()
        print(failure, flush=True)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failure else "PASS",
        "steps": results,
        "scope": "Modo demo, SQLite y Chromium. Sin OpenAI real ni PostgreSQL real.",
    }
    if failure:
        report["error"] = failure
    (OUTPUT / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Prueba de aceptación de Documind",
        "",
        "Resultado: **" + report["status"] + "**",
        "",
        report["timestamp"],
        "",
        "| Comprobación | Resultado |",
        "|---|---|",
    ]
    lines += ["| " + r["step"] + " | " + r["status"] + " |" for r in results]
    lines += ["", report["scope"]]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    raise SystemExit(1 if failure else 0)
