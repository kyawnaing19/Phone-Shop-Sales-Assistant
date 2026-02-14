import sqlite3

# ==== Change this to your database file ====
DB_PATH = r"/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project/users.db"
# Example: DB_PATH = "mobiles.db"

def show_database_structure(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"\nConnected to: {db_path}\n")

    # 1. Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print("No tables found.")
        return

    print("Tables in database:")
    for table in tables:
        table_name = table[0]
        print(f"\n--- Table: {table_name} ---")

        # 2. Get table structure
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        print("Columns:")
        print("cid | name | type | notnull | default | pk")
        for col in columns:
            print(col)

        # 3. Row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"Total rows: {count}")

    conn.close()


if __name__ == "__main__":
    show_database_structure(DB_PATH)
