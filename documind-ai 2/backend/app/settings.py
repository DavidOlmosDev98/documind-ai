from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    mode: str = "demo"
    database_url: str = ""
    api_key: str = ""
    model: str = "gpt-4.1-mini"
    web_origin: str = "http://localhost:5175"

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        mode = os.getenv("AI_MODE", "demo")
        if mode not in ("demo", "openai"):
            raise ValueError("AI_MODE debe ser demo u openai.")
        return cls(
            Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve(),
            mode,
            os.getenv("DATABASE_URL", ""),
            os.getenv("OPENAI_API_KEY", ""),
            os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            os.getenv("WEB_ORIGIN", "http://localhost:5175"),
        )
