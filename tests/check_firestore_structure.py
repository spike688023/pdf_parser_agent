"""
Check Firestore data structure
"""
import os
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()

def check_firestore_structure():
    """Check the actual Firestore data structure"""
    print("\n" + "="*60)
    print("🔍 Checking Firestore Data Structure")
    print("="*60)
    
    db = firestore.Client(
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        database=os.getenv("FIRESTORE_DATABASE", "(default)")
    )
    
    # Check root collections
    print("\n📂 Root Collections:")
    for collection in db.collections():
        print(f"   - {collection.id}")
    
    # Check sessions collection
    print("\n📂 Sessions Collection:")
    sessions_ref = db.collection('sessions')
    sessions = list(sessions_ref.stream())
    print(f"   Total sessions: {len(sessions)}")
    
    for session in sessions:
        print(f"\n   Session ID: {session.id}")
        data = session.to_dict()
        print(f"   Data: {data}")
        
        # Check subcollections
        chunks_ref = sessions_ref.document(session.id).collection('chunks')
        chunks = list(chunks_ref.stream())
        print(f"   Chunks in this session: {len(chunks)}")
        
        if chunks:
            print(f"   Sample chunk:")
            sample = chunks[0].to_dict()
            print(f"      ID: {chunks[0].id}")
            print(f"      Text preview: {sample.get('text', '')[:100]}...")
            print(f"      Document ID: {sample.get('document_id', 'N/A')}")
    
    # Check documents collection
    print("\n📂 Documents Collection:")
    docs_ref = db.collection('documents')
    docs = list(docs_ref.stream())
    print(f"   Total documents: {len(docs)}")
    
    for doc in docs:
        data = doc.to_dict()
        print(f"\n   Document ID: {doc.id}")
        print(f"   Name: {data.get('document_name', 'N/A')}")
        print(f"   Chunks: {data.get('chunk_count', 0)}")

if __name__ == "__main__":
    check_firestore_structure()
