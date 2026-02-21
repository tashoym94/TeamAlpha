from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List

from config import DATABASE_PATH

# Logging (REPLACED chaos_log + global debug list)
# OLD: Used print() and appended to a global _debug_messages list
# NEW: Use Python's built-in logging system (safer and scalable)
logger = logging.getLogger(__name__)


# Data model
# OLD: Used raw dicts stored in a global cache
# NEW: Use a simple dataclass for clarity and structure
@dataclass
class ContentItem:
    id: str
    title: str
    body: str
    content_type: str
    metadata: Dict[str, Any]


# Database connection helper
# OLD: Database access was hidden inside it_works_dont_ask_why()
# NEW: Clear, explicit DB connection function
def _connect_db() -> sqlite3.Connection:
    """
    Create a connection to SQLite.

    Added timeout to reduce 'database is locked' errors.
    """
    return sqlite3.connect(DATABASE_PATH, timeout=5)


# Fetch indexed content directly from DB
# OLD: Loaded content into a global cache once and reused it forever
# OLD: Cache was never invalidated after uploads
# NEW: Always fetch fresh indexed content from the database
def fetch_indexed_content(limit: int = 5) -> List[ContentItem]:
    sql = """
        SELECT id, title, body, content_type, metadata
        FROM content
        WHERE is_indexed = 1
        ORDER BY created_at DESC
        LIMIT ?
    """

    try:
        with _connect_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    except sqlite3.Error:
        # OLD: Errors were silently ignored
        # NEW: Log database errors so we can debug issues
        logger.exception("Database error while fetching content.")
        return []

    items: List[ContentItem] = []

    for row in rows:
        raw_metadata = row[4]

        # OLD: Could crash if metadata was invalid JSON
        # NEW: Safely handle JSON errors
        try:
            metadata = json.loads(raw_metadata) if raw_metadata else {}
        except json.JSONDecodeError:
            metadata = {}

        items.append(
            ContentItem(
                id=row[0],
                title=row[1] or "",
                body=row[2] or "",
                content_type=row[3] or "lesson",
                metadata=metadata,
            )
        )

    return items


# Base system prompt (unchanged content, just cleaned structure)
BASE_SYSTEM_PROMPT = """You are AISE ASK, a helpful AI assistant for the AI Safety and Engineering (AISE) fellowship program.
You help fellows with questions about:
- The AISE curriculum and schedule
- AI safety concepts (alignment, interpretability, robustness)
- Prompt engineering techniques
- Building AI agents
- Technical concepts covered in the program
- Program logistics and schedules

Be friendly, concise, and helpful. If you don't know something specific about the AISE program,
say so honestly rather than making things up. You can still help with general AI/ML questions.

Keep responses focused and practical. Fellows are busy learning - respect their time."""


# System prompt builder
# OLD: Called it_works_dont_ask_why() (mysterious global mutation)
# OLD: Used time.sleep(0.01) (blocked the app)
# OLD: Wrapped everything in bare except: pass
# NEW: Deterministic, readable, safe
def get_system_prompt(
    max_items: int = 5,
    max_body_chars: int = 1200,
) -> str:
    """
    Build the system prompt for the LLM.
    """
    prompt = BASE_SYSTEM_PROMPT

    # OLD: Pulled from global cache
    # NEW: Fetch fresh content from DB every time
    items = fetch_indexed_content(limit=max_items)

    if not items:
        return prompt

    prompt += "\n\nHere is some reference content from the AISE program:\n"

    for item in items:
        body = item.body.strip()

        # OLD: Could append extremely long lesson bodies
        # NEW: Trim long content to avoid huge prompts
        if len(body) > max_body_chars:
            body = body[:max_body_chars].rstrip() + "…"

        prompt += f"\n--- {item.title} ({item.content_type}) ---\n{body}\n"

    return prompt


# Optional local test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_system_prompt())
