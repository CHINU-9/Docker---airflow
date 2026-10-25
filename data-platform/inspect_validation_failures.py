
import duckdb
import json
from pathlib import Path

con = duckdb.connect()

# --------------------------------------------------
# 1. Connect to MinIO
# --------------------------------------------------
con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

# --------------------------------------------------
# 2. Load cleaned Parquet tables
# --------------------------------------------------
tables = {
    "salesforce_crm_opportunities": "salesforce_crm_opportunities",
    "netsuite_accounting_lines": "netsuite_accounting_lines",
    "sfcc_order_lines": "sfcc_order_lines",
    "sfcc_products": "sfcc_products",
    "sfcc_orders": "sfcc_orders",
    "sfcc_customers": "sfcc_customers",
    "salesforce_crm_contacts": "salesforce_crm_contacts",
    "salesforce_crm_accounts": "salesforce_crm_accounts",
    "netsuite_transaction_lines": "netsuite_transaction_lines",
    "netsuite_transactions": "netsuite_transactions",
    "cybersource_payments": "cybersource_payments",
}

for table, filename in tables.items():
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW "{table}" AS
        SELECT *
        FROM read_parquet('s3://clean-data/{filename}.parquet')
    """)

# --------------------------------------------------
# 3. Report structure
# --------------------------------------------------
report = {
    "source": "MinIO clean-data bucket",
    "treatment_policy": {
        "missing_phone_or_website":
            "Keep record; preserve missing value as NULL.",
        "missing_reconciliation_id":
            "Keep record and investigate payment status/business rules.",
        "invalid_quantity_or_price":
            "Quarantine record pending correction.",
        "broken_relationship":
            "Quarantine record pending key investigation.",
    },
    "findings": [],
    "summary": {},
}

def fetch_records(query):
    """Return query results as JSON-compatible dictionaries."""
    df = con.execute(query).fetchdf()
    return json.loads(df.to_json(orient="records", date_format="iso"))

def add_finding(category, table, rule, treatment, query):
    records = fetch_records(query)

    report["findings"].append({
        "category": category,
        "table": table,
        "rule": rule,
        "possible_treatment": treatment,
        "record_count": len(records),
        "records": records,
    })

    print(f"\n{'=' * 65}")
    print(f"Category: {category}")
    print(f"Table: {table}")
    print(f"Rule: {rule}")
    print(f"Treatment: {treatment}")
    print(f"Records found: {len(records)}")

    for record in records:
        print(record)

# --------------------------------------------------
# 4. Missing Phone or Website
# Treatment: keep records, normalize blanks to NULL
# in a future clean output; do not discard records.
# --------------------------------------------------
add_finding(
    category="Missing phone or website",
    table="salesforce_crm_accounts",
    rule="Phone or Website is NULL or blank",
    treatment=(
        "Keep the record; preserve missing values "
        "or standardize blank values to NULL."
    ),
    query="""
        SELECT *,
            CASE
                WHEN (Phone IS NULL OR TRIM(Phone) = '')
                 AND (Website IS NULL OR TRIM(Website) = '')
                    THEN 'Phone and Website missing'
                WHEN Phone IS NULL OR TRIM(Phone) = ''
                    THEN 'Phone missing'
                ELSE 'Website missing'
            END AS validation_issue
        FROM salesforce_crm_accounts
        WHERE Phone IS NULL OR TRIM(Phone) = ''
           OR Website IS NULL OR TRIM(Website) = ''
    """,
)

# --------------------------------------------------
# 5. Missing reconciliation ID
# Treatment: retain and investigate payment status.
# --------------------------------------------------
add_finding(
    category="Missing reconciliation ID",
    table="cybersource_payments",
    rule="reconciliationId is NULL or blank",
    treatment=(
        "Keep the record; investigate payment status "
        "and business rules before deciding what to do."
    ),
    query="""
        SELECT *
        FROM cybersource_payments
        WHERE reconciliationId IS NULL
           OR TRIM(reconciliationId) = ''
    """,
)

# --------------------------------------------------
# 6. Invalid quantity or price
# Treatment: quarantine records pending correction.
# --------------------------------------------------
add_finding(
    category="Invalid quantity",
    table="sfcc_order_lines",
    rule="Quantity is not numeric or is <= 0",
    treatment="Quarantine until corrected or approved.",
    query="""
        SELECT *,
            'Invalid quantity' AS validation_issue
        FROM sfcc_order_lines
        WHERE TRY_CAST(quantity AS DOUBLE) IS NULL
           OR TRY_CAST(quantity AS DOUBLE) <= 0
    """,
)

add_finding(
    category="Invalid price",
    table="sfcc_order_lines",
    rule="Unit price is not numeric or is < 0",
    treatment="Quarantine until corrected or approved.",
    query="""
        SELECT *,
            'Invalid unit price' AS validation_issue
        FROM sfcc_order_lines
        WHERE TRY_CAST(unitPrice AS DOUBLE) IS NULL
           OR TRY_CAST(unitPrice AS DOUBLE) < 0
    """,
)

add_finding(
    category="Invalid price",
    table="sfcc_products",
    rule="Base price is not numeric or is < 0",
    treatment="Quarantine until corrected or approved.",
    query="""
        SELECT *,
            'Invalid base price' AS validation_issue
        FROM sfcc_products
        WHERE TRY_CAST(basePrice AS DOUBLE) IS NULL
           OR TRY_CAST(basePrice AS DOUBLE) < 0
    """,
)

# --------------------------------------------------
# 7. Broken relationships
# Treatment: quarantine unresolved child records.
# --------------------------------------------------
relationships = [
    (
        "sfcc_orders", "customerNo",
        "sfcc_customers", "customerNo"
    ),
    (
        "salesforce_crm_contacts", "AccountId",
        "salesforce_crm_accounts", "Id"
    ),
    (
        "netsuite_transaction_lines", "transactionId",
        "netsuite_transactions", "id"
    ),
    (
        "cybersource_payments",
        "clientReferenceInformation.code",
        "sfcc_orders", "orderNo"
    ),
    (
        "sfcc_order_lines", "orderNo",
        "sfcc_orders", "orderNo"
    ),
    (
        "sfcc_order_lines", "productId",
        "sfcc_products", "productId"
    ),
    (
        "salesforce_crm_opportunities", "AccountId",
        "salesforce_crm_accounts", "Id"
    ),
    (
        "netsuite_accounting_lines", "transactionId",
        "netsuite_transactions", "id"
    ),
]

for child, child_key, parent, parent_key in relationships:
    child_col = '"' + child_key.replace('"', '""') + '"'
    parent_col = '"' + parent_key.replace('"', '""') + '"'

    add_finding(
        category="Broken relationship",
        table=child,
        rule=f"{child_key} does not match {parent}.{parent_key}",
        treatment=(
            "Quarantine unresolved child records; "
            "investigate the key before correction."
        ),
        query=f"""
            SELECT c.*,
                   'Missing parent: {parent}' AS validation_issue
            FROM "{child}" c
            WHERE c.{child_col} IS NOT NULL
              AND TRIM(CAST(c.{child_col} AS VARCHAR)) <> ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM "{parent}" p
                  WHERE p.{parent_col} = c.{child_col}
              )
        """,
    )

# --------------------------------------------------
# 8. Summary and output
# --------------------------------------------------
for finding in report["findings"]:
    key = finding["category"]
    report["summary"][key] = (
        report["summary"].get(key, 0)
        + finding["record_count"]
    )

output_file = Path("/tmp/validation_treatment_report.json")
output_file.write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("\n" + "=" * 65)
print("VALIDATION INSPECTION COMPLETE")
print(json.dumps(report["summary"], indent=2))
print(f"Report saved to: {output_file}")
print("No source or Parquet data files were modified.")

con.close()
