from app.services import storage


class FakeS3Client:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        self.created_buckets: list[str] = []

    def head_bucket(self, Bucket: str) -> None:
        return None

    def create_bucket(self, Bucket: str) -> None:
        self.created_buckets.append(Bucket)

    def generate_presigned_url(self, operation_name: str, Params: dict, ExpiresIn: int) -> str:
        return f"{self.endpoint_url}/{operation_name}/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"


def test_storage_service_uses_public_endpoint_for_presigned_urls(monkeypatch) -> None:
    created_clients: list[FakeS3Client] = []

    def fake_boto3_client(*args, **kwargs):
        client = FakeS3Client(kwargs["endpoint_url"])
        created_clients.append(client)
        return client

    monkeypatch.setattr(storage, "boto3", type("FakeBoto3", (), {"client": staticmethod(fake_boto3_client)}))
    monkeypatch.setattr(storage.settings, "MINIO_SERVER", "minio:9000")
    monkeypatch.setattr(storage.settings, "MINIO_PUBLIC_URL", "http://localhost:9000")
    monkeypatch.setattr(storage.settings, "MINIO_ACCESS_KEY", "minio")
    monkeypatch.setattr(storage.settings, "MINIO_SECRET_KEY", "secret")

    service = storage.StorageService()
    response = service.generate_presigned_put_url(
        tenant_id=1,
        process_id=2,
        filename="arquivo.pdf",
        content_type="application/pdf",
    )

    assert len(created_clients) == 2
    assert created_clients[0].endpoint_url == "http://minio:9000"
    assert created_clients[1].endpoint_url == "http://localhost:9000"
    assert response["upload_url"].startswith("http://localhost:9000/")


def test_storage_service_reuses_internal_endpoint_when_public_url_is_not_set(monkeypatch) -> None:
    created_clients: list[FakeS3Client] = []

    def fake_boto3_client(*args, **kwargs):
        client = FakeS3Client(kwargs["endpoint_url"])
        created_clients.append(client)
        return client

    monkeypatch.setattr(storage, "boto3", type("FakeBoto3", (), {"client": staticmethod(fake_boto3_client)}))
    monkeypatch.setattr(storage.settings, "MINIO_SERVER", "localhost:9000")
    monkeypatch.setattr(storage.settings, "MINIO_PUBLIC_URL", "")
    monkeypatch.setattr(storage.settings, "MINIO_ACCESS_KEY", "minio")
    monkeypatch.setattr(storage.settings, "MINIO_SECRET_KEY", "secret")

    service = storage.StorageService()
    response = service.generate_presigned_get_url("tenant_1/process_1/documento.pdf")

    assert len(created_clients) == 1
    assert created_clients[0].endpoint_url == "http://localhost:9000"
    assert response.startswith("http://localhost:9000/")


def test_get_storage_service_returns_cached_instance(monkeypatch) -> None:
    created_clients: list[FakeS3Client] = []

    def fake_boto3_client(*args, **kwargs):
        client = FakeS3Client(kwargs["endpoint_url"])
        created_clients.append(client)
        return client

    storage.get_storage_service.cache_clear()
    monkeypatch.setattr(storage.StorageService, "_bucket_ready", False)
    monkeypatch.setattr(storage, "boto3", type("FakeBoto3", (), {"client": staticmethod(fake_boto3_client)}))
    monkeypatch.setattr(storage.settings, "MINIO_SERVER", "localhost:9000")
    monkeypatch.setattr(storage.settings, "MINIO_PUBLIC_URL", "")
    monkeypatch.setattr(storage.settings, "MINIO_ACCESS_KEY", "minio")
    monkeypatch.setattr(storage.settings, "MINIO_SECRET_KEY", "secret")

    service_a = storage.get_storage_service()
    service_b = storage.get_storage_service()

    assert service_a is service_b
    assert len(created_clients) == 1
