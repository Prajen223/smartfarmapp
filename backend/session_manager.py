"""Session management and persistent conversation history for Smart Farming Assistant.

Milestone 3 – Part 1 Implementation:
  • Persistent SQLite database storage for farmer sessions and conversation messages.
  • Unique UUID4 session identifiers.
  • Anonymous and farmer_id-associated session tracking.
  • Chronological message storage for user questions and assistant responses.
  • Multi-turn conversational context resolution and entity tracking across turns.
  • Idle session expiration tracking (SESSION_TTL_SECONDS).
  • High-performance thread-safe concurrent session management.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS: int = 10          # maximum conversation turns retained in memory cache
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # default 1 hour idle expiry
DEFAULT_DB_PATH: Path = Path(__file__).parent / "data" / "farm_sessions.db"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ConversationTurn:
    """A single question-answer exchange with timestamp and entity context."""
    turn_number: int
    user_text: str          # raw farmer question
    detected_language: str  # e.g. "en", "ta", "hi", "kn"
    intent: str
    answer_summary: str     # first 200 chars of the answer
    entities: dict          # NER result for this turn
    timestamp: float = field(default_factory=time.time)
    iso_timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


@dataclass
class ConversationMessage:
    """Individual message record stored chronologically in the database."""
    message_id: str
    session_id: str
    role: str               # "user" or "assistant"
    content: str
    language: str = "en"
    intent: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    sources: Optional[list[str]] = None
    entities: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "language": self.language,
            "intent": self.intent,
            "created_at": self.created_at,
            "sources": self.sources or [],
            "entities": self.entities or {},
            "confidence": self.confidence,
        }


@dataclass
class FarmerSession:
    """Farmer dialogue session model supporting anonymous & registered farmer access."""
    session_id: str
    farmer_id: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    language: str = "en"
    is_active: bool = True
    context_metadata: dict[str, Any] = field(default_factory=dict)

    # In-memory transient & cached fields for backward compatibility
    history: list[ConversationTurn] = field(default_factory=list)
    preferred_language: Optional[str] = None
    last_active: float = field(default_factory=time.time)

    @property
    def turn_count(self) -> int:
        return len(self.history)

    # Entity tracking properties mapped to context_metadata
    @property
    def active_crop(self) -> Optional[str]:
        return self.context_metadata.get("active_crop")

    @active_crop.setter
    def active_crop(self, value: Optional[str]) -> None:
        self.context_metadata["active_crop"] = value

    @property
    def active_soil(self) -> Optional[str]:
        return self.context_metadata.get("active_soil")

    @active_soil.setter
    def active_soil(self, value: Optional[str]) -> None:
        self.context_metadata["active_soil"] = value

    @property
    def active_pest(self) -> Optional[str]:
        return self.context_metadata.get("active_pest")

    @active_pest.setter
    def active_pest(self, value: Optional[str]) -> None:
        self.context_metadata["active_pest"] = value

    @property
    def active_disease(self) -> Optional[str]:
        return self.context_metadata.get("active_disease")

    @active_disease.setter
    def active_disease(self, value: Optional[str]) -> None:
        self.context_metadata["active_disease"] = value

    @property
    def active_scheme(self) -> Optional[str]:
        return self.context_metadata.get("active_scheme")

    @active_scheme.setter
    def active_scheme(self, value: Optional[str]) -> None:
        self.context_metadata["active_scheme"] = value

    @property
    def active_season(self) -> Optional[str]:
        return self.context_metadata.get("active_season")

    @active_season.setter
    def active_season(self, value: Optional[str]) -> None:
        self.context_metadata["active_season"] = value

    @property
    def active_nutrient(self) -> Optional[str]:
        return self.context_metadata.get("active_nutrient")

    @active_nutrient.setter
    def active_nutrient(self, value: Optional[str]) -> None:
        self.context_metadata["active_nutrient"] = value

    @property
    def active_fertilizer(self) -> Optional[str]:
        return self.context_metadata.get("active_fertilizer")

    @active_fertilizer.setter
    def active_fertilizer(self, value: Optional[str]) -> None:
        self.context_metadata["active_fertilizer"] = value

    @property
    def created_at_iso(self) -> str:
        return self.created_at

    @property
    def detected_language_code(self) -> str:
        return self.context_metadata.get("detected_language_code", "und")

    @detected_language_code.setter
    def detected_language_code(self, val: str) -> None:
        self.context_metadata["detected_language_code"] = val
        self.language = val

    def touch(self) -> None:
        self.last_active = time.time()
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def add_turn(self, turn: ConversationTurn) -> None:
        """Append a turn, evicting the oldest from memory cache if history exceeds limit."""
        self.history.append(turn)
        if len(self.history) > MAX_HISTORY_TURNS:
            self.history = self.history[-MAX_HISTORY_TURNS:]

        entities = turn.entities or {}
        if entities.get("crops"):
            self.active_crop = entities["crops"][0]
        if entities.get("soil"):
            self.active_soil = entities["soil"][0]
        if entities.get("pests"):
            self.active_pest = entities["pests"][0]
        if entities.get("diseases"):
            self.active_disease = entities["diseases"][0]
        if entities.get("schemes"):
            self.active_scheme = entities["schemes"][0]
        if entities.get("seasons"):
            self.active_season = entities["seasons"][0]
        if entities.get("nutrients"):
            self.active_nutrient = entities["nutrients"][0]
        if entities.get("fertilizers"):
            self.active_fertilizer = entities["fertilizers"][0]
        elif turn.intent == "crop_advisory" and any(
            kw in turn.user_text.lower() for kw in ("fertilizer", "manure", "urea", "dap", "npk", "compost")
        ):
            self.active_fertilizer = "fertilizer"

    def resolve_context(self, current_entities: dict) -> dict:
        """Resolve missing entities from prior conversation turns."""
        resolved = dict(current_entities)

        if not resolved.get("crops") and self.active_crop:
            resolved["crops"] = [self.active_crop]
            resolved["_crop_carried_from_context"] = True

        if not resolved.get("soil") and self.active_soil:
            resolved["soil"] = [self.active_soil]

        if not resolved.get("schemes") and self.active_scheme:
            resolved["schemes"] = [self.active_scheme]

        if not resolved.get("seasons") and self.active_season:
            resolved["seasons"] = [self.active_season]

        if not resolved.get("nutrients") and self.active_nutrient:
            resolved["nutrients"] = [self.active_nutrient]

        if not resolved.get("fertilizers") and self.active_fertilizer:
            resolved["fertilizers"] = [self.active_fertilizer]

        if not resolved.get("pests") and self.active_pest:
            resolved["pests"] = [self.active_pest]

        if not resolved.get("diseases") and self.active_disease:
            resolved["diseases"] = [self.active_disease]

        return resolved

    def get_context_summary(self) -> dict[str, Any]:
        """Return a lightweight context snapshot safe to include in responses."""
        return {
            "session_id": self.session_id,
            "farmer_id": self.farmer_id,
            "turn_count": len(self.history),
            "detected_language_code": self.detected_language_code,
            "preferred_language": self.preferred_language,
            "last_intent": self.history[-1].intent if self.history else None,
            "active_crop": self.active_crop,
            "active_soil": self.active_soil,
            "active_pest": self.active_pest,
            "active_disease": self.active_disease,
            "active_scheme": self.active_scheme,
            "active_season": self.active_season,
            "active_nutrient": self.active_nutrient,
            "active_fertilizer": self.active_fertilizer,
            "last_active": self.last_active,
            "is_active": self.is_active,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "farmer_id": self.farmer_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "language": self.language,
            "is_active": self.is_active,
            "context_summary": self.get_context_summary(),
        }


# Type alias for complete backward compatibility
Session = FarmerSession


# ---------------------------------------------------------------------------
# Session Manager (Persistent SQLite + In-Memory Thread-Safe Cache)
# ---------------------------------------------------------------------------

class SessionManager:
    """Production-grade session manager supporting SQLite persistence and thread-safe operations."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._lock = threading.RLock()
        self._store: dict[str, FarmerSession] = {}
        
        env_db = os.getenv("FARM_SESSIONS_DB_PATH")
        if db_path is not None:
            self.db_path = str(db_path)
        elif env_db:
            self.db_path = env_db
        else:
            self.db_path = str(DEFAULT_DB_PATH)

        self._is_memory = self.db_path == ":memory:"
        self._shared_memory_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._shared_memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared_memory_conn.row_factory = sqlite3.Row

        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Yield a database connection with auto-commit and cleanup."""
        if self._is_memory and self._shared_memory_conn is not None:
            yield self._shared_memory_conn
            self._shared_memory_conn.commit()
            return

        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except Exception:
            pass

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create the persistent relational schema if not already initialized."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS farmer_sessions (
                        session_id TEXT PRIMARY KEY,
                        farmer_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        language TEXT NOT NULL DEFAULT 'en',
                        is_active INTEGER NOT NULL DEFAULT 1,
                        context_metadata TEXT
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_messages (
                        message_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        language TEXT NOT NULL DEFAULT 'en',
                        intent TEXT,
                        created_at TEXT NOT NULL,
                        sources TEXT,
                        entities TEXT,
                        confidence REAL,
                        FOREIGN KEY (session_id) REFERENCES farmer_sessions(session_id) ON DELETE CASCADE
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS farmer_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        message_id TEXT NOT NULL UNIQUE,
                        rating TEXT NOT NULL CHECK(rating IN ('positive', 'negative')),
                        comment TEXT,
                        farmer_id TEXT,
                        language TEXT NOT NULL DEFAULT 'en',
                        intent TEXT,
                        query_text TEXT,
                        answer_text TEXT,
                        review_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (session_id) REFERENCES farmer_sessions(session_id) ON DELETE CASCADE
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON conversation_messages(session_id, created_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_farmer ON farmer_sessions(farmer_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON farmer_sessions(is_active);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_session ON farmer_feedback(session_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON farmer_feedback(rating);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created ON farmer_feedback(created_at);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_message ON farmer_feedback(message_id);")

    def create_session(
        self,
        farmer_id: Optional[str] = None,
        language: str = "en",
    ) -> FarmerSession:
        """Create and persist a new farmer session."""
        with self._lock:
            session_id = str(uuid.uuid4())
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            session = FarmerSession(
                session_id=session_id,
                farmer_id=farmer_id,
                created_at=now_iso,
                updated_at=now_iso,
                language=language or "en",
                is_active=True,
                context_metadata={},
                history=[],
                preferred_language=language if language != "en" else None,
                last_active=time.time(),
            )

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO farmer_sessions (
                        session_id, farmer_id, created_at, updated_at, language, is_active, context_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.farmer_id,
                        session.created_at,
                        session.updated_at,
                        session.language,
                        1 if session.is_active else 0,
                        json.dumps(session.context_metadata),
                    ),
                )

            self._store[session_id] = session
            return session

    def get_session(
        self,
        session_id: str,
        include_inactive: bool = False,
    ) -> Optional[FarmerSession]:
        """Retrieve a session by ID from memory cache or database, respecting expiration."""
        if not session_id:
            return None

        with self._lock:
            self._expire_stale_sessions()

            # 1. Check in-memory store
            if session_id in self._store:
                sess = self._store[session_id]
                if not sess.is_active and not include_inactive:
                    return None
                return sess

            # 2. Check persistent database
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT session_id, farmer_id, created_at, updated_at, language, is_active, context_metadata
                    FROM farmer_sessions WHERE session_id = ?
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                is_active = bool(row["is_active"])
                if not is_active and not include_inactive:
                    return None
                    return None

                updated_at = row["updated_at"]
                try:
                    dt = datetime.datetime.fromisoformat(updated_at)
                    last_active_epoch = dt.timestamp()
                except Exception:
                    last_active_epoch = time.time()

                # Check idle expiration
                if time.time() - last_active_epoch > SESSION_TTL_SECONDS:
                    self.deactivate_session(session_id)
                    return None

                ctx_meta = {}
                if row["context_metadata"]:
                    try:
                        ctx_meta = json.loads(row["context_metadata"])
                    except Exception:
                        ctx_meta = {}

                sess = FarmerSession(
                    session_id=row["session_id"],
                    farmer_id=row["farmer_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    language=row["language"] or "en",
                    is_active=is_active,
                    context_metadata=ctx_meta,
                    last_active=last_active_epoch,
                )

                # Reconstruct recent history from conversation messages
                cur.execute(
                    """
                    SELECT message_id, role, content, language, intent, created_at, entities
                    FROM conversation_messages
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """,
                    (session_id,),
                )
                msg_rows = cur.fetchall()
                turns: list[ConversationTurn] = []
                user_msg: Optional[dict] = None

                for mr in msg_rows:
                    if mr["role"] == "user":
                        user_msg = dict(mr)
                    elif mr["role"] == "assistant" and user_msg:
                        turn_ent = {}
                        if user_msg.get("entities"):
                            try:
                                turn_ent = json.loads(user_msg["entities"])
                            except Exception:
                                pass
                        turns.append(
                            ConversationTurn(
                                turn_number=len(turns) + 1,
                                user_text=user_msg["content"],
                                detected_language=user_msg["language"],
                                intent=user_msg["intent"] or "crop_advisory",
                                answer_summary=mr["content"][:200],
                                entities=turn_ent,
                                iso_timestamp=mr["created_at"],
                            )
                        )
                        user_msg = None

                sess.history = turns[-MAX_HISTORY_TURNS:]
                self._store[session_id] = sess
                return sess

    def get_or_create(
        self,
        session_id: Optional[str],
        farmer_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> FarmerSession:
        """Return an existing active session or create a new one."""
        with self._lock:
            self._expire_stale_sessions()

            if session_id:
                existing = self.get_session(session_id)
                if existing:
                    existing.touch()
                    self._persist_session(existing)
                    return existing

            return self.create_session(farmer_id=farmer_id, language=language or "en")

    def deactivate_session(self, session_id: str) -> bool:
        """Safely deactivate/close a farmer session."""
        with self._lock:
            sess = self._store.get(session_id)
            if sess:
                sess.is_active = False

            with self._get_connection() as conn:
                cur = conn.cursor()
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                cur.execute(
                    "UPDATE farmer_sessions SET is_active = 0, updated_at = ? WHERE session_id = ?",
                    (now_iso, session_id),
                )
                affected = cur.rowcount
                return affected > 0 or (sess is not None)

    def delete_session(self, session_id: str) -> bool:
        """Deactivate a session safely."""
        return self.deactivate_session(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        language: str = "en",
        intent: Optional[str] = None,
        sources: Optional[list[str]] = None,
        entities: Optional[dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> ConversationMessage:
        """Persist a conversation message in SQLite."""
        with self._lock:
            message_id = str(uuid.uuid4())
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            msg = ConversationMessage(
                message_id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                language=language,
                intent=intent,
                created_at=now_iso,
                sources=sources,
                entities=entities,
                confidence=confidence,
            )

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO conversation_messages (
                        message_id, session_id, role, content, language, intent, created_at, sources, entities, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.message_id,
                        msg.session_id,
                        msg.role,
                        msg.content,
                        msg.language,
                        msg.intent,
                        msg.created_at,
                        json.dumps(msg.sources) if msg.sources else None,
                        json.dumps(msg.entities) if msg.entities else None,
                        msg.confidence,
                    ),
                )

            return msg

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> list[ConversationMessage]:
        """Retrieve chronological message history for a session."""
        with self._lock:
            query = """
                SELECT message_id, session_id, role, content, language, intent, created_at, sources, entities, confidence
                FROM conversation_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
            """
            params: list[Any] = [session_id]
            if limit and limit > 0:
                query += " LIMIT ?"
                params.append(limit)

            messages: list[ConversationMessage] = []
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, tuple(params))
                for row in cur.fetchall():
                    sources = json.loads(row["sources"]) if row["sources"] else []
                    entities = json.loads(row["entities"]) if row["entities"] else {}
                    messages.append(
                        ConversationMessage(
                            message_id=row["message_id"],
                            session_id=row["session_id"],
                            role=row["role"],
                            content=row["content"],
                            language=row["language"] or "en",
                            intent=row["intent"],
                            created_at=row["created_at"],
                            sources=sources,
                            entities=entities,
                            confidence=row["confidence"],
                        )
                    )
            return messages

    def record_turn(
        self,
        session_id: str,
        user_text: str,
        detected_language: str,
        intent: str,
        answer: str,
        entities: dict,
        sources: Optional[list[str]] = None,
        confidence: Optional[float] = None,
    ) -> Optional[tuple[ConversationMessage, ConversationMessage]]:
        """Append a question-answer turn to session history and persist both messages."""
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return None

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 1. Store user message in database
            user_msg = self.add_message(
                session_id=session_id,
                role="user",
                content=user_text,
                language=detected_language,
                intent=intent,
                entities=entities,
            )

            # 2. Store assistant message in database
            asst_msg = self.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                language=detected_language,
                intent=intent,
                sources=sources or [],
                confidence=confidence,
            )

            # 3. Update session object
            turn = ConversationTurn(
                turn_number=len(session.history) + 1,
                user_text=user_text,
                detected_language=detected_language,
                intent=intent,
                answer_summary=answer[:200],
                entities=entities,
                iso_timestamp=now_iso,
            )
            session.add_turn(turn)
            session.detected_language_code = detected_language
            session.touch()

            self._persist_session(session)
            return (user_msg, asst_msg)

    def set_preferred_language(
        self,
        session_id: str,
        language_code: str,
    ) -> bool:
        """Set user's preferred language explicitly in memory and SQLite."""
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return False

            session.preferred_language = language_code
            session.language = language_code
            session.touch()
            self._persist_session(session)
            return True

    def session_count(self) -> int:
        """Return number of active sessions."""
        with self._lock:
            self._expire_stale_sessions()
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM farmer_sessions WHERE is_active = 1")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def clear_all(self) -> None:
        """Remove all sessions and messages (for testing)."""
        with self._lock:
            self._store.clear()
            with self._get_connection() as conn:
                conn.execute("DELETE FROM farmer_feedback;")
                conn.execute("DELETE FROM conversation_messages;")
                conn.execute("DELETE FROM farmer_sessions;")

    def _persist_session(self, session: FarmerSession) -> None:
        """Update session state in the persistent SQLite database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO farmer_sessions (
                    session_id, farmer_id, created_at, updated_at, language, is_active, context_metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    language = excluded.language,
                    is_active = excluded.is_active,
                    context_metadata = excluded.context_metadata
                """,
                (
                    session.session_id,
                    session.farmer_id,
                    session.created_at,
                    session.updated_at,
                    session.language,
                    1 if session.is_active else 0,
                    json.dumps(session.context_metadata),
                ),
            )

    def _expire_stale_sessions(self) -> None:
        """Evict sessions that have exceeded the idle inactivity threshold."""
        now = time.time()
        stale_sids = [
            sid for sid, sess in self._store.items()
            if (now - sess.last_active > SESSION_TTL_SECONDS) or not sess.is_active
        ]
        for sid in stale_sids:
            sess = self._store.pop(sid, None)
            if sess:
                try:
                    with self._get_connection() as conn:
                        conn.execute(
                            "UPDATE farmer_sessions SET is_active = 0 WHERE session_id = ?",
                            (sid,),
                        )
                except Exception as exc:
                    logger.warning("Error marking session %s expired in db: %s", sid, exc)

    def get_analytics_summary(self, days: int = 7) -> dict[str, Any]:
        """Aggregate platform usage, query statistics, language breakdown, and recent activity.

        Returns structured metrics for the Admin Dashboard without exposing private farmer PII.
        """
        days = max(1, min(90, days))
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        today_prefix = now_dt.strftime("%Y-%m-%d")
        start_date = (now_dt - datetime.timedelta(days=days - 1)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            # 1. Registered Farmers count
            try:
                total_farmers = conn.execute(
                    "SELECT count(*) FROM users WHERE role = 'farmer'"
                ).fetchone()[0]
            except Exception:
                total_farmers = 0

            # 2. Total & Active Sessions
            total_sessions = conn.execute(
                "SELECT count(*) FROM farmer_sessions"
            ).fetchone()[0]
            active_sessions = conn.execute(
                "SELECT count(*) FROM farmer_sessions WHERE is_active = 1"
            ).fetchone()[0]

            # 3. Total Queries (user messages)
            total_queries = conn.execute(
                "SELECT count(*) FROM conversation_messages WHERE role = 'user'"
            ).fetchone()[0]

            # 4. Today's Queries
            today_queries = conn.execute(
                "SELECT count(*) FROM conversation_messages WHERE role = 'user' AND created_at >= ?",
                (today_prefix,),
            ).fetchone()[0]

            # 5. Unanswered & Review Queue Queries + Farmer Feedback
            unanswered_queries = 0
            feedback_data = {
                "positive": 0,
                "negative": 0,
                "has_feedback_data": False,
                "satisfaction_rate": 0.0,
            }
            try:
                from review_manager import review_manager
                review_stats = review_manager.get_stats()
                unanswered_queries = review_stats.get("pending", 0)
                pos = review_stats.get("approved", 0)
                neg = review_stats.get("rejected", 0)
                feedback_data = {
                    "positive": pos,
                    "negative": neg,
                    "has_feedback_data": (pos + neg) > 0,
                    "satisfaction_rate": round((pos / (pos + neg)) * 100, 1) if (pos + neg) > 0 else 0.0,
                }
            except Exception as e:
                logger.warning("Could not fetch review stats for analytics: %s", e)

            # Query real farmer feedback table if present
            try:
                fb_row = conn.execute("""
                    SELECT 
                        count(*) AS total,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg
                    FROM farmer_feedback
                """).fetchone()
                if fb_row and fb_row["total"] and fb_row["total"] > 0:
                    fb_pos = fb_row["pos"] or 0
                    fb_neg = fb_row["neg"] or 0
                    feedback_data = {
                        "positive": fb_pos,
                        "negative": fb_neg,
                        "has_feedback_data": True,
                        "satisfaction_rate": round((fb_pos / (fb_pos + fb_neg)) * 100, 1) if (fb_pos + fb_neg) > 0 else 0.0,
                    }
            except Exception as e:
                logger.warning("Could not query farmer_feedback in get_analytics_summary: %s", e)

            # 6. Daily Usage Timeline over the requested days
            daily_map: dict[str, dict[str, Any]] = {}
            for i in range(days - 1, -1, -1):
                d_str = (now_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                daily_map[d_str] = {"date": d_str, "queries": 0, "sessions": 0}

            query_rows = conn.execute(
                """
                SELECT substr(created_at, 1, 10) AS day, count(*) AS count
                FROM conversation_messages
                WHERE role = 'user' AND created_at >= ?
                GROUP BY substr(created_at, 1, 10)
                ORDER BY day ASC
                """,
                (start_date,),
            ).fetchall()
            for r in query_rows:
                day_key = r["day"]
                if day_key in daily_map:
                    daily_map[day_key]["queries"] = r["count"]

            session_rows = conn.execute(
                """
                SELECT substr(created_at, 1, 10) AS day, count(*) AS count
                FROM farmer_sessions
                WHERE created_at >= ?
                GROUP BY substr(created_at, 1, 10)
                ORDER BY day ASC
                """,
                (start_date,),
            ).fetchall()
            for r in session_rows:
                day_key = r["day"]
                if day_key in daily_map:
                    daily_map[day_key]["sessions"] = r["count"]

            daily_usage = list(daily_map.values())

            # 7. Language Distribution
            lang_names = {
                "en": "English",
                "hi": "हिंदी (Hindi)",
                "kn": "ಕನ್ನಡ (Kannada)",
                "ta": "தமிழ் (Tamil)",
                "te": "తెలుగు (Telugu)",
                "mr": "मराठी (Marathi)",
                "gu": "ગુજરાતી (Gujarati)",
                "pa": "ਪੰਜਾਬੀ (Punjabi)",
                "bn": "বাংলা (Bengali)",
            }
            lang_rows = conn.execute(
                """
                SELECT language, count(*) AS count
                FROM conversation_messages
                WHERE role = 'user'
                GROUP BY language
                ORDER BY count DESC
                """
            ).fetchall()
            lang_dist = []
            for r in lang_rows:
                code = r["language"] or "en"
                c = r["count"]
                pct = round((c / total_queries * 100), 1) if total_queries > 0 else 0.0
                lang_dist.append({
                    "code": code,
                    "language": lang_names.get(code, code.upper()),
                    "count": c,
                    "percentage": pct,
                })

            # 8. Intent Distribution
            intent_labels = {
                "irrigation": "Irrigation Guidance",
                "crop_advisory": "Crop Advisory",
                "pest_control": "Pest & Disease Control",
                "market_prices": "Mandi Market Prices",
                "government_schemes": "Government Schemes",
                "weather": "Weather Forecast",
                "general": "General Inquiry",
            }
            intent_rows = conn.execute(
                """
                SELECT COALESCE(intent, 'general') AS intent_name, count(*) AS count
                FROM conversation_messages
                WHERE role = 'user'
                GROUP BY intent_name
                ORDER BY count DESC
                """
            ).fetchall()
            intent_dist = []
            for r in intent_rows:
                iname = r["intent_name"]
                c = r["count"]
                pct = round((c / total_queries * 100), 1) if total_queries > 0 else 0.0
                intent_dist.append({
                    "intent": iname,
                    "label": intent_labels.get(iname, iname.replace("_", " ").title()),
                    "count": c,
                    "percentage": pct,
                })

            # 9. Recent Activity (Latest 15 user messages with PII masking)
            activity_rows = conn.execute(
                """
                SELECT m.message_id, m.session_id, m.content, m.language, m.intent,
                       m.confidence, m.created_at, s.farmer_id
                FROM conversation_messages m
                LEFT JOIN farmer_sessions s ON m.session_id = s.session_id
                WHERE m.role = 'user'
                ORDER BY m.created_at DESC
                LIMIT 15
                """
            ).fetchall()

            recent_activity = []
            for r in activity_rows:
                raw_farmer = r["farmer_id"]
                if raw_farmer:
                    if len(raw_farmer) > 4:
                        masked_farmer = raw_farmer[:3] + "***" + raw_farmer[-1]
                    else:
                        masked_farmer = raw_farmer[0] + "***"
                else:
                    masked_farmer = "Anonymous Farmer"

                raw_sid = r["session_id"]
                masked_sid = (raw_sid[:4] + "..." + raw_sid[-4:]) if len(raw_sid) > 8 else raw_sid

                recent_activity.append({
                    "message_id": r["message_id"],
                    "session_id_masked": masked_sid,
                    "farmer_id_masked": masked_farmer,
                    "query_preview": (r["content"][:95] + "...") if len(r["content"]) > 95 else r["content"],
                    "language": r["language"] or "en",
                    "intent": r["intent"] or "general",
                    "confidence": r["confidence"],
                    "created_at": r["created_at"],
                })

        return {
            "summary": {
                "total_farmers": total_farmers,
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_queries": total_queries,
                "today_queries": today_queries,
                "unanswered_queries": unanswered_queries,
                "feedback": feedback_data,
            },
            "daily_usage": daily_usage,
            "language_distribution": lang_dist,
            "intent_distribution": intent_dist,
            "recent_activity": recent_activity,
        }

    # -----------------------------------------------------------------------
    # Milestone 3, Part 4.4: Farmer Feedback & Satisfaction Management
    # -----------------------------------------------------------------------

    def record_feedback(
        self,
        session_id: str,
        message_id: Optional[str] = None,
        rating: str = "positive",
        comment: Optional[str] = None,
        farmer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record or update feedback from a farmer for an assistant response."""
        with self._lock:
            # 1. Normalize and validate rating
            norm_rating = (rating or "").strip().lower()
            if norm_rating in ("thumbs_up", "up", "positive"):
                norm_rating = "positive"
            elif norm_rating in ("thumbs_down", "down", "negative"):
                norm_rating = "negative"
            else:
                raise ValueError("Invalid rating. Must be 'positive' or 'negative'.")

            # 2. Validate session exists
            session = self.get_session(session_id)
            if not session:
                raise ValueError(f"Session '{session_id}' not found.")

            assigned_farmer = farmer_id or session.farmer_id

            # 3. Sanitize comment for farmer privacy
            sanitized_comment = None
            if comment:
                trimmed = str(comment).strip()[:500]
                if trimmed:
                    try:
                        from review_manager import sanitize_pii_for_review
                        sanitized_comment = sanitize_pii_for_review(trimmed)
                    except Exception:
                        sanitized_comment = trimmed

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 4. Resolve message content, query_text, answer_text, language, intent
            query_text = ""
            answer_text = ""
            lang = session.language or "en"
            intent = None

            with self._get_connection() as conn:
                resolved_msg_id = message_id
                if resolved_msg_id:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT message_id, role, content, language, intent, created_at FROM conversation_messages WHERE message_id = ?",
                        (resolved_msg_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        if row["role"] == "assistant":
                            answer_text = row["content"]
                            lang = row["language"] or lang
                            intent = row["intent"]
                            u_row = conn.execute(
                                "SELECT content FROM conversation_messages WHERE session_id = ? AND role = 'user' AND created_at <= ? ORDER BY created_at DESC LIMIT 1",
                                (session_id, row["created_at"]),
                            ).fetchone()
                            if u_row:
                                query_text = u_row["content"]
                        else:
                            query_text = row["content"]
                            lang = row["language"] or lang
                            intent = row["intent"]

                # If no message_id was given or not found in conversation_messages, find latest assistant message
                if not answer_text:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT message_id, role, content, language, intent, created_at FROM conversation_messages WHERE session_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        resolved_msg_id = resolved_msg_id or row["message_id"]
                        answer_text = row["content"]
                        lang = row["language"] or lang
                        intent = row["intent"]
                        u_row = conn.execute(
                            "SELECT content FROM conversation_messages WHERE session_id = ? AND role = 'user' AND created_at <= ? ORDER BY created_at DESC LIMIT 1",
                            (session_id, row["created_at"]),
                        ).fetchone()
                        if u_row:
                            query_text = u_row["content"]
                    else:
                        if not resolved_msg_id:
                            resolved_msg_id = f"gen_msg_{uuid.uuid4().hex[:10]}"
                        if session.history:
                            last_turn = session.history[-1]
                            query_text = last_turn.user_text
                            answer_text = last_turn.answer_summary
                            lang = last_turn.detected_language or lang
                            intent = last_turn.intent

                # 5. Check if feedback for this message_id already exists
                cur = conn.cursor()
                cur.execute(
                    "SELECT feedback_id, review_id, created_at FROM farmer_feedback WHERE message_id = ?",
                    (resolved_msg_id,),
                )
                existing_fb = cur.fetchone()

                if existing_fb:
                    fb_id = existing_fb["feedback_id"]
                    review_id = existing_fb["review_id"]
                    conn.execute(
                        """
                        UPDATE farmer_feedback
                        SET rating = ?, comment = ?, farmer_id = COALESCE(?, farmer_id), updated_at = ?
                        WHERE feedback_id = ?
                        """,
                        (norm_rating, sanitized_comment, assigned_farmer, now_iso, fb_id),
                    )
                else:
                    fb_id = f"fb_{uuid.uuid4().hex[:12]}"
                    review_id = None
                    conn.execute(
                        """
                        INSERT INTO farmer_feedback (
                            feedback_id, session_id, message_id, rating, comment,
                            farmer_id, language, intent, query_text, answer_text,
                            review_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fb_id, session_id, resolved_msg_id, norm_rating, sanitized_comment,
                            assigned_farmer, lang, intent, query_text, answer_text,
                            review_id, now_iso, now_iso,
                        ),
                    )

                # Return fresh record
                cur = conn.cursor()
                cur.execute("SELECT * FROM farmer_feedback WHERE feedback_id = ?", (fb_id,))
                result = dict(cur.fetchone())
                return result

    def get_feedback(self, feedback_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a specific feedback record by feedback_id."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM farmer_feedback WHERE feedback_id = ?", (feedback_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_feedback_by_message_id(self, message_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a specific feedback record by message_id."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM farmer_feedback WHERE message_id = ?", (message_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_feedback_detail(self, feedback_id: str) -> Optional[dict[str, Any]]:
        """Return full feedback detail including linked review status if available."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM farmer_feedback WHERE feedback_id = ?", (feedback_id,))
                fb = cur.fetchone()
                if not fb:
                    return None
                data = dict(fb)

                if data.get("review_id"):
                    try:
                        from review_manager import review_manager
                        rev = review_manager.get_review(data["review_id"])
                        if rev:
                            data["review_detail"] = rev if isinstance(rev, dict) else rev.to_dict()
                    except Exception:
                        pass
                return data

    def list_feedback(
        self,
        rating: Optional[str] = None,
        language: Optional[str] = None,
        intent: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query farmer feedback with comprehensive filters and overall satisfaction statistics."""
        with self._lock:
            with self._get_connection() as conn:
                conditions = []
                params: list[Any] = []

                if rating and rating != "all":
                    norm_r = (
                        "positive"
                        if rating in ("positive", "thumbs_up", "up")
                        else ("negative" if rating in ("negative", "thumbs_down", "down") else rating)
                    )
                    conditions.append("rating = ?")
                    params.append(norm_r)

                if language and language != "all":
                    conditions.append("language = ?")
                    params.append(language)

                if intent and intent != "all":
                    conditions.append("intent = ?")
                    params.append(intent)

                if start_date:
                    conditions.append("created_at >= ?")
                    params.append(start_date)

                if end_date:
                    conditions.append("created_at <= ?")
                    params.append(end_date)

                if search and search.strip():
                    s_term = f"%{search.strip()}%"
                    conditions.append("(query_text LIKE ? OR answer_text LIKE ? OR comment LIKE ?)")
                    params.extend([s_term, s_term, s_term])

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                # Overall summary stats across ALL feedback
                stats_row = conn.execute("""
                    SELECT 
                        count(*) AS total,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg
                    FROM farmer_feedback
                """).fetchone()

                total_all = stats_row["total"] or 0
                pos_all = stats_row["pos"] or 0
                neg_all = stats_row["neg"] or 0
                sat_rate = round((pos_all / total_all) * 100, 1) if total_all > 0 else 0.0

                count_query = f"SELECT count(*) FROM farmer_feedback {where_clause}"
                total_filtered = conn.execute(count_query, params).fetchone()[0]

                data_query = f"""
                    SELECT feedback_id, session_id, message_id, rating, comment,
                           farmer_id, language, intent, query_text, answer_text,
                           review_id, created_at, updated_at
                    FROM farmer_feedback
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cur = conn.cursor()
                cur.execute(data_query, params + [limit, offset])
                items = [dict(row) for row in cur.fetchall()]

                return {
                    "items": items,
                    "total": total_filtered,
                    "limit": limit,
                    "offset": offset,
                    "stats": {
                        "total_ratings": total_all,
                        "positive": pos_all,
                        "negative": neg_all,
                        "satisfaction_rate": sat_rate,
                    },
                }

    def get_feedback_analytics(self, days: int = 30) -> dict[str, Any]:
        """Compute satisfaction analytics, daily trends, and breakdowns by language and intent."""
        with self._lock:
            with self._get_connection() as conn:
                days = max(1, min(365, days))
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                start_dt = now_dt - datetime.timedelta(days=days - 1)
                start_date = start_dt.strftime("%Y-%m-%d")

                # 1. Overall stats for the period
                stats_row = conn.execute("""
                    SELECT 
                        count(*) AS total,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg
                    FROM farmer_feedback
                    WHERE created_at >= ?
                """, (start_date,)).fetchone()

                total_ratings = stats_row["total"] or 0
                pos_ratings = stats_row["pos"] or 0
                neg_ratings = stats_row["neg"] or 0
                sat_rate = round((pos_ratings / total_ratings) * 100, 1) if total_ratings > 0 else 0.0

                # 2. Daily trend
                daily_map: dict[str, dict[str, Any]] = {}
                for i in range(days - 1, -1, -1):
                    d_str = (now_dt - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                    daily_map[d_str] = {
                        "date": d_str,
                        "positive": 0,
                        "negative": 0,
                        "total": 0,
                        "satisfaction_rate": 0.0,
                    }

                trend_rows = conn.execute("""
                    SELECT 
                        substr(created_at, 1, 10) AS day,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg,
                        count(*) AS count
                    FROM farmer_feedback
                    WHERE created_at >= ?
                    GROUP BY substr(created_at, 1, 10)
                    ORDER BY day ASC
                """, (start_date,)).fetchall()

                for r in trend_rows:
                    day_key = r["day"]
                    if day_key in daily_map:
                        pos = r["pos"] or 0
                        neg = r["neg"] or 0
                        tot = r["count"] or 0
                        rate = round((pos / tot) * 100, 1) if tot > 0 else 0.0
                        daily_map[day_key] = {
                            "date": day_key,
                            "positive": pos,
                            "negative": neg,
                            "total": tot,
                            "satisfaction_rate": rate,
                        }

                daily_trend = list(daily_map.values())

                # 3. By Language
                lang_names = {
                    "en": "English",
                    "hi": "हिंदी (Hindi)",
                    "kn": "ಕನ್ನಡ (Kannada)",
                    "ta": "தமிழ் (Tamil)",
                    "te": "తెలుగు (Telugu)",
                    "mr": "मराठी (Marathi)",
                    "gu": "ગુજરાતી (Gujarati)",
                    "pa": "ਪੰਜਾਬੀ (Punjabi)",
                    "bn": "বাংলা (Bengali)",
                }
                lang_rows = conn.execute("""
                    SELECT 
                        language,
                        count(*) AS count,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg
                    FROM farmer_feedback
                    WHERE created_at >= ?
                    GROUP BY language
                    ORDER BY count DESC
                """, (start_date,)).fetchall()

                by_lang = []
                for r in lang_rows:
                    code = r["language"] or "en"
                    cnt = r["count"] or 0
                    pos = r["pos"] or 0
                    neg = r["neg"] or 0
                    r_sat = round((pos / cnt) * 100, 1) if cnt > 0 else 0.0
                    by_lang.append({
                        "code": code,
                        "language": lang_names.get(code, code.upper()),
                        "count": cnt,
                        "positive": pos,
                        "negative": neg,
                        "satisfaction_rate": r_sat,
                    })

                # 4. By Intent
                intent_labels = {
                    "irrigation": "Irrigation Guidance",
                    "crop_advisory": "Crop Advisory",
                    "pest_control": "Pest & Disease Control",
                    "market_prices": "Mandi Market Prices",
                    "government_schemes": "Government Schemes",
                    "weather": "Weather Forecast",
                    "general": "General Inquiry",
                }
                intent_rows = conn.execute("""
                    SELECT 
                        COALESCE(intent, 'general') AS iname,
                        count(*) AS count,
                        SUM(CASE WHEN rating = 'positive' THEN 1 ELSE 0 END) AS pos,
                        SUM(CASE WHEN rating = 'negative' THEN 1 ELSE 0 END) AS neg
                    FROM farmer_feedback
                    WHERE created_at >= ?
                    GROUP BY iname
                    ORDER BY count DESC
                """, (start_date,)).fetchall()

                by_intent = []
                for r in intent_rows:
                    iname = r["iname"]
                    cnt = r["count"] or 0
                    pos = r["pos"] or 0
                    neg = r["neg"] or 0
                    r_sat = round((pos / cnt) * 100, 1) if cnt > 0 else 0.0
                    by_intent.append({
                        "intent": iname,
                        "label": intent_labels.get(iname, iname.replace("_", " ").title()),
                        "count": cnt,
                        "positive": pos,
                        "negative": neg,
                        "satisfaction_rate": r_sat,
                    })

                return {
                    "satisfaction_rate": sat_rate,
                    "total_ratings": total_ratings,
                    "positive_ratings": pos_ratings,
                    "negative_ratings": neg_ratings,
                    "daily_trend": daily_trend,
                    "by_language": by_lang,
                    "by_intent": by_intent,
                }

    def flag_feedback_for_review(self, feedback_id: str, reviewer_notes: Optional[str] = None) -> dict[str, Any]:
        """Flag a negative or problematic feedback item into the agricultural expert review queue."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM farmer_feedback WHERE feedback_id = ?", (feedback_id,))
                fb = cur.fetchone()
                if not fb:
                    raise ValueError(f"Feedback '{feedback_id}' not found.")
                fb_dict = dict(fb)

                from review_manager import review_manager, ReviewRecord
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

                existing_rev_id = fb_dict.get("review_id")
                review_obj = None
                if existing_rev_id:
                    review_obj = review_manager._reviews.get(existing_rev_id)

                if not review_obj:
                    h = hashlib.sha256(f"{feedback_id}_{now_iso}".encode()).hexdigest()[:8]
                    rev_id = f"rev_fb_{h}"
                    flag_reason = f"Farmer negative feedback: {fb_dict.get('comment') or 'Dissatisfied with response'}"

                    review_rec = ReviewRecord(
                        review_id=rev_id,
                        created_at=now_iso,
                        query=fb_dict.get("query_text") or "Farmer Query",
                        canonical_text=fb_dict.get("query_text") or "Farmer Query",
                        intent=fb_dict.get("intent") or "crop_advisory",
                        confidence=0.50,
                        quality_score=0.50,
                        source_reliability=0.50,
                        evidence_grounding_score=0.50,
                        status="pending",
                        original_answer=fb_dict.get("answer_text") or "",
                        flag_reason=flag_reason[:150],
                        language=fb_dict.get("language") or "en",
                        reviewer_notes=reviewer_notes,
                    )
                    review_manager._reviews[rev_id] = review_rec
                    review_manager.save()
                    review_id = rev_id
                else:
                    review_id = review_obj.review_id
                    if reviewer_notes:
                        review_obj.reviewer_notes = reviewer_notes
                        review_manager.save()

                conn.execute(
                    "UPDATE farmer_feedback SET review_id = ?, updated_at = ? WHERE feedback_id = ?",
                    (review_id, now_iso, feedback_id),
                )

                fb_dict["review_id"] = review_id
                fb_dict["updated_at"] = now_iso
                return {
                    "feedback_id": feedback_id,
                    "review_id": review_id,
                    "status": "flagged_for_review",
                    "feedback": fb_dict,
                }


# Module-level singleton instance
session_manager = SessionManager()
