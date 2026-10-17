"""Create MinIO bucket and configure Lakekeeper warehouse."""

import datetime
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


LAKEKEEPER_URL = "http://localhost:18181"
MINIO_HOST = "localhost:19000"

PROJECT_ID = "00000000-0000-0000-0000-000000000000"

BUCKET_NAME = "lakehouse"
WAREHOUSE_NAME = "lab1"

S3_REGION = "us-east-1"
S3_ACCESS_KEY = "labadmin"
S3_SECRET_KEY = "lab_local_password"


def request(url, data=None, method=None, headers=None):
    """Выполнить JSON-запрос и вернуть тело ответа как текст."""

    request_headers = {
        "Content-Type": "application/json",
    }

    if headers:
        request_headers.update(headers)

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    http_request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers=request_headers,
    )

    with urllib.request.urlopen(
        http_request,
        timeout=30,
    ) as response:
        return response.read().decode("utf-8")


def signing_key(secret_key, date, region, service):
    """Сформировать ключ AWS Signature Version 4."""

    def sign(key, value):
        return hmac.new(
            key,
            value.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    date_key = sign(
        ("AWS4" + secret_key).encode("utf-8"),
        date,
    )

    region_key = sign(
        date_key,
        region,
    )

    service_key = sign(
        region_key,
        service,
    )

    return sign(
        service_key,
        "aws4_request",
    )


def minio_error_code(body):
    """Получить S3 error code из XML-ответа MinIO."""

    try:
        root = ET.fromstring(body)
        return root.findtext("Code")
    except ET.ParseError:
        return None


def create_bucket():
    """Создать S3 bucket в MinIO через AWS Signature Version 4."""

    now = datetime.datetime.now(datetime.timezone.utc)

    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")

    path = f"/{BUCKET_NAME}"

    payload_hash = hashlib.sha256(b"").hexdigest()

    canonical_headers = (
        f"host:{MINIO_HOST}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{timestamp}\n"
    )

    signed_headers = (
        "host;"
        "x-amz-content-sha256;"
        "x-amz-date"
    )

    canonical_request = (
        "PUT\n"
        f"{path}\n"
        "\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    credential_scope = (
        f"{date}/"
        f"{S3_REGION}/"
        "s3/"
        "aws4_request"
    )

    canonical_request_hash = hashlib.sha256(
        canonical_request.encode("utf-8")
    ).hexdigest()

    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{canonical_request_hash}"
    )

    key = signing_key(
        S3_SECRET_KEY,
        date,
        S3_REGION,
        "s3",
    )

    signature = hmac.new(
        key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={S3_ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    bucket_request = urllib.request.Request(
        f"http://{MINIO_HOST}{path}",
        data=b"",
        method="PUT",
        headers={
            "Host": MINIO_HOST,
            "x-amz-date": timestamp,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization,
        },
    )

    try:
        with urllib.request.urlopen(
            bucket_request,
            timeout=30,
        ) as response:
            print(
                f"Bucket {BUCKET_NAME!r} создан: "
                f"HTTP {response.status}"
            )

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        error_code = minio_error_code(body)

        if (
            exc.code == 409
            and error_code == "BucketAlreadyOwnedByYou"
        ):
            print(
                f"Bucket {BUCKET_NAME!r} уже существует."
            )
            return

        raise RuntimeError(
            f"Не удалось создать bucket {BUCKET_NAME!r}: "
            f"HTTP {exc.code}, "
            f"code={error_code}, "
            f"body={body}"
        ) from exc


def wait_for_lakekeeper():
    """Ожидать готовности Lakekeeper не более 120 секунд."""

    print("Ожидание готовности Lakekeeper...", flush=True)

    last_error = None

    for attempt in range(60):
        try:
            request(
                f"{LAKEKEEPER_URL}/health",
                method="GET",
            )

            print("Lakekeeper готов.", flush=True)
            return

        except Exception as exc:
            last_error = exc

            if attempt < 59:
                time.sleep(2)

    raise RuntimeError(
        "Lakekeeper не стал доступен за 120 секунд."
    ) from last_error


def create_minio_bucket():
    """Создать bucket, ожидая готовности MinIO."""

    print("Создание bucket в MinIO...", flush=True)

    last_error = None

    for attempt in range(60):
        try:
            create_bucket()
            return

        except urllib.error.URLError as exc:
            last_error = exc

        except RuntimeError as exc:
            last_error = exc

            # Ошибки авторизации и конфигурации повторять бессмысленно.
            text = str(exc)

            if (
                "HTTP 400" in text
                or "HTTP 401" in text
                or "HTTP 403" in text
                or "HTTP 409" in text
            ):
                raise

        if attempt < 59:
            time.sleep(2)

    raise RuntimeError(
        "MinIO не стал доступен за 120 секунд."
    ) from last_error


def bootstrap_lakekeeper():
    """Выполнить первоначальную настройку Lakekeeper."""

    print("Проверка bootstrap Lakekeeper...", flush=True)

    try:
        response = request(
            f"{LAKEKEEPER_URL}/management/v1/bootstrap",
            data={
                "accept-terms-of-use": True,
            },
            method="POST",
        )

        # Успешный bootstrap обычно возвращает HTTP 204
        # и поэтому не содержит тела ответа.
        if response:
            print(f"Bootstrap: {response}")
        else:
            print("Bootstrap Lakekeeper выполнен.")

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        if exc.code == 409:
            print("Lakekeeper уже настроен.")
            return

        # Некоторые старые версии могли возвращать HTTP 400
        # при повторном bootstrap. Игнорируем его только тогда,
        # когда ответ действительно говорит о завершённом bootstrap.
        lower_body = body.lower()

        already_bootstrapped = (
            exc.code == 400
            and "bootstrap" in lower_body
            and (
                "already" in lower_body
                or "closed" in lower_body
                or "completed" in lower_body
            )
        )

        if already_bootstrapped:
            print("Lakekeeper уже настроен.")
            return

        raise RuntimeError(
            "Ошибка bootstrap Lakekeeper: "
            f"HTTP {exc.code}, body={body}"
        ) from exc


def get_warehouses():
    """Получить список warehouses проекта."""

    response = request(
        f"{LAKEKEEPER_URL}/management/v1/warehouse",
        method="GET",
        headers={
            "x-project-id": PROJECT_ID,
        },
    )

    if not response:
        return []

    result = json.loads(response)

    return result.get("warehouses", [])


def create_warehouse():
    """Создать warehouse lab1, если он ещё не существует."""

    warehouses = get_warehouses()

    for warehouse in warehouses:
        warehouse_name = warehouse.get(
            "name",
            warehouse.get("warehouse-name"),
        )

        if warehouse_name == WAREHOUSE_NAME:
            print(
                f"Warehouse {WAREHOUSE_NAME!r} уже существует."
            )
            return

    warehouse_data = {
        "warehouse-name": WAREHOUSE_NAME,
        "storage-profile": {
            "type": "s3",
            "bucket": BUCKET_NAME,
            "key-prefix": WAREHOUSE_NAME,
            "endpoint": "http://minio:9000",
            "region": S3_REGION,
            "path-style-access": True,
            "flavor": "s3-compat",
            "sts-enabled": False,
        },
        "storage-credential": {
            "type": "s3",
            "credential-type": "access-key",
            "access-key-id": S3_ACCESS_KEY,
            "secret-access-key": S3_SECRET_KEY,
        },
    }

    try:
        response = request(
            f"{LAKEKEEPER_URL}/management/v1/warehouse",
            data=warehouse_data,
            method="POST",
            headers={
                "x-project-id": PROJECT_ID,
            },
        )

    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Не удалось создать warehouse {WAREHOUSE_NAME!r}: "
            f"HTTP {exc.code}, body={body}"
        ) from exc

    if response:
        print(f"Warehouse создан: {response}")
    else:
        print(f"Warehouse {WAREHOUSE_NAME!r} создан.")


def main():
    """Подготовить MinIO и Lakekeeper к запуску ELT."""

    wait_for_lakekeeper()
    create_minio_bucket()
    bootstrap_lakekeeper()
    create_warehouse()

    print("Warehouse ready")


if __name__ == "__main__":
    main()