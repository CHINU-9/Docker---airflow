
import duckdb

con = duckdb.connect()

# Load the S3-compatible storage extension
con.execute("INSTALL AND LOAD httpfs")

# Configure MinIO
con.execute("SET s3_endpoint = 'minio:9000'")
con.execute("SET s3_access_key_id = 'minioadmin'")
con.execute("SET s3_secret_access_key = 'ChangeThisPassword123!'")
con.execute("SET s3_region = 'us-east-1'")
con.execute("SET s3_url_style = 'path'")
con.execute("SET s3_use_ssl = false")

print("DuckDB connected to MinIO configuration.")

# List CSV files in the raw-data bucket
query = """
SELECT file
FROM glob('s3://raw-data/csv/*.csv')
"""

try:
    files = con.execute(query).fetchall()

    if files:
        print("\nCSV files found in MinIO:")
        for file in files:
            print(file[0])
    else:
        print("No CSV files found at s3://raw-data/csv/")

except Exception as error:
    print("Could not list CSV files.")
    print("Error:", error)

con.close()
