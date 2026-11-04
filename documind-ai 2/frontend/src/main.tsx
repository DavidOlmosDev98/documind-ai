import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownToLine,
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  FolderOpen,
  Layers,
  LoaderCircle,
  MessageSquare,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import "./style.css";

type Doc = {
  id: string;
  name: string;
  pages: number;
  size: number;
  mode: string;
  chunk_count: number;
  created_at: string;
};
type Citation = { chunk_id: number; page: number; quote: string };
type Message = {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
  supported: boolean;
  mode: string;
};
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch("/api" + path, init);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : response.status === 422
          ? "Comprueba los datos. La pregunta debe tener entre 5 y 600 caracteres."
          : "No se pudo completar la solicitud. Inténtalo de nuevo.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const suggestions = [
  "¿Cuántos días de vacaciones hay?",
  "¿Cuál es el presupuesto de formación?",
  "¿Cómo se solicitan los reembolsos?",
];
function App() {
  const [documents, setDocuments] = useState<Doc[]>([]),
    [selected, setSelected] = useState<string | null>(null),
    [messages, setMessages] = useState<Message[]>([]),
    [mode, setMode] = useState("demo"),
    [question, setQuestion] = useState(""),
    [pending, setPending] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [historyLoading, setHistoryLoading] = useState(false),
    [error, setError] = useState(""),
    [page, setPage] = useState(1),
    [pageText, setPageText] = useState(""),
    [sourceLoading, setSourceLoading] = useState(false),
    [citation, setCitation] = useState<Citation | null>(null),
    [showSource, setShowSource] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false),
    [dragging, setDragging] = useState(false);
  const upload = useRef<HTMLInputElement>(null),
    bottom = useRef<HTMLDivElement>(null),
    input = useRef<HTMLTextAreaElement>(null);
  const doc = documents.find((d) => d.id === selected);
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Doc[]>("/documents"),
      request<{ mode: string }>("/health"),
    ])
      .then(([docs, health]) => {
        if (active) {
          setDocuments(docs);
          setSelected(docs[0]?.id || null);
          setMode(health.mode);
        }
      })
      .catch((e) => {
        if (active)
          setError(
            "No se pudo conectar con la API. Comprueba que esté iniciada. " +
              e.message,
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    setMessages([]);
    setCitation(null);
    setPage(1);
    setShowSource(false);
    setConfirmDelete(false);
    setQuestion("");
    if (!selected) return;
    const controller = new AbortController();
    setHistoryLoading(true);
    request<Message[]>(`/documents/${selected}/messages`, {
      signal: controller.signal,
    })
      .then(setMessages)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [selected]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setPageText("");
    setSourceLoading(true);
    request<{ text: string }>(`/documents/${selected}/pages/${page}`, {
      signal: controller.signal,
    })
      .then((data) => setPageText(data.text))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setSourceLoading(false);
      });
    return () => controller.abort();
  }, [selected, page]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function addDocument(newDoc: Doc) {
    setDocuments((items) => [newDoc, ...items]);
    setSelected(newDoc.id);
  }
  function uploadFile(file?: File) {
    if (!file || busy) return;
    void action(async () => {
      if (file.size > 8 * 1024 * 1024)
        throw new Error("El máximo es de 8 MB por PDF.");
      if (!file.name.toLowerCase().endsWith(".pdf"))
        throw new Error("Selecciona un archivo PDF.");
      const body = new FormData();
      body.append("file", file);
      addDocument(await request<Doc>("/documents", { method: "POST", body }));
    });
  }
  function useSample() {
    void action(async () =>
      addDocument(await request<Doc>("/documents/sample", { method: "POST" })),
    );
  }
  function source(ref: Citation) {
    setCitation(ref);
    setPage(ref.page);
    setShowSource(true);
  }
  async function ask(text = question) {
    const clean = text.trim();
    if (!doc || clean.length < 5 || busy || historyLoading) return;
    setQuestion("");
    setPending(clean);
    await action(async () => {
      const message = await request<Message>(`/documents/${doc.id}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: clean }),
      });
      setMessages((items) => [...items, message]);
      if (message.citations[0]) {
        setCitation(message.citations[0]);
        setPage(message.citations[0].page);
      }
    });
    setPending("");
  }
  const lock = busy || historyLoading || loading;
  function highlighted() {
    if (
      !citation ||
      citation.page !== page ||
      !pageText.includes(citation.quote)
    )
      return pageText;
    const position = pageText.indexOf(citation.quote);
    return (
      <>
        {pageText.slice(0, position)}
        <mark>{citation.quote}</mark>
        {pageText.slice(position + citation.quote.length)}
      </>
    );
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-icon">
            <BookOpen size={21} />
          </span>
          documind<span className="brand-dot">.</span>
        </a>
        <div className="workspace">
          <span className="avatar">D</span>
          <div>
            <strong>Mi biblioteca</strong>
            <small>Tu espacio de conocimiento</small>
          </div>
          <span className="workspace-tag">PERSONAL</span>
        </div>
        <button
          className="upload-side"
          onClick={() => upload.current?.click()}
          disabled={lock}
        >
          <Plus size={17} /> Subir documento <span>PDF</span>
        </button>
        <div className="nav-label">
          TUS DOCUMENTOS{" "}
          <span>{documents.length.toString().padStart(2, "0")}</span>
        </div>
        <div className="document-list">
          {documents.map((d) => (
            <button
              key={d.id}
              className={"document-item " + (d.id === selected ? "active" : "")}
              onClick={() => {
                setSelected(d.id);
                setError("");
              }}
              disabled={lock}
            >
              <FileText size={18} />
              <span>
                <strong>{d.name}</strong>
                <small>
                  {d.pages} páginas · {(d.size / 1024).toFixed(0)} KB
                </small>
              </span>
              {d.id === selected && <span className="selected-dot" />}
            </button>
          ))}
          {!documents.length && (
            <div className="library-empty">
              <FolderOpen size={23} />
              <p>Tus documentos aparecerán aquí.</p>
            </div>
          )}
        </div>
        <div className="sidebar-tip">
          <div>
            <Sparkles size={17} />
            <strong>Empieza con una pregunta.</strong>
          </div>
          <p>
            Encuentra lo importante.
            <br />
            Conoce de dónde viene.
          </p>
          <button disabled={lock} onClick={useSample}>
            Explorar PDF de ejemplo <ArrowUpRight size={14} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <span className="status-dot" />
          {mode === "demo"
            ? "Modo demo · sin API key"
            : "OpenAI · IA conectada"}
          <span className="version">v1.0</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span>Mi biblioteca</span>
            <ChevronRight size={13} />
            <strong>{doc ? "Espacio de lectura" : "Vista general"}</strong>
          </div>
          <div className="topbar-right">
            <span className="private-badge">
              <ShieldCheck size={13} />
              {mode === "demo"
                ? "Procesamiento local"
                : "Procesamiento con OpenAI"}
            </span>
            <span className="top-avatar">D</span>
          </div>
        </header>
        {error && (
          <div className="error" role="alert">
            <span>{error}</span>
            <button aria-label="Cerrar error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        <input
          hidden
          ref={upload}
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Seleccionar PDF"
          onChange={(e) => {
            uploadFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        {!doc ? (
          <section
            className="welcome"
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              uploadFile(e.dataTransfer.files[0]);
            }}
          >
            <div className="eyebrow">
              <span /> CONVERSA CON TUS DOCUMENTOS
            </div>
            <h1>
              Menos buscar.
              <br />
              Más <span>comprender.</span>
            </h1>
            <p className="welcome-description">
              Tus documentos tienen respuestas.
              <br />
              Encuéntralas con preguntas, no con horas de lectura.
            </p>
            <div className={"dropzone " + (dragging ? "dragging" : "")}>
              <div className="upload-art">
                <div className="paper-back" />
                <div className="paper-front">
                  <FileText size={29} />
                  <i />
                  <i />
                  <i />
                </div>
                <span className="sparkle-art">
                  <Sparkles size={18} />
                </span>
              </div>
              <h2>
                {busy
                  ? "Preparando tu documento…"
                  : loading
                    ? "Abriendo tu biblioteca…"
                    : "Tu próxima respuesta empieza aquí."}
              </h2>
              <p>Arrastra un PDF o selecciónalo desde tu equipo.</p>
              <button
                className="primary"
                disabled={lock}
                onClick={() => upload.current?.click()}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Upload size={17} />
                )}{" "}
                Subir mi documento
              </button>
              <small>PDF con texto · Hasta 8 MB · Máximo 100 páginas</small>
            </div>
            <div className="sample-cta">
              <span>
                <BookOpen size={17} /> ¿Solo estás explorando?
              </span>
              <button onClick={useSample} disabled={lock}>
                Prueba con nuestra guía de ejemplo <ArrowUpRight size={15} />
              </button>
            </div>
            <div className="feature-row">
              <div>
                <MessageSquare size={17} />
                <span>Pregunta con naturalidad</span>
              </div>
              <div>
                <Search size={17} />
                <span>Encuentra el contexto</span>
              </div>
              <div>
                <Layers size={17} />
                <span>Verifica cada fuente</span>
              </div>
            </div>
            <p className="demo-note">
              {mode === "demo"
                ? "Modo demo: búsqueda por palabras y fragmentos literales, sin IA generativa."
                : "Modo IA: el texto del PDF y tus preguntas se envían a OpenAI."}
            </p>
          </section>
        ) : (
          <>
            <section className="document-header">
              <div className="document-breadcrumb">
                <span className="eyebrow">ESPACIO DE LECTURA</span>
                <span className="ready">
                  <Check size={12} /> Documento listo
                </span>
              </div>
              <div className="document-heading">
                <div>
                  <h1>{doc.name.replace(/\.pdf$/i, "")}</h1>
                  <p>
                    <FileText size={13} />
                    {doc.pages} páginas <span>·</span>
                    {doc.chunk_count} fragmentos <span>·</span>
                    {doc.mode === "demo"
                      ? "Índice local"
                      : "Embeddings semánticos"}
                  </p>
                </div>
                <div className="document-actions">
                  <button
                    className="outline mobile-source"
                    onClick={() => setShowSource(true)}
                  >
                    <BookOpen size={15} /> Fuente
                  </button>
                  <a
                    className="outline"
                    href={`/api/documents/${doc.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ArrowUpRight size={15} />
                    <span>Abrir PDF</span>
                  </a>
                  <button
                    className="icon-button"
                    aria-label="Eliminar documento"
                    disabled={lock}
                    onClick={() => setConfirmDelete(true)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </section>
            <div className="reading-layout">
              <section className="conversation">
                <div className="section-title">
                  <span>
                    <MessageSquare size={15} /> Conversación
                  </span>
                  <span className="subtle">
                    {mode === "demo" ? "DEMO EXTRACTIVA" : "RESPUESTAS CON IA"}
                  </span>
                </div>
                <div className="message-scroll">
                  {historyLoading ? (
                    <div className="chat-empty">
                      <LoaderCircle className="spin" /> Cargando conversación…
                    </div>
                  ) : !messages.length && !pending ? (
                    <div className="chat-empty">
                      <div className="chat-symbol">
                        <Sparkles size={25} />
                      </div>
                      <h2>Abre una nueva perspectiva.</h2>
                      <p>
                        Pregunta sobre el documento y encuentra
                        <br />
                        respuestas con fuentes que puedes revisar.
                      </p>
                      {doc.name.includes("Nébula") && (
                        <div className="suggestions">
                          {suggestions.map((s) => (
                            <button
                              key={s}
                              onClick={() => void ask(s)}
                              disabled={lock}
                            >
                              {s}
                              <ArrowUpRight size={14} />
                            </button>
                          ))}
                        </div>
                      )}
                      <small>
                        Una pregunta completa por turno.
                        <br />
                        Las preguntas anteriores no se usan como contexto.
                      </small>
                    </div>
                  ) : (
                    messages.map((m) => (
                      <article className="exchange" key={m.id}>
                        <div className="user-message">
                          <span className="user-label">TÚ</span>
                          <p>{m.question}</p>
                        </div>
                        <div className="assistant-message">
                          <span className="assistant-symbol">
                            <Sparkles size={17} />
                          </span>
                          <div>
                            <div className="answer-label">
                              DOCUMIND{" "}
                              <span>
                                {m.mode === "demo"
                                  ? "FRAGMENTOS DEL DOCUMENTO"
                                  : "IA · FUENTES VERIFICADAS"}
                              </span>
                            </div>
                            <p
                              className={
                                "answer " + (!m.supported ? "refusal" : "")
                              }
                            >
                              {m.answer}
                            </p>
                            {!!m.citations.length && (
                              <>
                                <div className="sources-label">
                                  CONSULTAR FUENTES
                                </div>
                                <div className="citation-list">
                                  {m.citations.map((ref, i) => (
                                    <button
                                      key={i}
                                      aria-label={`Ver fuente ${i + 1}, página ${ref.page}`}
                                      onClick={() => source(ref)}
                                      title={ref.quote}
                                    >
                                      <FileText size={12} />
                                      <span>{i + 1}</span>Pág. {ref.page}
                                      <ArrowUpRight size={12} />
                                    </button>
                                  ))}
                                </div>
                              </>
                            )}
                            <span className="answer-footer">
                              {m.supported ? (
                                <>
                                  <Check size={11} /> Citas contrastadas con el
                                  PDF
                                </>
                              ) : (
                                <>Sin respaldo suficiente en este documento</>
                              )}
                            </span>
                          </div>
                        </div>
                      </article>
                    ))
                  )}
                  {pending && (
                    <article className="exchange">
                      <div className="user-message">
                        <span className="user-label">TÚ</span>
                        <p>{pending}</p>
                      </div>
                      <div className="answer-loading" role="status">
                        <LoaderCircle size={17} className="spin" /> Buscando en
                        tu documento…
                      </div>
                    </article>
                  )}
                  <div ref={bottom} />
                </div>
                <form
                  className="composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void ask();
                  }}
                >
                  <label className="sr-only" htmlFor="question">
                    Pregunta sobre el documento
                  </label>
                  <div>
                    <textarea
                      id="question"
                      ref={input}
                      placeholder="¿Qué te gustaría saber del documento?"
                      rows={2}
                      maxLength={600}
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      disabled={lock}
                      onKeyDown={(e) => {
                        if (
                          e.key === "Enter" &&
                          !e.shiftKey &&
                          !e.nativeEvent.isComposing
                        ) {
                          e.preventDefault();
                          void ask();
                        }
                      }}
                    />
                    <button
                      className="send"
                      aria-label="Enviar pregunta"
                      disabled={lock || question.trim().length < 5}
                    >
                      {busy ? (
                        <LoaderCircle size={17} className="spin" />
                      ) : (
                        <ArrowUp size={19} />
                      )}
                    </button>
                  </div>
                  <p>
                    <ShieldCheck size={11} />
                    {mode === "demo"
                      ? "Demo local. Los fragmentos relacionados pueden no responder toda la pregunta."
                      : "Verifica las citas: la IA puede cometer errores."}
                    <span>{question.length}/600</span>
                  </p>
                </form>
              </section>
              <aside
                className={
                  "source-panel " + (showSource ? "source-visible" : "")
                }
                aria-label="Fuente del documento"
              >
                <div className="section-title">
                  <span>
                    <BookOpen size={15} /> Documento fuente
                  </span>
                  <button
                    className="source-close"
                    aria-label="Cerrar fuente"
                    onClick={() => setShowSource(false)}
                  >
                    <X size={17} />
                  </button>
                  <span className="subtle desktop-only">TEXTO EXTRAÍDO</span>
                </div>
                <div className="source-toolbar">
                  <span>
                    <FileText size={13} /> Vista de texto
                  </span>
                  <div>
                    <button
                      aria-label="Página anterior"
                      disabled={page <= 1}
                      onClick={() => {
                        setCitation(null);
                        setPage(page - 1);
                      }}
                    >
                      <ChevronLeft size={15} />
                    </button>
                    <span>
                      {page} / {doc.pages}
                    </span>
                    <button
                      aria-label="Página siguiente"
                      disabled={page >= doc.pages}
                      onClick={() => {
                        setCitation(null);
                        setPage(page + 1);
                      }}
                    >
                      <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
                <div className="source-scroll">
                  <div className="source-paper">
                    <span className="source-paper-brand">
                      DOCUMIND / FUENTE ORIGINAL
                    </span>
                    <h2>Página {page.toString().padStart(2, "0")}</h2>
                    <div className="paper-rule" />
                    <p>{sourceLoading ? "Cargando página…" : highlighted()}</p>
                    <div className="paper-page">{page}</div>
                  </div>
                  <div className="source-tip">
                    <span className="highlight-dot" />
                    <p>
                      {citation
                        ? "El fragmento citado aparece resaltado. Compáralo con la respuesta."
                        : "Selecciona una cita para localizar el fragmento en su página."}
                    </p>
                  </div>
                </div>
                <div className="source-footer">
                  <ShieldCheck size={13} /> La página proviene del PDF. Las
                  citas se validan literalmente.
                </div>
              </aside>
            </div>
          </>
        )}
      </main>
      {confirmDelete && doc && (
        <div className="overlay">
          <section
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <Trash2 size={25} />
            <h2 id="delete-title">¿Eliminar este documento?</h2>
            <p>Se borrarán el PDF, su índice y su conversación.</p>
            <div>
              <button
                className="outline"
                onClick={() => setConfirmDelete(false)}
              >
                Cancelar
              </button>
              <button
                className="danger"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    await request(`/documents/${doc.id}`, { method: "DELETE" });
                    setDocuments((ds) => ds.filter((d) => d.id !== doc.id));
                    setSelected(null);
                    setConfirmDelete(false);
                  })
                }
              >
                Eliminar documento
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
