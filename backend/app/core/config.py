"""Environment-based configuration."""

import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


def _resolve_data_dir(
    configured: str | None = None,
    *,
    project_dir: Path = PROJECT_DIR,
    backend_dir: Path = BACKEND_DIR,
    cwd: Path | None = None,
) -> Path:
    if not configured:
        return (project_dir / "data" / "dataset").resolve()

    path = Path(configured).expanduser()
    if path.is_absolute():
        return path.resolve()

    working_directory = (cwd or Path.cwd()).resolve()
    candidates = [
        (working_directory / path).resolve(),
        (project_dir / path).resolve(),
        (backend_dir / path).resolve(),
    ]
    for candidate in candidates:
        if (candidate / "companies.csv").is_file():
            if candidate != candidates[0]:
                LOGGER.warning(
                    "Resolved relative CASHFLOW_DATA_DIR=%r to %s because the dataset was not found relative to the working directory.",
                    configured,
                    candidate,
                )
            return candidate
    return candidates[0]


DATA_DIR = _resolve_data_dir(os.getenv("CASHFLOW_DATA_DIR"))
DATABASE_PATH = Path(os.getenv("CASHFLOW_DATABASE", BACKEND_DIR / "data" / "cashflow.sqlite3")).expanduser().resolve()
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CASHFLOW_FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
