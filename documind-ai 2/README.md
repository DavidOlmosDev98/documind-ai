# Documind AI

**Menos buscar. Más comprender.** Asistente para consultar PDF con respuestas respaldadas por fragmentos y números de página. Incluye búsqueda local sin claves, integración RAG con OpenAI y revisión visual de las fuentes.

![Conversación con citas y fuente](docs/test-results/conversation.png)

## Lo que puedes probar

- Subir un PDF con texto o abrir el documento ficticio incluido.
- Preguntar en español y consultar citas por página, con el fragmento resaltado.
- Recibir una negativa si no se encuentra respaldo suficiente.
- Conservar documentos y preguntas al reiniciar, y eliminarlos desde la interfaz.
- Cambiar entre SQLite local y PostgreSQL con pgvector mediante configuración.

El **modo demo es extractivo y no utiliza IA generativa**: busca por palabras y muestra frases literales relacionadas. El **modo OpenAI utiliza embeddings y generación con RAG**, con validación de las citas en el servidor. No se presentan resultados demo como si provinieran de un modelo.

## Requisitos

Python **3.12** y Node.js **24**. No necesitas Docker ni una clave para el recorrido demo. Ejecuta los comandos desde la raíz `documind-ai`.

### Windows / PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm ci --prefix frontend
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8001
```

Abre otra terminal en la misma carpeta:

```powershell
npm run dev --prefix frontend
```

### macOS / Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
cp .env.example .env
.venv/bin/python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8001
```

En otra terminal:

```bash
npm run dev --prefix frontend
```

Abre **http://localhost:5175**. La API corre en :8001 y su documentación está en http://127.0.0.1:8001/docs. Detén cada proceso con Ctrl+C.

## Ejemplo de dos minutos

1. Pulsa **Prueba con nuestra guía de ejemplo**.
2. Pregunta: **¿Cuántos días de vacaciones hay?** Encontrarás **22 días**, página 1.
3. Abre **Pág. 1** para contrastar el fragmento resaltado.
4. Pregunta: **¿Cuál es el presupuesto de formación?** Encontrarás **600 euros**, página 2.
5. Pregunta: **¿Cuál es la capital de Japón?** El documento no contiene esa respuesta.
6. Recarga: la conversación se conserva. También puedes subir tu propio PDF de prueba.

## Activar IA real

En `.env` configura:

```dotenv
AI_MODE=openai
OPENAI_API_KEY=tu_clave_privada
OPENAI_MODEL=gpt-4.1-mini
```

Reinicia la API y **vuelve a subir el documento**: cada índice pertenece al modo en el que se creó. La interfaz avisa si intentas consultar un índice de otro modo. El servidor usa `text-embedding-3-small` con 1536 dimensiones. Los embeddings del documento se calculan al cargar; cada pregunta necesita un embedding y puede generar una respuesta. Las llamadas tienen coste.

El texto extraído y las preguntas se envían a OpenAI; usa documentos ficticios o autorizados. La clave permanece en el backend. Un fallo del proveedor se comunica como error y no se sustituye silenciosamente por la demo.

## PostgreSQL + pgvector opcional

```bash
docker compose up -d db
```

Configura `DATABASE_URL=postgresql://documind:local_only@localhost:5434/documind` en `.env` y reinicia. El usuario debe poder crear la extensión `vector`; la imagen de desarrollo la incluye. En modo OpenAI, la búsqueda utiliza distancia coseno en PostgreSQL mediante `<=>`, filtrada por documento. En SQLite se calcula coseno en Python. No hay índice aproximado HNSW: esta versión busca de forma exacta en documentos pequeños.

Cada motor mantiene datos independientes; cambiar la URL no migra registros. El PDF original se guarda en `DATA_DIR` también cuando usas PostgreSQL. Conserva tanto el almacenamiento de archivos como la base si necesitas respaldos.

## Arquitectura

```mermaid
flowchart LR
    A[React + TypeScript] --> B[FastAPI]
    B --> C[Extracción PDF y fragmentos por página]
    C --> D[SQLite o PostgreSQL]
    B --> E[Búsqueda local o embeddings]
    E --> F[Fragmentos relevantes]
    F --> G[Extractos demo o respuesta OpenAI]
    G --> H[Validación literal de citas]
    H --> A
```

| Ruta | Función |
|---|---|
| `backend/app/pdf.py` | Extrae texto y fragmenta sin cruzar páginas |
| `backend/app/retrieval.py` | Búsqueda lexical, coseno y respuestas demo |
| `backend/app/ai.py` | Embeddings, generación estructurada y validación de citas |
| `backend/app/store.py` | Persistencia y búsqueda pgvector |
| `backend/app/main.py` | API, carga, preguntas e historial |
| `frontend/src/main.tsx` | Biblioteca, conversación y visor de fuentes |
| `examples/guia-equipo.pdf` | Referencia ficticia de dos páginas |
| `docs/manual.pdf` | Manual en español y recorrido guiado |

## Pruebas

```bash
# macOS/Linux; en Windows usa .\.venv\Scripts\python.exe
.venv/bin/python -m pytest -q
npm run build --prefix frontend
```

Prueba de aceptación en navegador, con servidores y base temporal propios:

```bash
.venv/bin/python -m pip install playwright==1.62.0
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/test_e2e.py
```

Genera capturas, `docs/test-results/result.json` y un [informe](docs/test-results/report.md). Reserva los puertos 48001 y 45175 para esta prueba. No toca tus documentos normales. GitHub Actions repite las pruebas y adjunta sus resultados al subir el workflow.

## API

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/health` | Modo y almacenamiento |
| GET / POST | `/api/documents` | Listar / subir multipart `file` |
| POST | `/api/documents/sample` | Cargar ejemplo |
| POST | `/api/documents/{id}/questions` | Enviar JSON `{"question":"..."}` |
| GET | `/api/documents/{id}/messages` | Historial |
| GET | `/api/documents/{id}/pages/{n}` | Texto fuente de una página |
| GET | `/api/documents/{id}/file` | Abrir PDF original |
| DELETE | `/api/documents/{id}` | Eliminar PDF, índice e historial |

## Alcance y límites

MVP local de un solo usuario: sin autenticación, equipos, OCR, lectura de imágenes ni conversación con varios documentos a la vez. Cada pregunta es independiente; el historial se muestra pero no se envía como contexto. Máximo 8 MB, 100 páginas y 180.000 caracteres extraídos. PDF muy complejos o dañados pueden rechazarse. El visor muestra texto extraído, no reproduce el diseño del PDF.

Una cita literal válida **no demuestra que toda la respuesta sea correcta**. Comprueba las fuentes; no hay evaluación formal de exactitud. El umbral coseno es una heurística, no una probabilidad de acierto. La búsqueda demo puede devolver frases relacionadas que no contesten toda la pregunta, especialmente con palabras ambiguas.

Antes de exponerlo a Internet: añade autenticación, cuotas, protección de subida y límites en el proxy, aislamiento de procesamiento de PDF, tiempos máximos y límites de gasto. Los controles locales no convierten el parser en un sandbox para archivos hostiles. Para producción también hacen falta migraciones y respaldos. La integración real OpenAI y PostgreSQL requiere verificarse con servicios configurados; las pruebas de proveedor incluidas usan simulaciones.

## GitHub

Publica los archivos incluyendo `.env.example`, `.gitignore` y `.github`. Nunca subas `.env`, `.venv`, `node_modules` ni `data`. En GitHub Desktop revisa los cambios, crea un commit y usa **Push origin**.
