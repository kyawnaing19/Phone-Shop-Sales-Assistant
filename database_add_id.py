import sqlite3

DB_PATH = "/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project/phones.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Adding id column safely...")

# 1. Create new table with id
cursor.execute("""
CREATE TABLE products_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT,
    model TEXT,
    price INTEGER,
    specifications TEXT,
    best_for TEXT,
    quantity INTEGER
);
""")

# 2. Copy old data
cursor.execute("""
INSERT INTO products_new (brand, model, price, specifications, best_for, quantity)
SELECT brand, model, price, specifications, best_for, quantity
FROM products;
""")

# 3. Delete old table
cursor.execute("DROP TABLE products;")

# 4. Rename new table
cursor.execute("ALTER TABLE products_new RENAME TO products;")

conn.commit()
conn.close()

print("Done! 'id' column added.")
