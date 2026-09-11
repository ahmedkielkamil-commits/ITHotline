import importlib
import os
import sys
from datetime import timedelta
from io import BytesIO
from pathlib import Path

ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "password")
BUCKET = os.environ.get("MINIO_BUCKET", "demo")
PRESIGNED_EXPIRY_SECONDS = int(os.environ.get("MINIO_PRESIGNED_EXPIRY", "3600"))


def _load_minio_lib():
    this_module = sys.modules[__name__]
    project_dir = Path(__file__).resolve().parent
    sys.modules.pop("minio", None)
    original_path = sys.path.copy()
    sys.path = [entry for entry in sys.path if Path(entry).resolve() != project_dir]
    try:
        return importlib.import_module("minio")
    finally:
        sys.path = original_path
        sys.modules["minio"] = this_module


_minio_lib = _load_minio_lib()
Minio = _minio_lib.Minio
DeleteObject = _minio_lib.deleteobjects.DeleteObject

client = Minio(
    ENDPOINT,
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    secure=False,
)


def ensure_bucket():
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)


def list_objects():
    ensure_bucket()
    return list(client.list_objects(BUCKET, recursive=True))


def upload_file(file_storage, object_name=None):
    ensure_bucket()
    name = object_name or file_storage.filename
    if not name:
        raise ValueError("No filename provided")

    file_storage.stream.seek(0)
    length = file_storage.content_length
    if length is None or length < 0:
        data = file_storage.read()
        length = len(data)
        stream = BytesIO(data)
    else:
        stream = file_storage.stream

    client.put_object(BUCKET, name, stream, length, content_type=file_storage.mimetype or "application/octet-stream")
    return name


def get_object(object_name):
    return client.get_object(BUCKET, object_name)


def presigned_url(object_name: str, expires_seconds: int | None = None) -> str:
    ensure_bucket()
    expiry = expires_seconds or PRESIGNED_EXPIRY_SECONDS
    return client.presigned_get_object(
        BUCKET,
        object_name,
        expires=timedelta(seconds=expiry),
    )


def upload_bytes(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    ensure_bucket()
    stream = BytesIO(data)
    client.put_object(BUCKET, object_name, stream, len(data), content_type=content_type)
    return object_name


def clear_bucket():
    ensure_bucket()
    to_delete = [
        DeleteObject(obj.object_name)
        for obj in client.list_objects(BUCKET, recursive=True)
    ]
    if not to_delete:
        return 0

    errors = list(client.remove_objects(BUCKET, to_delete))
    if errors:
        raise RuntimeError(f"Failed to delete {len(errors)} object(s).")

    return len(to_delete)
