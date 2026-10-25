
import duckdb
import json
from pathlib import Path

con = duckdb.connect()

# Connect to MinIO
con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

# Read all CSV files from MinIO
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

report = {
    "source": "MinIO raw-data bucket",
    "tables": {},
}

for table in tables:
    path = f"s3://raw-data/csv/{table}.csv"

    print(f"\nChecking {table}...")

    try:
        # Register the raw CSV as a temporary DuckDB view
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW raw_data AS
            SELECT * FROM read_csv_auto('{path}', all_varchar=true)
            """
        )

        columns = con.execute(
            "DESCRIBE SELECT * FROM raw_data"
        ).fetchall()

        row_count = con.execute(
            "SELECT COUNT(*) FROM raw_data"
        ).fetchone()[0]

        column_names = [column[0] for column in columns]

        # Count missing values in each column
        missing_values = {}
        for column in column_names:
            quoted = '"' + column.replace('"', '""') + '"'
            count = con.execute(
                f"""
                SELECT COUNT(*)
                FROM raw_data
                WHERE {quoted} IS NULL
                   OR TRIM({quoted}) = ''
                """
            ).fetchone()[0]

            if count:
                missing_values[column] = count

        # Count exact duplicate rows
        duplicate_rows = con.execute(
            """
            SELECT COALESCE(SUM(row_count - 1), 0)
            FROM (
                SELECT COUNT(*) AS row_count
                FROM raw_data
                GROUP BY ALL
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        report["tables"][table] = {
            "row_count": row_count,
            "columns": column_names,
            "missing_values": missing_values,
            "exact_duplicate_rows": duplicate_rows,
        }

        print(f"Rows: {row_count}")
        print(f"Columns: {len(column_names)}")
        print(f"Columns with missing values: {missing_values}")
        print(f"Exact duplicate rows: {duplicate_rows}")

    except Exception as error:
        report["tables"][table] = {"error": str(error)}
        print(f"Validation error: {error}")

# Save the report inside the project folder
output_file = Path("/tmp/data_quality_report.json")
output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\nValidation profiling completed.")
print(f"Report saved to: {output_file}")

con.close()
