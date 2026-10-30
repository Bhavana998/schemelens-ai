"""
SQLite Persistent Storage Layer for SchemeLens AI.
Implements parameterized queries, strict schema isolation between drafts and approved records,
versioning, and immutable audit logs.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from src.models.schemas import (
    ApprovedScheme,
    DocumentContent,
    ExtractedPage,
    ReviewAuditEntry,
    ReviewStatus,
    SchemeDraft,
    SchemeFieldRecord,
)


class DatabaseManager:
    """
    Manages SQLite database connection, table initialization, and parameterized CRUD operations.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.db_path = base_dir / "data" / "schemelens.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_tables()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """Creates tables with strict schemas if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Documents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    total_pages INTEGER NOT NULL,
                    raw_full_text TEXT NOT NULL,
                    pages_json TEXT NOT NULL,
                    ocr_applied INTEGER NOT NULL DEFAULT 0,
                    ocr_warning TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Scheme Drafts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheme_drafts (
                    id TEXT PRIMARY KEY,
                    scheme_name TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    review_status TEXT NOT NULL DEFAULT 'draft',
                    source_document_ids_json TEXT NOT NULL,
                    fields_json TEXT NOT NULL,
                    has_conflicts INTEGER NOT NULL DEFAULT 0,
                    missing_fields_count INTEGER NOT NULL DEFAULT 0,
                    unverified_evidence_count INTEGER NOT NULL DEFAULT 0,
                    processing_metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 3. Approved Schemes Table (Isolated from drafts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheme_approved (
                    id TEXT NOT NULL,
                    draft_id TEXT NOT NULL,
                    scheme_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    fields_json TEXT NOT NULL,
                    reviewer_notes TEXT,
                    audit_hash TEXT NOT NULL,
                    PRIMARY KEY (id, version)
                )
            """)

            # 4. Review Audit Log Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_audit_log (
                    id TEXT PRIMARY KEY,
                    scheme_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details_json TEXT
                )
            """)

            conn.commit()

    # --- Document Operations ---

    def save_document(self, doc: DocumentContent):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            pages_data = [p.model_dump() for p in doc.pages]
            cursor.execute("""
                INSERT OR REPLACE INTO documents (
                    document_id, filename, file_hash, total_pages, raw_full_text,
                    pages_json, ocr_applied, ocr_warning, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc.document_id,
                doc.filename,
                doc.file_hash,
                doc.total_pages,
                doc.raw_full_text,
                json.dumps(pages_data, ensure_ascii=False),
                1 if doc.ocr_applied else 0,
                doc.ocr_warning,
                json.dumps(doc.metadata, ensure_ascii=False)
            ))
            conn.commit()

    def get_document(self, document_id: str) -> Optional[DocumentContent]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
            row = cursor.fetchone()
            if not row:
                return None

            pages_raw = json.loads(row["pages_json"])
            pages = [ExtractedPage(**p) for p in pages_raw]
            metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

            return DocumentContent(
                document_id=row["document_id"],
                filename=row["filename"],
                file_hash=row["file_hash"],
                total_pages=row["total_pages"],
                pages=pages,
                raw_full_text=row["raw_full_text"],
                ocr_applied=bool(row["ocr_applied"]),
                ocr_warning=row["ocr_warning"],
                metadata=metadata
            )

    def list_documents(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT document_id, filename, file_hash, total_pages, ocr_applied, created_at FROM documents ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --- Draft Operations ---

    def save_draft(self, draft: SchemeDraft):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fields_dict = {k: v.model_dump() for k, v in draft.fields.items()}

            status_val = draft.review_status.value if hasattr(draft.review_status, "value") else str(draft.review_status)
            if "." in status_val:
                status_val = status_val.split(".")[-1]
            status_val = status_val.lower()

            cursor.execute("""
                INSERT OR REPLACE INTO scheme_drafts (
                    id, scheme_name, version, review_status, source_document_ids_json,
                    fields_json, has_conflicts, missing_fields_count, unverified_evidence_count,
                    processing_metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                draft.id,
                draft.scheme_name,
                draft.version,
                status_val,
                json.dumps(draft.source_document_ids, ensure_ascii=False),
                json.dumps(fields_dict, ensure_ascii=False),
                1 if draft.has_conflicts else 0,
                draft.missing_fields_count,
                draft.unverified_evidence_count,
                json.dumps(draft.processing_metadata, ensure_ascii=False),
                draft.created_at,
                draft.updated_at
            ))
            conn.commit()

    def get_draft(self, draft_id: str) -> Optional[SchemeDraft]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheme_drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()
            if not row:
                return None

            fields_raw = json.loads(row["fields_json"])
            fields = {k: SchemeFieldRecord(**v) for k, v in fields_raw.items()}
            source_ids = json.loads(row["source_document_ids_json"])
            metadata = json.loads(row["processing_metadata_json"]) if row["processing_metadata_json"] else {}

            raw_status = row["review_status"]
            if hasattr(raw_status, "value"):
                raw_status = raw_status.value
            elif "." in str(raw_status):
                raw_status = str(raw_status).split(".")[-1]
            raw_status = str(raw_status).lower()

            try:
                status_enum = ReviewStatus(raw_status)
            except Exception:
                status_enum = ReviewStatus.DRAFT

            return SchemeDraft(
                id=row["id"],
                scheme_name=row["scheme_name"],
                version=row["version"],
                review_status=status_enum,
                source_document_ids=source_ids,
                fields=fields,
                has_conflicts=bool(row["has_conflicts"]),
                missing_fields_count=row["missing_fields_count"],
                unverified_evidence_count=row["unverified_evidence_count"],
                processing_metadata=metadata,
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def list_drafts(self, review_status: Optional[str] = None) -> List[SchemeDraft]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if review_status:
                status_filter = review_status.value if hasattr(review_status, "value") else str(review_status)
                if "." in status_filter:
                    status_filter = status_filter.split(".")[-1]
                status_filter = status_filter.lower()
                cursor.execute("SELECT id FROM scheme_drafts WHERE LOWER(review_status) = ? ORDER BY updated_at DESC", (status_filter,))
            else:
                cursor.execute("SELECT id FROM scheme_drafts ORDER BY updated_at DESC")

            rows = cursor.fetchall()
            return [self.get_draft(row["id"]) for row in rows if self.get_draft(row["id"]) is not None]

    # --- Approved Scheme Operations ---

    def save_approved_scheme(self, approved: ApprovedScheme):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fields_dict = {k: v.model_dump() for k, v in approved.fields.items()}

            cursor.execute("""
                INSERT INTO scheme_approved (
                    id, draft_id, scheme_name, version, approved_by, approved_at,
                    fields_json, reviewer_notes, audit_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                approved.id,
                approved.draft_id,
                approved.scheme_name,
                approved.version,
                approved.approved_by,
                approved.approved_at,
                json.dumps(fields_dict, ensure_ascii=False),
                approved.reviewer_notes,
                approved.audit_hash
            ))
            conn.commit()

    def get_latest_approved_version(self, scheme_id: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) as max_v FROM scheme_approved WHERE id = ?", (scheme_id,))
            row = cursor.fetchone()
            return row["max_v"] if row and row["max_v"] is not None else 0

    def list_approved_schemes(self) -> List[ApprovedScheme]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Select latest version for each approved scheme
            cursor.execute("""
                SELECT sa.* FROM scheme_approved sa
                INNER JOIN (
                    SELECT id, MAX(version) as max_v
                    FROM scheme_approved
                    GROUP BY id
                ) latest ON sa.id = latest.id AND sa.version = latest.max_v
                ORDER BY sa.approved_at DESC
            """)
            rows = cursor.fetchall()
            approved_list = []
            for row in rows:
                fields_raw = json.loads(row["fields_json"])
                fields = {k: SchemeFieldRecord(**v) for k, v in fields_raw.items()}
                approved_list.append(
                    ApprovedScheme(
                        id=row["id"],
                        draft_id=row["draft_id"],
                        scheme_name=row["scheme_name"],
                        version=row["version"],
                        approved_by=row["approved_by"],
                        approved_at=row["approved_at"],
                        fields=fields,
                        reviewer_notes=row["reviewer_notes"],
                        audit_hash=row["audit_hash"]
                    )
                )
            return approved_list

    # --- Audit Trail Operations ---

    def log_audit_entry(self, entry: ReviewAuditEntry):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO review_audit_log (
                    id, scheme_id, action, actor, timestamp, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.scheme_id,
                entry.action,
                entry.actor,
                entry.timestamp,
                json.dumps(entry.details, ensure_ascii=False)
            ))
            conn.commit()

    def get_audit_trail(self, scheme_id: str) -> List[ReviewAuditEntry]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM review_audit_log
                WHERE scheme_id = ?
                ORDER BY rowid DESC
            """, (scheme_id,))
            rows = cursor.fetchall()
            return [
                ReviewAuditEntry(
                    id=row["id"],
                    scheme_id=row["scheme_id"],
                    action=row["action"],
                    actor=row["actor"],
                    timestamp=row["timestamp"],
                    details=json.loads(row["details_json"]) if row["details_json"] else {}
                )
                for row in rows
            ]
