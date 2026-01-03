import sys
import os
sys.path.append(os.path.abspath("backend"))

from backend.app.db import insert_inquiry, init_db

try:
    print("Initializing DB...")
    init_db()
    print("Inserting inquiry...")
    rid = insert_inquiry("Test", "test@test.com", "msg", "test", "en")
    print(f"Success! ID: {rid}")
except Exception as e:
    print(f"Error: {e}")
