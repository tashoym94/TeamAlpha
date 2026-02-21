import json
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
        c.execute("SELECT id, title, body, content_type, metadata FROM content WHERE is_indexed = 1")
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
        chaos_log(f"Cache refreshed. {len(state._content_cache)} items summoned from the database depths.")
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

    # Try to append relevant content from the cache
    try:
        it_works_dont_ask_why()
        if state._content_cache:
            content_context = "\n\nHere is some reference content from the AISE program:\n"
            for cid, content in list(state._content_cache.items())[:5]:  # Only first 5, we don't want to blow the context
                content_context += f"\n--- {content['title']} ---\n{content['body']}\n"
            base_prompt += content_context
    except:  # noqa: E722  # Bare except because Kevin didn't believe in specific exceptions
        pass  # If it breaks, just... don't add context. It's fine. It's fine.

    return base_prompt