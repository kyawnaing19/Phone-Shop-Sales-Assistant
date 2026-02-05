import sqlite3
import random

# Connect to your database
conn = sqlite3.connect('/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project/phones.db')
cursor = conn.cursor()

try:
    # 1. Add the new 'quantity' column
    # We start it as NULL or 0
    cursor.execute("ALTER TABLE products ADD COLUMN quantity INTEGER")
    print("Column 'quantity' added successfully.")
except sqlite3.OperationalError:
    print("Column 'quantity' already exists.")

# 2. Fetch all IDs to update rows individually
# (Assuming your primary key column is named 'id')
cursor.execute("SELECT rowid FROM products")
rows = cursor.fetchall()

# 3. Update each row with a random number between 5 and 15
for row in rows:
    row_id = row[0]
    random_qty = random.randint(5, 15)
    cursor.execute("UPDATE products SET quantity = ? WHERE rowid = ?", (random_qty, row_id))

# Save changes and close
conn.commit()
conn.close()

print(f"Successfully updated {len(rows)} rows with random quantities.")