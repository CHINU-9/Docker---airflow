
from pathlib import Path
from minio import Minio
from minio.error import S3Error

# MinIO connection settings
MINIO_ENDPOINT = "localhost:9000"
ACCESS_KEY = "minioadmin"
SECRET_KEY = "ChangeThisPassword123!"
BUCKET_NAME = "raw-data"

# Source folders
BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIRS = [
    BASE_DIR / "source-data" / "csv",
    BASE_DIR / "source-data" / "json",
]

def main():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        secure=False,
    )

    # Check that the bucket exists
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"Created bucket: {BUCKET_NAME}")

    uploaded = 0

    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            print(f"Folder not found: {source_dir}")
            continue

        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in {".csv", ".json"}:
                continue

            # Keep CSV and JSON files organized in separate folders
            object_name = file_path.relative_to(BASE_DIR / "source-data").as_posix()

            try:
                client.fput_object(
                    BUCKET_NAME,
                    object_name,
                    str(file_path),
                )
                print(f"Uploaded: {object_name}")
                uploaded += 1
            except S3Error as error:
                print(f"Failed: {object_name} — {error}")

    print(f"\nUpload complete. Files uploaded: {uploaded}")

if __name__ == "__main__":
    main()
