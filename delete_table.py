import sqlite3


def delete_redundant_tables(db_file):
    # List of tables you want to remove
    tables_to_drop = [
        "cart"
    ]

    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        print(f"Connected to {db_file} successfully.")

        for table in tables_to_drop:
            # Use f-string carefully or a whitelist to prevent SQL injection
            # Since these are hardcoded strings, it's safe here
            sql = f"DROP TABLE IF EXISTS {table};"
            cursor.execute(sql)
            print(f"Dropped table: {table}")

        # Commit changes and close
        conn.commit()
        print("--- All specified tables deleted successfully. ---")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Replace 'your_database.db' with your actual filename
    delete_redundant_tables('/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project/users.db')