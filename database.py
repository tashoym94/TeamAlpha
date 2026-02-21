import sqlite3
import json
import uuid

from config import DATABASE_PATH
from state import _debug_messages
from config import DEBUG_MODE


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


def init_db():
    """Initialize the database. All tables in one function because modularity is overrated."""
    chaos_log("Summoning the database from the void...")
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            role TEXT DEFAULT 'fellow'
        )
    """)

    # Chat history
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            message TEXT,
            response TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            tokens_used INTEGER DEFAULT 0
        )
    """)

    # Content table - Kevin was supposed to finish this
    c.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id TEXT PRIMARY KEY,
            title TEXT,
            body TEXT,
            content_type TEXT DEFAULT 'lesson',
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            uploaded_by TEXT,
            is_indexed INTEGER DEFAULT 0
        )
    """)

    # This table was for something. I think analytics?
    c.execute("""
        CREATE TABLE IF NOT EXISTS mystery_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            thing TEXT,
            other_thing TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    chaos_log("Database awakened. It hungers for data.")


def seed_default_content():
    """Pre-populate some content because the upload endpoint is... unreliable"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM content")
    count = c.fetchone()[0]
    if count == 0:
        chaos_log("Seeding default content because nothing else works...")
        default_content = [
            {
                "id": str(uuid.uuid4()),
                "title": "Introduction to AI Safety",
                "body": "AI Safety is a field dedicated to ensuring that artificial intelligence systems are developed and deployed in ways that are safe, beneficial, and aligned with human values. Key topics include alignment, interpretability, robustness, and governance. The AISE program covers these fundamentals across 12 weeks of intensive study.",
                "content_type": "lesson",
                "metadata": json.dumps({"week": 1, "module": "foundations", "tags": ["ai-safety", "intro", "alignment"]}),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Prompt Engineering Fundamentals",
                "body": "Prompt engineering is the practice of designing and refining inputs to large language models to achieve desired outputs. Techniques include zero-shot prompting, few-shot prompting, chain-of-thought reasoning, and system prompt design. Fellows will practice these techniques throughout the AISE program with hands-on exercises.",
                "content_type": "lesson",
                "metadata": json.dumps({"week": 2, "module": "prompt-engineering", "tags": ["prompts", "llm", "techniques"]}),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Building AI Agents",
                "body": "AI Agents are systems that use LLMs as reasoning engines to take actions, use tools, and accomplish goals autonomously. Key concepts include tool use, planning, memory systems, and evaluation. The AISE program dedicates weeks 5-8 to building increasingly sophisticated agent systems.",
                "content_type": "lesson",
                "metadata": json.dumps({"week": 5, "module": "agents", "tags": ["agents", "tools", "planning"]}),
            },
            {
                "id": str(uuid.uuid4()),
                "title": "AISE Program Schedule",
                "body": "Week 1-2: Foundations of AI Safety and Ethics. Week 3-4: Prompt Engineering and LLM APIs. Week 5-8: Building AI Agents and Tool Use. Week 9-10: Evaluation and Red Teaming. Week 11-12: Capstone Projects and Presentations. All sessions are held Monday-Friday, 9am-5pm ET.",
                "content_type": "schedule",
                "metadata": json.dumps({"type": "schedule", "version": "2025-fall"}),
            },
        ]
        for item in default_content:
            c.execute(
                "INSERT INTO content (id, title, body, content_type, metadata, is_indexed) VALUES (?, ?, ?, ?, ?, 1)",
                (item["id"], item["title"], item["body"], item["content_type"], item["metadata"]),
            )
        conn.commit()
    conn.close()