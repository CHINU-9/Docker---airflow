
import duckdb

con = duckdb.connect()

con.execute("INSTALL AND LOAD httpfs")
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

con.execute("""
    CREATE OR REPLACE TEMP VIEW contacts AS
    SELECT *
    FROM read_csv_auto(
        's3://raw-data/csv/salesforce_crm_contacts.csv',
        all_varchar = true
    )
""")

print("Duplicate Salesforce contact records:")

print(con.execute("""
    SELECT *
    FROM contacts
    WHERE Id = '003SYN000050'
""").fetchdf().to_string(index=False))

print("\nAre the two rows identical?")

print(con.execute("""
    SELECT COUNT(*) AS total_rows,
           COUNT(DISTINCT hash(
               AccountId, FirstName, LastName,
               Email, Title, CreatedDate
           )) AS distinct_records
    FROM contacts
    WHERE Id = '003SYN000050'
""").fetchdf().to_string(index=False))

con.close()
