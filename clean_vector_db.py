"""
Clean and rebuild vector database with ONLY your database products
Run this once to ensure vector DB has no external content
"""
# First, audit to see what's in your vector DB
# python clean_vector_db.py audit

# If external content found, rebuild
# python clean_vector_db.py rebuild

import os
import sqlite3
import shutil
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

BASE_PATH = os.getenv("BASE_PATH")
SQLITE_PATH = os.path.join(BASE_PATH, "phones.db")
CHROMA_PATH = os.path.join(BASE_PATH, "chroma_db_v3")
CHROMA_BACKUP = os.path.join(BASE_PATH, "chroma_db_v3_backup")


def get_all_products_from_db():
    """Get all products from SQLite database"""
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT brand, model, price, quantity, specifications, best_for, ram_storage, color 
        FROM products 
        ORDER BY brand, price ASC
    """)

    products = [dict(row) for row in cursor.fetchall()]
    conn.close()

    print(f"📊 Found {len(products)} products in database")
    return products


def rebuild_clean_vector_db():
    """Rebuild vector DB with ONLY database products (no external content)"""

    print("\n" + "=" * 70)
    print("🧹 CLEANING VECTOR DATABASE")
    print("=" * 70 + "\n")

    # Step 1: Backup old vector DB
    if os.path.exists(CHROMA_PATH):
        if os.path.exists(CHROMA_BACKUP):
            shutil.rmtree(CHROMA_BACKUP)
        print(f"📦 Backing up old vector DB to: {CHROMA_BACKUP}")
        shutil.move(CHROMA_PATH, CHROMA_BACKUP)

    # Step 2: Get products from database
    products = get_all_products_from_db()

    if not products:
        print("❌ No products found in database!")
        return

    # Step 3: Create documents from database products ONLY
    print(f"\n📝 Creating {len(products)} documents from database...")
    documents = []

    for p in products:
        # Format product information
        text = f"{p['brand']} {p['model']}"
        text += f"\nPrice: {p['price']} MMK"

        if p.get('ram_storage'):
            text += f"\nRAM/Storage: {p['ram_storage']}"

        if p.get('color'):
            text += f"\nColors: {p['color']}"

        if p.get('specifications'):
            text += f"\nSpecifications: {p['specifications']}"

        if p.get('best_for'):
            text += f"\nBest for: {p['best_for']}"

        # Create document
        documents.append(Document(
            page_content=text,
            metadata={
                'brand': p['brand'],
                'model': p['model'],
                'price': p['price'],
                'source': 'database',  # IMPORTANT: Mark as from database
                'type': 'product'
            }
        ))

    # Step 4: Create new clean vector DB
    print(f"\n🔨 Building new vector database...")
    embeddings = HuggingFaceEmbeddings(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )

    vector_db = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_PATH
    )

    vector_db.persist()

    print(f"\n✅ SUCCESS!")
    print(f"   • Created clean vector DB at: {CHROMA_PATH}")
    print(f"   • Total documents: {len(documents)}")
    print(f"   • Source: Database products ONLY")
    print(f"   • Backup location: {CHROMA_BACKUP}")
    print("\n" + "=" * 70 + "\n")


def audit_vector_db():
    """Check what's in the current vector database"""

    print("\n" + "=" * 70)
    print("🔍 AUDITING VECTOR DATABASE")
    print("=" * 70 + "\n")

    if not os.path.exists(CHROMA_PATH):
        print("❌ Vector database not found!")
        return

    embeddings = HuggingFaceEmbeddings(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )

    vector_db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings
    )

    # Get all documents
    all_docs = vector_db.get()

    print(f"📊 Vector DB Statistics:")
    print(f"   • Total documents: {len(all_docs['documents'])}")

    # Check for external brands
    external_brands = [
        'pixel 8', 'pixel 7',
         'oneplus 12', 'nothing phone 2'
    ]

    print(f"\n🔍 Checking for external content...")
    found_external = False

    for brand in external_brands:
        count = sum(1 for doc in all_docs['documents'] if brand.lower() in doc.lower())
        if count > 0:
            print(f"   ⚠️ Found '{brand}': {count} times")
            found_external = True

    if not found_external:
        print(f"   ✅ No external brands found - database is clean!")
    else:
        print(f"\n   ❌ External content detected! Run rebuild_clean_vector_db()")

    # Show sample documents
    print(f"\n📄 Sample documents (first 3):")
    for i, doc in enumerate(all_docs['documents'][:3]):
        print(f"\n--- Document {i + 1} ---")
        print(doc[:300])
        print("...")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python clean_vector_db.py audit    - Check current vector DB")
        print("  python clean_vector_db.py rebuild  - Rebuild clean vector DB")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "audit":
        audit_vector_db()
    elif command == "rebuild":
        rebuild_clean_vector_db()
    else:
        print(f"Unknown command: {command}")
        print("Use 'audit' or 'rebuild'")