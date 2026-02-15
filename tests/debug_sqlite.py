
import sqlite3
import os

storage_dir = "/app/storage"
db_path = os.path.join(storage_dir, "metadata.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get 1 row
cursor.execute("SELECT text, document_name, source FROM chunks LIMIT 1")
row = cursor.fetchone()

if row:
    text, doc_name, source = row
    print(f"Sample Chunk Text Length: {len(text)}")
    print(f"Sample Doc Name: {doc_name} (Len: {len(str(doc_name))})")
    print(f"Sample Source: {source} (Len: {len(str(source))})")
else:
    print("Database is empty.")

