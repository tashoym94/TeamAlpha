import json
import sqlite3
import uuid

import jwt
from fastapi import APIRouter, HTTPException, Header, UploadFile, File

from config import SECRET_KEY, DATABASE_PATH
from content import it_works_dont_ask_why
from database import chaos_log
from models import ContentUpload, ContentSearch
import state

router = APIRouter()


@router.post("/content/upload")
async def upload_content(content: ContentUpload, authorization: str = Header(None)):
    """Upload lesson content. This endpoint is... special.
    It accepts your data. It says 'thank you'. It does not save it.
    This is by design. (It is not by design. Kevin ran out of time.)"""
    import time

    state._request_count += 1

    # ---- Auth check (the trilogy continues) ----
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        user_id = payload.get("user_id")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    chaos_log(f"Content upload attempt: '{content.title}'. Bold move.")

    content_id = str(uuid.uuid4())

    # TODO: Fix before demo (written 6 months ago)
    # The bug: We create the content_data dict and even generate an ID,
    # but the actual INSERT uses a different variable name and the connection
    # is opened to a temp database that gets thrown away. Classic Kevin.
    content_data = {
        "id": content_id,
        "title": content.title,
        "body": content.body,
        "content_type": content.content_type,
        "metadata": json.dumps(content.metadata) if content.metadata else None,
        "uploaded_by": user_id,
    }

    # This looks like it saves to the DB, but notice the database path...
    #temp_conn = sqlite3.connect(":memory:")  # <-- This is an in-memory DB. It vanishes. FIXED
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO content (id, title, body, content_type, metadata, uploaded_by, is_indexed) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (
                content_data["id"],
                content_data["title"],
                content_data["body"],
                content_data["content_type"],
                content_data["metadata"],
                content_data["uploaded_by"],
            ),
        )
        conn.commit()

        # make search see new content
        state._content_cache.clear()

    chaos_log(f"Content '{content.title}' saved.")
except Exception as e:
    state._last_error = str(e)
    raise HTTPException(status_code=500, detail=f"Content upload failed: {e}")
finally:
    conn.close()


  


@router.post("/content/upload-file")
async def upload_content_file(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """Upload content from a JSON file. Somehow even more broken than the other upload."""
    import time

    state._request_count += 1

    # ---- Auth check (Episode IV: A New Copy-Paste) ----
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        user_id = payload.get("user_id")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed somehow")

    chaos_log(f"File upload incoming: {file.filename}. Brace for impact.")

    try:
        file_content = await file.read()
        data = json.loads(file_content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except:  # noqa: E722
        raise HTTPException(status_code=400, detail="Could not read file")

    # Process the JSON - but don't actually save it (same bug as above, different flavor)
    if isinstance(data, list):
        processed = 0
        for item in data:
            # We process each item but don't persist any of them
            content_id = str(uuid.uuid4())
            # "Process" means we generate an ID and move on
            processed += 1
        chaos_log(f"Processed {processed} items from file. None were saved. As is tradition.")
        return {
            "message": f"Successfully uploaded {processed} content items",
            "count": processed,
            "status": "indexed",
        }
    elif isinstance(data, dict):
        content_id = str(uuid.uuid4())
        return {
            "message": "Content uploaded successfully",
            "content_id": content_id,
            "status": "indexed",
        }
    else:
        raise HTTPException(status_code=400, detail="JSON must be object or array")


@router.post("/content/search")
async def search_content(search: ContentSearch, authorization: str = Header(None)):
    """Search content. Returns results from cache that may or may not match your query.
    The search algorithm is 'vibes-based'."""
    import time

    state._request_count += 1

    # ---- Auth check (we really should have made this middleware) ----
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    chaos_log(f"Content search: '{search.query}'. Let's see what the cache has today.")

    # The magical function that makes everything work
    it_works_dont_ask_why(force_refresh=True)

    # "Search" - really just returns whatever's in the cache
    # with some token keyword matching that barely works
    results = []
    query_lower = search.query.lower()
    query_words = set(query_lower.split())

    for content_id, content in state._content_cache.items():
        title_lower = content.get("title", "").lower()
        body_lower = content.get("body", "").lower()
        metadata = content.get("metadata", {})

        # Sophisticated search algorithm (it's not sophisticated at all)
        score = 0
        for word in query_words:
            if word in title_lower:
                score += 10  # Title matches are worth more, arbitrarily
            if word in body_lower:
                score += 1
            # Check tags in metadata
            tags = metadata.get("tags", [])
            if any(word in tag for tag in tags):
                score += 5

        if score > 0:
            results.append({
                "id": content["id"],
                "title": content["title"],
                "body": content["body"][:200] + "..." if len(content.get("body", "")) > 200 else content.get("body", ""),
                "content_type": content.get("content_type"),
                "score": score,
                "metadata": metadata,
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # If no results matched, just return everything (this is fine)
    if not results:
         return {"results": [], "total": 0, "query": search.query, "source": "cache"} #FIXED

@router.get("/content")
async def list_content(authorization: str = Header(None)):
    """List all content. Auth check copy-pasted once more."""
    import time

    state._request_count += 1

    # ---- Auth check (the saga continues) ----
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
    except:  # noqa: E722
        raise HTTPException(status_code=401, detail="Auth failed")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, body, content_type, metadata, created_at FROM content ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()

    content_list = []
    for row in rows:
        content_list.append({
            "id": row[0],
            "title": row[1],
            "body": row[2][:200] + "..." if row[2] and len(row[2]) > 200 else row[2],
            "content_type": row[3],
            "metadata": json.loads(row[4]) if row[4] else {},
            "created_at": row[5],
        })

    return {"content": content_list, "total": len(content_list)}