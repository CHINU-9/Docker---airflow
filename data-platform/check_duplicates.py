
import duckdb

con = duckdb.connect()

con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

tables = {
    "cybersource_payments": "id",
    "netsuite_accounting_lines": "transactionId, transactionLine",
    "netsuite_transaction_lines": "transactionId, line",
    "netsuite_transactions": "id",
    "salesforce_crm_accounts": "Id",
    "salesforce_crm_contacts": "Id",
    "salesforce_crm_leads": "Id",
    "salesforce_crm_opportunities": "Id",
    "sfcc_customers": "customerNo",
    "sfcc_order_lines": "orderNo, lineNo",
    "sfcc_orders": "orderNo",
    "sfcc_products": "productId",
}

for table, keys in tables.items():
    path = f"s3://raw-data/csv/{table}.csv"
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_data AS
        SELECT * FROM read_csv_auto('{path}', all_varchar=true)
    """)

    key_expr = ", ".join(f'"{k.strip()}"' for k in keys.split(","))

    total = con.execute(
        "SELECT COUNT(*) FROM raw_data"
    ).fetchone()[0]

    distinct_rows = con.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_data)"
    ).fetchone()[0]

    duplicate_keys = con.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT {key_expr}
            FROM raw_data
            GROUP BY {key_expr}
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    print(
        f"{table}: total={total}, "
        f"distinct_rows={distinct_rows}, "
        f"duplicate_key_groups={duplicate_keys}"
    )

    if table == "cybersource_payments":
        print("Duplicate payment records:")
        print(con.execute("""
            SELECT id, COUNT(*) AS occurrences
            FROM raw_data
            GROUP BY id
            HAVING COUNT(*) > 1
        """).fetchdf().to_string(index=False))

con.close()
