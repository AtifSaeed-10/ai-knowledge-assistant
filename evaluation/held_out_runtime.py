"""
Isolated index + evidence runtime for the held-out handbook.

Keeps embeddings, SQLite, and PDFs out of the live app corpus. Localization
uses production mapping against the generated PDF; retrieval uses production
ask_question against this isolated Chroma collection.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

import chromadb

from database.db import get_connection, init_db
from database.document_store import get_document
from evaluation.held_out_handbook import (
    HELD_OUT_DOCUMENT_ID,
    HELD_OUT_PDF_NAME,
    HELD_OUT_VERSION,
    write_held_out_pdf,
)
from evaluation.run_real_document_eval import (
    MODE_LOCALIZATION,
    EvalCorpus,
    RealDocumentCase,
    prepare_eval_document,
    run_evaluation,
)

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
HELD_OUT_STORE = RESULTS_DIR / "held_out"
STAMP_NAME = "stamp.json"


@dataclass
class HeldOutRuntime:
    document_id: str
    pdf_path: str
    corpus: EvalCorpus
    chroma_path: str
    sqlite_path: str
    indexed: bool


def _pdf_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(HELD_OUT_VERSION.encode("utf-8"))
    digest.update(b"\n")
    digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_fixed_document(document_id: str, filename: str) -> None:
    init_db()
    if get_document(document_id):
        return
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO documents
        (document_id, filename, upload_time, total_pages, total_chunks)
        VALUES (?, ?, ?, ?, ?)
        """,
        (document_id, filename, datetime.now().isoformat(), 0, 0),
    )
    connection.commit()
    connection.close()


def _stamp_path() -> Path:
    return HELD_OUT_STORE / STAMP_NAME


def _read_stamp() -> dict[str, Any] | None:
    path = _stamp_path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _write_stamp(payload: dict[str, Any]) -> None:
    HELD_OUT_STORE.mkdir(parents=True, exist_ok=True)
    _stamp_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _index_is_current(pdf_path: Path, chroma_path: str) -> bool:
    stamp = _read_stamp()
    if not stamp:
        return False
    if stamp.get("fingerprint") != _pdf_fingerprint(pdf_path):
        return False
    if stamp.get("document_id") != HELD_OUT_DOCUMENT_ID:
        return False
    row = get_document(HELD_OUT_DOCUMENT_ID)
    if not row or str(row.get("status") or "") != "ready":
        return False
    from config import COLLECTION_NAME

    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return int(collection.count() or 0) > 0


def _index_handbook(pdf_path: Path, stored_pdf: Path, chroma_path: str) -> None:
    from indexer import index_pdf

    index_pdf(str(stored_pdf), HELD_OUT_DOCUMENT_ID)
    _write_stamp(
        {
            "fingerprint": _pdf_fingerprint(pdf_path),
            "document_id": HELD_OUT_DOCUMENT_ID,
            "chroma_path": chroma_path,
            "pdf_path": str(pdf_path),
        }
    )


@contextmanager
def held_out_eval_environment(*, index: bool = True) -> Iterator[HeldOutRuntime]:
    """
    Point SQLite, Chroma, and DATA_DIR at evaluation/results/held_out/.

    Live app data/chroma_db are not written.
    """
    import document_paths
    import index_hygiene
    import indexer
    import rag
    from bm25_index import bm25_index
    from config import COLLECTION_NAME
    from document_paths import stored_pdf_path

    HELD_OUT_STORE.mkdir(parents=True, exist_ok=True)
    sqlite_path = str(HELD_OUT_STORE / "eval.db")
    chroma_path = str(HELD_OUT_STORE / "chroma")
    data_dir = str(HELD_OUT_STORE / "data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    Path(chroma_path).mkdir(parents=True, exist_ok=True)

    pdf_path = write_held_out_pdf()
    eval_client = chromadb.PersistentClient(path=chroma_path)

    def _get_collection():
        return eval_client.get_or_create_collection(name=COLLECTION_NAME)

    with ExitStack() as stack:
        stack.enter_context(patch("database.db.SQLITE_DB_PATH", sqlite_path))
        stack.enter_context(patch.object(indexer, "CHROMA_DB_PATH", chroma_path))
        stack.enter_context(patch.object(index_hygiene, "CHROMA_DB_PATH", chroma_path))
        stack.enter_context(patch.object(document_paths, "DATA_DIR", data_dir))
        stack.enter_context(patch.object(rag, "client", eval_client))
        stack.enter_context(patch.object(rag, "CHROMA_DB_PATH", chroma_path))
        stack.enter_context(patch.object(rag, "get_collection", _get_collection))
        init_db()
        ensure_fixed_document(HELD_OUT_DOCUMENT_ID, HELD_OUT_PDF_NAME)
        stored = stored_pdf_path(HELD_OUT_DOCUMENT_ID, must_exist=False)
        if not stored:
            raise RuntimeError("held-out DATA_DIR is not writable")
        shutil.copy2(pdf_path, stored)
        indexed = False
        if index:
            if not _index_is_current(pdf_path, chroma_path):
                _index_handbook(pdf_path, Path(stored), chroma_path)
            indexed = True
            bm25_index.invalidate()
        corpus = prepare_eval_document(
            pdf_path,
            document_id=HELD_OUT_DOCUMENT_ID,
            filename=HELD_OUT_PDF_NAME,
        )
        yield HeldOutRuntime(
            document_id=HELD_OUT_DOCUMENT_ID,
            pdf_path=str(pdf_path),
            corpus=corpus,
            chroma_path=chroma_path,
            sqlite_path=sqlite_path,
            indexed=indexed,
        )


def cases_use_held_out(cases: list[RealDocumentCase]) -> bool:
    return any(case.document_id == HELD_OUT_DOCUMENT_ID for case in cases)


def run_held_out_evaluation(
    cases: list[RealDocumentCase],
    *,
    index: bool = True,
    mode: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    with held_out_eval_environment(index=index) as runtime:
        report = run_evaluation(
            cases,
            mode=mode or MODE_LOCALIZATION,
            corpus=runtime.corpus,
            limit=limit,
        )
    return asdict(report)
