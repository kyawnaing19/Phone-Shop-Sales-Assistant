import sqlite3
import pandas as pd


def display_table_values(db_file, table_name):
    try:
        # 1. Database ကို ချိတ်ဆက်ခြင်း
        conn = sqlite3.connect(db_file)

        # 2. SQL Query ရေးပြီး Pandas DataFrame ထဲသို့ ဖတ်ယူခြင်း
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)

        # 3. Data ရှိမရှိ စစ်ဆေးပြီး Table ပုံစံဖြင့် ပြသခြင်း
        if not df.empty:
            print(f"\n📊 Table: {table_name}")
            print("-" * 30)
            print(df.to_string(index=False))  # index=False က ဘေးက column နံပါတ်တွေကို ဖျောက်ပေးပါတယ်
        else:
            print(f"❌ Table '{table_name}' ထဲမှာ data မရှိပါ။")

        conn.close()

    except sqlite3.Error as e:
        print(f"❌ Error occurred: {e}")


# အသုံးပြုနည်း
# သင့်ရဲ့ database file name နဲ့ table name ကို ဒီမှာ ထည့်ပေးပါ
display_table_values('/home/pyae-phyo-aung/PycharmProjects/MyanmarMobileSaleChatbot/Mobile_Sales_Project/users.db', 'orders')