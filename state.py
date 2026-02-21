import time

# Global mutable state because architecture is for people with time
_user_sessions = {}
_content_cache = {}
_request_count = 0
_last_error = None
_debug_messages = []
_system_start_time = time.time()
spaghetti_handler = None  # Gets set later. Maybe. Depends on the moon phase.
