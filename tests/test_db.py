import psycopg2

try:
    conn = psycopg2.connect(
        dbname="crypto_portfolio",
        user="portfolio_user",
        password="password123",  # Use the password you set
        host="localhost",
        port="5432"
    )
    print("✅ Database connection successful!")
    
    # Try creating a test table
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_table (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100)
        );
    """)
    conn.commit()
    print("✅ Table creation successful!")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")