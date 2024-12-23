import pymysql

# Database connection configuration
DB_HOST = "JennyJC.mysql.pythonanywhere-services.com"
DB_USER = "JennyJC"
DB_PASSWORD = "chen12300."
DB_NAME = "JennyJC$FHVeggies"

# Connect to the database
try:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    print("Connected to the database successfully!")

    # Use a cursor to execute SQL commands
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print("Tables in the database:", tables)

except pymysql.MySQLError as e:
    print("Error while connecting to the database:", e)

finally:
    if 'connection' in locals() and connection.open:
        connection.close()
        print("Database connection closed.")
