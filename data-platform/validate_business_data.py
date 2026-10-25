
import duckdb
import json
from pathlib import Path

con = duckdb.connect()

# Connect DuckDB to MinIO
con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

# Read deduplicated Parquet files from clean-data
tables = {
    "sfcc_customers": "s3://clean-data/sfcc_customers.parquet",
    "sfcc_orders": "s3://clean-data/sfcc_orders.parquet",
    "sfcc_order_lines": "s3://clean-data/sfcc_order_lines.parquet",
    "sfcc_products": "s3://clean-data/sfcc_products.parquet",
    "salesforce_crm_accounts": "s3://clean-data/salesforce_crm_accounts.parquet",
    "salesforce_crm_contacts": "s3://clean-data/salesforce_crm_contacts.parquet",
    "salesforce_crm_opportunities": "s3://clean-data/salesforce_crm_opportunities.parquet",
    "netsuite_transactions": "s3://clean-data/netsuite_transactions.parquet",
    "netsuite_transaction_lines": "s3://clean-data/netsuite_transaction_lines.parquet",
    "netsuite_accounting_lines": "s3://clean-data/netsuite_accounting_lines.parquet",
    "cybersource_payments": "s3://clean-data/cybersource_payments.parquet",
}

report = {
    "source": "MinIO clean-data bucket",
    "missing_values": [],
    "invalid_records": [],
    "relationships": [],
}

# Register each Parquet file as a temporary DuckDB view
for table, path in tables.items():
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW "{table}" AS
        SELECT * FROM read_parquet('{path}')
    """)

# 1. Missing-value checks
for table in tables:
    columns = con.execute(
        f'DESCRIBE SELECT * FROM "{table}"'
    ).fetchall()

    for column_info in columns:
        column = column_info[0]
        quoted_column = '"' + column.replace('"', '""') + '"'

        missing = con.execute(f"""
            SELECT COUNT(*)
            FROM "{table}"
            WHERE {quoted_column} IS NULL
               OR TRIM(CAST({quoted_column} AS VARCHAR)) = ''
        """).fetchone()[0]

        if missing:
            report["missing_values"].append({
                "table": table,
                "column": column,
                "count": missing,
            })

# 2. Basic invalid-value checks
checks = [
    (
        "sfcc_order_lines",
        "quantity",
        "TRY_CAST(quantity AS DOUBLE) IS NULL OR TRY_CAST(quantity AS DOUBLE) <= 0",
        "Quantity must be a positive number",
    ),
    (
        "sfcc_order_lines",
        "unitPrice",
        "TRY_CAST(unitPrice AS DOUBLE) IS NULL OR TRY_CAST(unitPrice AS DOUBLE) < 0",
        "Unit price must be a non-negative number",
    ),
    (
        "sfcc_products",
        "basePrice",
        "TRY_CAST(basePrice AS DOUBLE) IS NULL OR TRY_CAST(basePrice AS DOUBLE) < 0",
        "Base price must be a non-negative number",
    ),
    (
        "sfcc_products",
        "inventory",
        "TRY_CAST(inventory AS BIGINT) IS NULL OR TRY_CAST(inventory AS BIGINT) < 0",
        "Inventory must be a non-negative integer",
    ),
    (
        "sfcc_orders",
        "totalGrossPrice",
        "TRY_CAST(totalGrossPrice AS DOUBLE) IS NULL OR TRY_CAST(totalGrossPrice AS DOUBLE) < 0",
        "Order total must be a non-negative number",
    ),
    (
        "cybersource_payments",
        "orderInformation.amountDetails.totalAmount",
        "TRY_CAST(\"orderInformation.amountDetails.totalAmount\" AS DOUBLE) IS NULL OR TRY_CAST(\"orderInformation.amountDetails.totalAmount\" AS DOUBLE) < 0",
        "Payment amount must be a non-negative number",
    ),
]

for table, column, condition, description in checks:
    result = con.execute(f"""
        SELECT COUNT(*)
        FROM "{table}"
        WHERE {condition}
    """).fetchone()[0]

    report["invalid_records"].append({
        "table": table,
        "rule": description,
        "invalid_count": result,
    })

# 3. Broken relationship checks
relationships = [
    (
        "sfcc_orders",
        "customerNo",
        "sfcc_customers",
        "customerNo",
    ),
    (
        "sfcc_order_lines",
        "orderNo",
        "sfcc_orders",
        "orderNo",
    ),
    (
        "sfcc_order_lines",
        "productId",
        "sfcc_products",
        "productId",
    ),
    (
        "salesforce_crm_contacts",
        "AccountId",
        "salesforce_crm_accounts",
        "Id",
    ),
    (
        "salesforce_crm_opportunities",
        "AccountId",
        "salesforce_crm_accounts",
        "Id",
    ),
    (
        "netsuite_transaction_lines",
        "transactionId",
        "netsuite_transactions",
        "id",
    ),
    (
        "netsuite_accounting_lines",
        "transactionId",
        "netsuite_transactions",
        "id",
    ),
    (
        "cybersource_payments",
        "clientReferenceInformation.code",
        "sfcc_orders",
        "orderNo",
    ),
]

for child, child_key, parent, parent_key in relationships:
    child_col = '"' + child_key.replace('"', '""') + '"'
    parent_col = '"' + parent_key.replace('"', '""') + '"'

    invalid_count = con.execute(f"""
        SELECT COUNT(*)
        FROM "{child}" c
        WHERE c.{child_col} IS NOT NULL
          AND TRIM(CAST(c.{child_col} AS VARCHAR)) <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM "{parent}" p
              WHERE p.{parent_col} = c.{child_col}
          )
    """).fetchone()[0]

    report["relationships"].append({
        "child_table": child,
        "child_column": child_key,
        "parent_table": parent,
        "parent_column": parent_key,
        "orphan_count": invalid_count,
    })

# Save report
output = Path("/tmp/business_validation_report.json")
output.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("BUSINESS DATA VALIDATION COMPLETE")
print("Missing-value findings:", len(report["missing_values"]))
print("Invalid-value rules checked:", len(report["invalid_records"]))
print("Relationships checked:", len(report["relationships"]))
print("Report saved to:", output)

print("\nMISSING VALUES")
print(json.dumps(report["missing_values"], indent=2))

print("\nINVALID RECORDS")
print(json.dumps(report["invalid_records"], indent=2))

print("\nBROKEN RELATIONSHIPS")
print(json.dumps(report["relationships"], indent=2))

con.close()
