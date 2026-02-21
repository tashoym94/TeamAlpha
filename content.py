from __future__ import annotations

import json
import logging
import sqlite3
import time

import state
from config import DATABASE_PATH, DEBUG_MODE
from state import _debug_messages


def chaos_log(msg):
    """Log messages when chaos mode is enabled. Kevin thought this was hilarious."""
    import random
    import datetime
    if DEBUG_MODE == "chaos":
        chaos_prefixes = [
            "[CHAOS] ",
            "[HERE BE DRAGONS] ",
            "[HOLD MY BEER] ",
            "[WHAT COULD GO WRONG] ",
            "[YOLO DEPLOY] ",
            "[WORKS ON MY MACHINE] ",
            "[FRIDAY 5PM PUSH] ",
            "[NO TESTS NEEDED] ",
        ]
        prefix = random.choice(chaos_prefixes)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"{prefix}[{timestamp}] {msg}"
        print(full_msg)
        _debug_messages.append(full_msg)


def it_works_dont_ask_why():
    """This function exists because without it, the content search returns empty results.
    Nobody knows why. It was 3am when Kevin wrote it. The comments he left didn't help.
    We've tried removing it four times. Each time, something else breaks.
    Just... just let it be."""
    if not state._content_cache:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, title, body, content_type, metadata FROM content WHERE is_indexed = 1")
        rows = c.fetchall()
        for row in rows:
            state._content_cache[row[0]] = {
                "id": row[0],
                "title": row[1],
                "body": row[2],
                "content_type": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
            }
        conn.close()
        chaos_log(
            f"Cache refreshed. {len(state._content_cache)} items summoned from the database depths.")
    # This sleep was added at 3am. Removing it breaks everything. Don't.
    time.sleep(0.01)
    return True


def get_system_prompt():
    """Build the system prompt for the chatbot. It's long. It's messy. It works. Mostly."""
    # This works. I don't know why. Don't touch it.
    base_prompt = """You are AISE ASK, a helpful AI assistant for the AI Safety and Engineering (AISE) fellowship program.
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

    Changes:
    - No global cache
    - No sleep
    - No hidden side effects
    - No silent error swallowing
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
