"""SQLite for local use, PostgreSQL/pgvector for the optional vector backend."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, data_dir: Path, database_url: str = ""):
        self.directory, self.database_url = data_dir, database_url
        data_dir.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        if self.database_url:
            import psycopg

            connection = psycopg.connect(self.database_url)
        else:
            connection = sqlite3.connect(self.directory / "documind.db", timeout=15)
            connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, payload TEXT NOT NULL)"
            )
            if self.database_url:
                db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS chunks (document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, chunk_id INTEGER NOT NULL, embedding vector(1536) NOT NULL, PRIMARY KEY(document_id, chunk_id))"
                )

    def query(self, sql):
        return sql.replace("?", "%s") if self.database_url else sql

    def list_documents(self):
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM documents").fetchall()
        return sorted(
            [json.loads(row[0]) for row in rows],
            key=lambda d: d["created_at"],
            reverse=True,
        )

    def get(self, document_id):
        with self.connection() as db:
            row = db.execute(
                self.query("SELECT payload FROM documents WHERE id=?"), (document_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, document):
        with self.connection() as db:
            db.execute(
                self.query("INSERT INTO documents (id,payload) VALUES (?,?)"),
                (document["id"], json.dumps(document)),
            )
            if self.database_url and document["mode"] == "openai":
                for chunk in document["chunks"]:
                    db.execute(
                        "INSERT INTO chunks (document_id,chunk_id,embedding) VALUES (%s,%s,%s::vector)",
                        (document["id"], chunk["id"], json.dumps(chunk["embedding"])),
                    )

    def vector_search(self, document_id, embedding, limit=5):
        with self.connection() as db:
            rows = db.execute(
                "SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score FROM chunks WHERE document_id=%s ORDER BY embedding <=> %s::vector LIMIT %s",
                (json.dumps(embedding), document_id, json.dumps(embedding), limit),
            ).fetchall()
        return [(row[0], float(row[1])) for row in rows]

    def history(self, document_id):
        with self.connection() as db:
            rows = db.execute(
                self.query("SELECT payload FROM messages WHERE document_id=?"),
                (document_id,),
            ).fetchall()
        return sorted(
            [json.loads(row[0]) for row in rows], key=lambda m: m["created_at"]
        )

    def add_message(self, message):
        with self.connection() as db:
            db.execute(
                self.query(
                    "INSERT INTO messages (id,document_id,payload) VALUES (?,?,?)"
                ),
                (message["id"], message["document_id"], json.dumps(message)),
            )

    def delete(self, document_id):
        with self.connection() as db:
            db.execute(self.query("DELETE FROM documents WHERE id=?"), (document_id,))
