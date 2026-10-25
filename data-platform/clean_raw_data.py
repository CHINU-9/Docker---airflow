
import duckdb

con = duckdb.connect()

# Connect to MinIO
con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

# Create a separate bucket for cleaned data
con.execute("""
    CREATE SECRET IF NOT EXISTS minio_secret (
        TYPE S3,
        KEY_ID 'minioadmin',
        SECRET 'ChangeThisPassword123!',
        REGION 'us-east-1',
        ENDPOINT 'minio:9000',
        URL_STYLE 'path',
        USE_SSL false
    )
""")

# Make the destination bucket if needed using MinIO's API
from minio import Minio

client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="ChangeThisPassword123!",
    secure=False,
)

if not client.bucket_exists("clean-data"):
    client.make_bucket("clean-data")

tables = [
    "cybersource_payments",
    "netsuite_accounting_lines",
    "netsuite_transaction_lines",
    "netsuite_transactions",
    "salesforce_crm_accounts",
    "salesforce_crm_contacts",
    "salesforce_crm_leads",
    "salesforce_crm_opportunities",
    "sfcc_customers",
    "sfcc_order_lines",
    "sfcc_orders",
    "sfcc_products",
]

for table in tables:
    source = f"s3://raw-data/csv/{table}.csv"
    destination = f"s3://clean-data/{table}.parquet"

    print(f"\nCleaning {table}...")

    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_table AS
        SELECT *
        FROM read_csv_auto('{source}', all_varchar=true)
    """)

    before = con.execute(
        "SELECT COUNT(*) FROM raw_table"
    ).fetchone()[0]

    # Remove exact duplicate rows only
    con.execute("""
        CREATE OR REPLACE TEMP VIEW clean_table AS
        SELECT DISTINCT *
        FROM raw_table
    """)

    after = con.execute(
        "SELECT COUNT(*) FROM clean_table"
    ).fetchone()[0]

    # Write the cleaned table as Parquet
    con.execute(f"""
        COPY clean_table
        TO '{destination}'
        (FORMAT PARQUET, OVERWRITE_OR_IGNORE true)
    """)

    print(f"Rows before: {before}")
    print(f"Rows after:  {after}")
    print(f"Removed exact duplicates: {before - after}")
    print(f"Saved to: {destination}")

print("\nCleaning completed.")
con.close()
