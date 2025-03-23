import sqlite3

db_path = "techtree.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

query = "SELECT * FROM users WHERE email = ?"
params = ("wgilpin@gmail.com",)

cursor.execute(query, params)
result = cursor.fetchone()

if result:
    print(dict(result))
else:
    print("User not found")

conn.close()