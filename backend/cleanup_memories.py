"""
MemoryBridge — Full Reset Script
Deletes all memory documents from Firestore (including photos subcollection)
and all associated files from Firebase Storage.

Run from the backend/ directory:
    python cleanup_memories.py

What it deletes:
  - Firestore: memories/{id} documents
  - Firestore: memories/{id}/photos/{*} subcollection docs
  - Firebase Storage: memories/{id}/** files (photos + voice recording)

What it does NOT touch:
  - ElevenLabs voice clones, knowledge bases, or agents
    (manage those at https://elevenlabs.io/app/voice-lab)
  - Your .env file
  - Any Firebase config
"""

import os
import sys

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore, storage


def init_firebase() -> tuple:
    cred_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "./serviceAccount.json")
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "")

    if not os.path.isfile(cred_path):
        print(f"ERROR: serviceAccount.json not found at {cred_path}")
        sys.exit(1)
    if not bucket_name:
        print("ERROR: FIREBASE_STORAGE_BUCKET not set in .env")
        sys.exit(1)

    cred = credentials.Certificate(cred_path)
    app = firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    db = firestore.client()
    bucket = storage.bucket()
    return db, bucket


def list_memories(db) -> list:
    docs = list(db.collection("memories").stream())
    return docs


def delete_memory(db, bucket, memory_id: str, dry_run: bool = False) -> None:
    prefix = f"memories/{memory_id}/"

    # 1. Delete photos subcollection docs
    photos_ref = db.collection("memories").document(memory_id).collection("photos")
    photo_docs = list(photos_ref.stream())
    for photo_doc in photo_docs:
        if dry_run:
            print(f"  [DRY RUN] Would delete Firestore photo: {photo_doc.id}")
        else:
            photo_doc.reference.delete()
            print(f"  Deleted Firestore photo doc: {photo_doc.id}")

    # 2. Delete Storage files under memories/{id}/
    blobs = list(bucket.list_blobs(prefix=prefix))
    if blobs:
        for blob in blobs:
            if dry_run:
                print(f"  [DRY RUN] Would delete Storage file: {blob.name}")
            else:
                blob.delete()
                print(f"  Deleted Storage file: {blob.name}")
    else:
        print(f"  No Storage files found under {prefix}")

    # 3. Delete the parent memory document
    mem_ref = db.collection("memories").document(memory_id)
    if dry_run:
        print(f"  [DRY RUN] Would delete Firestore memory doc: {memory_id}")
    else:
        mem_ref.delete()
        print(f"  Deleted Firestore memory doc: {memory_id}")


def main() -> None:
    print("=" * 60)
    print("MemoryBridge — Firestore + Storage Reset")
    print("=" * 60)

    db, bucket = init_firebase()
    memories = list_memories(db)

    if not memories:
        print("\nNo memory documents found in Firestore. Nothing to clean up.")
        return

    print(f"\nFound {len(memories)} memory document(s):\n")
    for doc in memories:
        data = doc.to_dict() or {}
        person = data.get("person_name", "Unknown")
        status = data.get("status", "unknown")
        voice_id = data.get("voice_id") or "(none)"
        agent_id = data.get("agent_id") or "(none)"
        created = data.get("created_at", "unknown date")
        print(f"  ID       : {doc.id}")
        print(f"  Person   : {person}")
        print(f"  Status   : {status}")
        print(f"  voice_id : {voice_id}")
        print(f"  agent_id : {agent_id}")
        print(f"  Created  : {created}")
        print()

    print("-" * 60)
    print("This will permanently delete the Firestore documents and")
    print("all Firebase Storage files listed above.")
    print()
    print("ElevenLabs resources (voice clone, KB, agent) are NOT")
    print("deleted here — manage those at elevenlabs.io if needed.")
    print("-" * 60)
    print()
    choice = input("Type  yes  to delete ALL, or enter a memory ID to delete just one: ").strip()

    if choice.lower() == "yes":
        targets = memories
    elif choice in {doc.id for doc in memories}:
        targets = [doc for doc in memories if doc.id == choice]
    else:
        print("Aborted — nothing deleted.")
        return

    print()
    for doc in targets:
        memory_id = doc.id
        person = (doc.to_dict() or {}).get("person_name", "Unknown")
        print(f"Deleting memory for '{person}' ({memory_id}) ...")
        delete_memory(db, bucket, memory_id, dry_run=False)
        print(f"  Done.\n")

    print("=" * 60)
    print("Reset complete.")
    print()
    print("Next steps:")
    print("  1. Restart the Flask backend:  cd backend && python run.py")
    print("  2. Open the frontend:          cd frontend && npm run dev")
    print("  3. Go to http://localhost:5173 and upload fresh photos")
    print("=" * 60)


if __name__ == "__main__":
    main()
