
import duckdb

con = duckdb.connect()

con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

tables = [
    "salesforce_crm_accounts",
    "netsuite_transactions",
    "sfcc_orders",
    "cybersource_payments",
]

for table in tables:
    path = f"s3://raw-data/csv/{table}.csv"

    print(f"\n{'=' * 60}")
    print(f"TABLE: {table}")

    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW inspected AS
        SELECT *
        FROM read_csv_auto('{path}', all_varchar=true)
    """)

    print("First 5 records:")
    print(con.execute("SELECT * FROM inspected LIMIT 5").fetchdf().to_string(index=False))

    print("\nDistinct rows:", con.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT * FROM inspected)"
    ).fetchone()[0])

    print("Total rows:", con.execute(
        "SELECT COUNT(*) FROM inspected"
    ).fetchone()[0])

con.close()
