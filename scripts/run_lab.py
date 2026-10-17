"""Run real TPC-H Q10 ELT and repeatable local benchmark.

The script uses only Python standard library modules.
"""

import argparse
import csv
import datetime
import json
import math
import random
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SQL_DIRECTORY = ROOT / "sql"

RESULTS.mkdir(parents=True, exist_ok=True)
SQL_DIRECTORY.mkdir(parents=True, exist_ok=True)

TRINO_URL = "http://localhost:18080/v1/statement"

TRINO_HEADERS = {
    "X-Trino-User": "lab",
    "X-Trino-Source": "lab1-q10",
    "Content-Type": "text/plain; charset=utf-8",
}

COLUMNS = {
    "customer": (
        "custkey, name, acctbal, nationkey, "
        "address, phone, comment"
    ),
    "orders": (
        "orderkey, custkey, orderdate"
    ),
    "lineitem": (
        "orderkey, linenumber, extendedprice, "
        "discount, returnflag"
    ),
    "nation": (
        "nationkey, name"
    ),
}

VARIANTS = [
    ("bronze_gzip", "PARQUET", "GZIP"),
    ("bronze", "PARQUET", "ZSTD"),
    ("bronze_orc", "ORC", "ZSTD"),
    ("bronze_none", "PARQUET", "NONE"),
]


def read_trino_response(request):
    """Отправить HTTP-запрос в Trino и прочитать JSON-ответ."""

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            return json.load(response)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"Trino HTTP error {exc.code}: {body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Не удалось подключиться к Trino: {exc.reason}"
        ) from exc


def query(sql, label="query"):
    """Выполнить SQL в Trino и вернуть строки, колонки и метрики."""

    start = time.perf_counter()

    request = urllib.request.Request(
        TRINO_URL,
        data=sql.encode("utf-8"),
        headers=TRINO_HEADERS,
        method="POST",
    )

    response = read_trino_response(request)

    rows = []
    columns = []
    query_id = response.get("id")

    while True:
        if "error" in response:
            error = response["error"]
            message = error.get("message", "Неизвестная ошибка Trino")
            error_name = error.get("errorName")
            error_type = error.get("errorType")

            details = [message]

            if error_name:
                details.append(f"errorName={error_name}")

            if error_type:
                details.append(f"errorType={error_type}")

            raise RuntimeError(
                f"{label}: {'; '.join(details)}\n"
                f"Query ID: {query_id}\n"
                f"SQL:\n{sql}"
            )

        if "columns" in response:
            columns = [
                column["name"]
                for column in response["columns"]
            ]

        rows.extend(response.get("data", []))

        next_uri = response.get("nextUri")

        if not next_uri:
            break

        next_request = urllib.request.Request(
            next_uri,
            headers=TRINO_HEADERS,
            method="GET",
        )

        response = read_trino_response(next_request)

        if query_id is None:
            query_id = response.get("id")

    elapsed = time.perf_counter() - start
    stats = response.get("stats", {})

    record = {
        "label": label,
        "query_id": query_id,
        "wall_seconds": elapsed,
        "stats": stats,
        "sql": sql,
    }

    with (RESULTS / "queries.jsonl").open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

    return {
        "columns": columns,
        "rows": rows,
        "seconds": elapsed,
        "query_id": query_id,
        "stats": stats,
    }


def save(filename, data):
    """Сохранить Python-объект в JSON."""

    path = RESULTS / filename

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_sql(filename, sql):
    """Сохранить выполняемый SQL в отдельный файл."""

    path = SQL_DIRECTORY / filename

    path.write_text(
        sql.strip().rstrip(";") + ";\n",
        encoding="utf-8",
    )


def q10(schema):
    """Вернуть запрос TPC-H Q10 для указанной схемы."""

    return f"""
        SELECT
            c.custkey,
            c.name,
            sum(
                l.extendedprice * (1 - l.discount)
            ) AS revenue,
            c.acctbal,
            n.name AS nation,
            c.address,
            c.phone,
            c.comment
        FROM {schema}.customer AS c
        JOIN {schema}.orders AS o
            ON c.custkey = o.custkey
        JOIN {schema}.lineitem AS l
            ON l.orderkey = o.orderkey
        JOIN {schema}.nation AS n
            ON c.nationkey = n.nationkey
        WHERE o.orderdate >= DATE '1993-10-01'
          AND o.orderdate < DATE '1994-01-01'
          AND l.returnflag = 'R'
        GROUP BY
            c.custkey,
            c.name,
            c.acctbal,
            n.name,
            c.address,
            c.phone,
            c.comment
        ORDER BY
            revenue DESC,
            c.custkey
        LIMIT 20
    """


def table_stats(schema, table):
    """Получить количество строк, файлов и размер Iceberg-таблицы."""

    row_count = query(
        f"""
            SELECT count(*)
            FROM lakehouse.{schema}.{table}
        """,
        f"count_{schema}_{table}",
    )

    file_stats = query(
        f"""
            SELECT
                count(*),
                coalesce(sum(file_size_in_bytes), 0)
            FROM lakehouse.{schema}."{table}$files"
            WHERE content = 0
        """,
        f"files_{schema}_{table}",
    )

    return {
        "table": f"{schema}.{table}",
        "rows": row_count["rows"][0][0],
        "data_files": file_stats["rows"][0][0],
        "bytes": file_stats["rows"][0][1],
    }


def equivalent(expected, actual):
    """Проверить соответствие результата эталонному Q10."""

    assert expected["columns"] == actual["columns"], (
        "Состав колонок не совпадает",
        expected["columns"],
        actual["columns"],
    )

    assert len(expected["rows"]) == 20, (
        "Эталонный Q10 должен вернуть 20 строк",
        len(expected["rows"]),
    )

    assert len(actual["rows"]) == 20, (
        "Проверяемый запрос должен вернуть 20 строк",
        len(actual["rows"]),
    )

    for row_number, (expected_row, actual_row) in enumerate(
        zip(expected["rows"], actual["rows"]),
        start=1,
    ):
        for column_number, (expected_value, actual_value) in enumerate(
            zip(expected_row, actual_row),
            start=1,
        ):
            if isinstance(expected_value, float) or isinstance(
                actual_value,
                float,
            ):
                assert math.isclose(
                    float(expected_value),
                    float(actual_value),
                    rel_tol=1e-10,
                    abs_tol=1e-6,
                ), (
                    f"Числовое значение не совпадает: "
                    f"строка {row_number}, колонка {column_number}",
                    expected_value,
                    actual_value,
                )
            else:
                assert expected_value == actual_value, (
                    f"Значение не совпадает: "
                    f"строка {row_number}, колонка {column_number}",
                    expected_value,
                    actual_value,
                )


def wait_for_trino():
    """Ожидать готовности Trino не более трёх минут."""

    print("Ожидание готовности Trino...", flush=True)

    for attempt in range(90):
        try:
            query("SELECT 1", "readiness")
            print("Trino готов.", flush=True)
            return

        except Exception:
            if attempt == 89:
                raise

            time.sleep(2)


def table_exists(schema, table):
    """Проверить существование таблицы в Iceberg-каталоге."""

    result = query(
        f"""
            SELECT count(*)
            FROM lakehouse.information_schema.tables
            WHERE table_schema = '{schema}'
              AND table_name = '{table}'
        """,
        f"exists_{schema}_{table}",
    )

    return result["rows"][0][0] > 0


def create_bronze_variants(scale):
    """Создать варианты Bronze и собрать метрики записи."""

    metrics = []
    writes = []

    writes_path = RESULTS / "writes.json"

    if writes_path.exists():
        old_writes = json.loads(
            writes_path.read_text(encoding="utf-8")
        )
    else:
        old_writes = []

    for schema, file_format, codec in VARIANTS:
        query(
            f"CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}",
            f"create_schema_{schema}",
        )

        for table, columns in COLUMNS.items():
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS
                    lakehouse.{schema}.{table}
                WITH (
                    format = '{file_format}',
                    compression_codec = '{codec}'
                )
                AS
                SELECT {columns}
                FROM tpch.{scale}.{table}
            """

            save_sql(
                f"02_{schema}_{table}.sql",
                create_sql,
            )

            if table_exists(schema, table):
                print(
                    f"Повторно используется {schema}.{table}; "
                    f"сохраняется исходное время записи.",
                    flush=True,
                )

                matching = [
                    item
                    for item in old_writes
                    if item["table"] == f"{schema}.{table}"
                ]

                if not matching:
                    raise RuntimeError(
                        f"Таблица {schema}.{table} уже существует, "
                        f"но её измерение отсутствует в writes.json. "
                        f"Используйте пустой каталог results и "
                        f"новый Compose-проект либо восстановите "
                        f"results/writes.json."
                    )

                writes.append(matching[0])

            else:
                result = query(
                    create_sql,
                    f"write_{schema}_{table}",
                )

                writes.append(
                    {
                        "table": f"{schema}.{table}",
                        "format": file_format,
                        "codec": codec,
                        "seconds": result["seconds"],
                        "query_id": result["query_id"],
                    }
                )

            save("writes.json", writes)

            metric = table_stats(schema, table)
            metric.update(
                format=file_format,
                codec=codec,
                columns=columns,
            )

            metrics.append(metric)
            save("table_metrics.json", metrics)

            print(
                f"{schema}.{table}: "
                f"{metric['rows']:,} строк, "
                f"{metric['bytes'] / 1_000_000:.2f} МБ",
                flush=True,
            )

    return metrics, writes


def check_bronze_variants(baseline):
    """Сравнить каждый Bronze-вариант с исходным TPC-H Q10."""

    for schema, _, _ in VARIANTS:
        result = query(
            q10(f"lakehouse.{schema}"),
            f"check_{schema}",
        )

        equivalent(baseline, result)

        save_sql(
            f"03_q10_{schema}.sql",
            q10(f"lakehouse.{schema}"),
        )


def run_benchmark(args, baseline, metrics, writes):
    """Выполнить прогрев и измеряемые запуски Q10."""

    print("Прогрев вариантов Bronze...", flush=True)

    for schema, _, _ in VARIANTS:
        query(
            q10(f"lakehouse.{schema}"),
            f"warmup_{schema}",
        )

    runs = []
    random_generator = random.Random(20261016)

    for repetition in range(args.repeats):
        order = list(VARIANTS)
        random_generator.shuffle(order)

        for schema, file_format, codec in order:
            result = query(
                q10(f"lakehouse.{schema}"),
                f"benchmark_{schema}",
            )

            equivalent(baseline, result)

            runs.append(
                {
                    "schema": schema,
                    "format": file_format,
                    "codec": codec,
                    "round": repetition + 1,
                    "seconds": result["seconds"],
                    "query_id": result["query_id"],
                    "server_elapsed_ms": result["stats"].get(
                        "elapsedTimeMillis"
                    ),
                    "processed_bytes": result["stats"].get(
                        "processedBytes"
                    ),
                }
            )

            save("benchmark_runs.json", runs)

            print(
                f"Раунд {repetition + 1}: "
                f"{schema} — {result['seconds']:.3f} с",
                flush=True,
            )

    benchmark = []

    for schema, file_format, codec in VARIANTS:
        times = [
            item["seconds"]
            for item in runs
            if item["schema"] == schema
        ]

        total_bytes = sum(
            item["bytes"]
            for item in metrics
            if item["table"].startswith(f"{schema}.")
        )

        write_seconds = sum(
            item["seconds"]
            for item in writes
            if item["table"].startswith(f"{schema}.")
        )

        benchmark.append(
            {
                "schema": schema,
                "format": file_format,
                "codec": codec,
                "bytes": total_bytes,
                "write_seconds": write_seconds,
                "median_seconds": statistics.median(times),
                "min_seconds": min(times),
                "max_seconds": max(times),
                "runs": len(times),
            }
        )

    save("benchmark.json", benchmark)

    with (RESULTS / "benchmark.csv").open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(benchmark[0]),
        )
        writer.writeheader()
        writer.writerows(benchmark)

    return benchmark


def create_silver_and_gold(baseline, metrics):
    """Создать Silver и Gold и проверить результат."""

    query(
        "CREATE SCHEMA IF NOT EXISTS lakehouse.silver",
        "create_silver_schema",
    )

    query(
        "CREATE SCHEMA IF NOT EXISTS lakehouse.gold",
        "create_gold_schema",
    )

    transformations = [
        (
            "04_silver_customers.sql",
            """
                CREATE TABLE IF NOT EXISTS
                    lakehouse.silver.customer_dim
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    c.custkey,
                    c.name,
                    c.acctbal,
                    n.name AS nation,
                    c.address,
                    c.phone,
                    c.comment,
                    trim(c.name) AS name_normalized,
                    trim(c.address) AS address_normalized,
                    trim(c.comment) AS comment_normalized
                FROM lakehouse.bronze.customer AS c
                JOIN lakehouse.bronze.nation AS n
                    ON c.nationkey = n.nationkey
                WHERE c.custkey IS NOT NULL
            """,
        ),
        (
            "05_silver_returns.sql",
            """
                CREATE TABLE IF NOT EXISTS
                    lakehouse.silver.returned_lines
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    o.custkey,
                    o.orderkey,
                    l.linenumber,
                    o.orderdate,
                    l.extendedprice,
                    l.discount,
                    l.extendedprice * (1 - l.discount) AS revenue
                FROM lakehouse.bronze.orders AS o
                JOIN lakehouse.bronze.lineitem AS l
                    ON l.orderkey = o.orderkey
                WHERE o.orderdate >= DATE '1993-10-01'
                  AND o.orderdate < DATE '1994-01-01'
                  AND upper(trim(l.returnflag)) = 'R'
                  AND l.extendedprice >= 0
                  AND l.discount BETWEEN 0 AND 1
            """,
        ),
        (
            "06_gold.sql",
            """
                CREATE TABLE IF NOT EXISTS
                    lakehouse.gold.returned_customers_top20
                WITH (
                    format = 'PARQUET',
                    compression_codec = 'ZSTD'
                )
                AS
                SELECT
                    c.custkey,
                    c.name,
                    sum(l.revenue) AS revenue,
                    c.acctbal,
                    c.nation,
                    c.address,
                    c.phone,
                    c.comment
                FROM lakehouse.silver.customer_dim AS c
                JOIN lakehouse.silver.returned_lines AS l
                    ON c.custkey = l.custkey
                GROUP BY
                    c.custkey,
                    c.name,
                    c.acctbal,
                    c.nation,
                    c.address,
                    c.phone,
                    c.comment
                ORDER BY
                    revenue DESC,
                    c.custkey
                LIMIT 20
            """,
        ),
    ]

    for filename, sql in transformations:
        save_sql(filename, sql)
        query(sql, filename)

    gold = query(
        """
            SELECT *
            FROM lakehouse.gold.returned_customers_top20
            ORDER BY revenue DESC, custkey
        """,
        "gold_result",
    )

    equivalent(baseline, gold)
    save("gold_top20.json", gold)

    with (RESULTS / "gold_top20.csv").open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(gold["columns"])
        writer.writerows(gold["rows"])

    for schema, table in [
        ("silver", "customer_dim"),
        ("silver", "returned_lines"),
        ("gold", "returned_customers_top20"),
    ]:
        metric = table_stats(schema, table)
        metric.update(
            format="PARQUET",
            codec="ZSTD",
        )
        metrics.append(metric)

    save("table_metrics.json", metrics)


def run_quality_checks():
    """Выполнить проверки качества Bronze."""

    check_sql = {
        "customer_duplicates": """
            SELECT count(*) - count(DISTINCT custkey)
            FROM lakehouse.bronze.customer
        """,
        "order_duplicates": """
            SELECT count(*) - count(DISTINCT orderkey)
            FROM lakehouse.bronze.orders
        """,
        "line_duplicates": """
            SELECT count(*)
            FROM (
                SELECT orderkey, linenumber
                FROM lakehouse.bronze.lineitem
                GROUP BY orderkey, linenumber
                HAVING count(*) > 1
            )
        """,
        "invalid_money": """
            SELECT count(*)
            FROM lakehouse.bronze.lineitem
            WHERE extendedprice IS NULL
               OR extendedprice < 0
               OR discount IS NULL
               OR discount NOT BETWEEN 0 AND 1
        """,
        "orphan_orders": """
            SELECT count(*)
            FROM lakehouse.bronze.orders AS o
            LEFT JOIN lakehouse.bronze.customer AS c
                ON o.custkey = c.custkey
            WHERE c.custkey IS NULL
        """,
        "orphan_lines": """
            SELECT count(*)
            FROM lakehouse.bronze.lineitem AS l
            LEFT JOIN lakehouse.bronze.orders AS o
                ON o.orderkey = l.orderkey
            WHERE o.orderkey IS NULL
        """,
        "orphan_nations": """
            SELECT count(*)
            FROM lakehouse.bronze.customer AS c
            LEFT JOIN lakehouse.bronze.nation AS n
                ON n.nationkey = c.nationkey
            WHERE n.nationkey IS NULL
        """,
    }

    checks = {}

    for label, sql in check_sql.items():
        checks[label] = query(
            sql,
            label,
        )["rows"][0][0]

        assert checks[label] == 0, (
            label,
            checks[label],
        )

    save_sql(
        "07_quality.sql",
        ";\n\n".join(
            sql.strip()
            for sql in check_sql.values()
        ),
    )

    checks["gold_matches_tpch"] = True
    checks["all_bronze_variants_match_tpch"] = True

    save("checks.json", checks)


def run_schema_evolution():
    """Продемонстрировать добавление и переименование колонки."""

    # Таблица используется только для демонстрации.
    # Пересоздание делает проверку повторяемой даже после
    # незавершённого предыдущего запуска.
    query(
        "DROP TABLE IF EXISTS lakehouse.silver.evolution_demo",
        "drop_evolution_demo",
    )

    create_sql = """
        CREATE TABLE lakehouse.silver.evolution_demo
        WITH (
            format = 'PARQUET',
            compression_codec = 'ZSTD'
        )
        AS
        SELECT
            custkey,
            name
        FROM lakehouse.silver.customer_dim
        LIMIT 3
    """

    query(create_sql, "create_evolution_demo")

    before = query(
        """
            SELECT *
            FROM lakehouse.silver.evolution_demo
            ORDER BY custkey
        """,
        "evolution_before",
    )

    add_column_sql = """
        ALTER TABLE lakehouse.silver.evolution_demo
        ADD COLUMN source VARCHAR
    """

    rename_column_sql = """
        ALTER TABLE lakehouse.silver.evolution_demo
        RENAME COLUMN source TO data_source
    """

    query(add_column_sql, "evolution_add_column")
    query(rename_column_sql, "evolution_rename_column")

    after = query(
        """
            SELECT *
            FROM lakehouse.silver.evolution_demo
            ORDER BY custkey
        """,
        "evolution_after",
    )

    assert len(before["rows"]) == 3
    assert len(after["rows"]) == 3
    assert "data_source" in after["columns"]

    save(
        "schema_evolution.json",
        {
            "before": before,
            "after": after,
        },
    )

    save_sql(
        "08_schema_evolution.sql",
        (
            create_sql
            + ";\n\n"
            + add_column_sql
            + ";\n\n"
            + rename_column_sql
        ),
    )


def run_time_travel():
    """Продемонстрировать time travel и rollback Iceberg."""

    snapshot_result = query(
        """
            SELECT snapshot_id
            FROM lakehouse.silver."evolution_demo$snapshots"
            ORDER BY committed_at DESC
            LIMIT 1
        """,
        "get_snapshot",
    )

    snapshot_id = int(snapshot_result["rows"][0][0])

    old_count = query(
        """
            SELECT count(*)
            FROM lakehouse.silver.evolution_demo
        """,
        "count_before_insert",
    )["rows"][0][0]

    insert_sql = """
        INSERT INTO lakehouse.silver.evolution_demo
        VALUES (-1, 'temporary row', 'demo')
    """

    query(insert_sql, "time_travel_insert")

    new_count = query(
        """
            SELECT count(*)
            FROM lakehouse.silver.evolution_demo
        """,
        "count_after_insert",
    )["rows"][0][0]

    travel_sql = f"""
        SELECT count(*)
        FROM lakehouse.silver.evolution_demo
        FOR VERSION AS OF {snapshot_id}
    """

    historical_count = query(
        travel_sql,
        "historical_count",
    )["rows"][0][0]

    rollback_sql = f"""
        ALTER TABLE lakehouse.silver.evolution_demo
        EXECUTE rollback_to_snapshot({snapshot_id})
    """

    query(rollback_sql, "rollback_to_snapshot")

    restored_count = query(
        """
            SELECT count(*)
            FROM lakehouse.silver.evolution_demo
        """,
        "count_after_rollback",
    )["rows"][0][0]

    assert (
        old_count,
        new_count,
        historical_count,
        restored_count,
    ) == (3, 4, 3, 3)

    save(
        "time_travel.json",
        {
            "snapshot_id": snapshot_id,
            "before": old_count,
            "after_insert": new_count,
            "historical": historical_count,
            "restored": restored_count,
        },
    )

    save_sql(
        "09_time_travel.sql",
        f"""
            -- Snapshot ID необходимо получать перед повторным запуском.
            {insert_sql};

            {travel_sql};

            {rollback_sql}
        """,
    )


def run(args):
    """Выполнить весь процесс загрузки, проверки и измерений."""

    environment_path = RESULTS / "environment.json"

    if environment_path.exists():
        previous_environment = json.loads(
            environment_path.read_text(encoding="utf-8")
        )
    else:
        previous_environment = {}

    previous_scale = previous_environment.get(
        "scale",
        args.scale,
    )

    if previous_scale != args.scale:
        raise RuntimeError(
            "Масштаб отличается от сохранённых результатов. "
            "Используйте отдельный Compose-проект и пустой "
            "каталог results."
        )

    wait_for_trino()

    environment = {
        "started_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "scale": args.scale,
        "repeats": args.repeats,
        "version": query(
            "SELECT version()",
            "trino_version",
        )["rows"][0][0],
    }

    save("environment.json", environment)

    print("Выполнение эталонного Q10...", flush=True)

    baseline_sql = q10(f"tpch.{args.scale}")

    baseline = query(
        baseline_sql,
        "reference",
    )

    save("reference.json", baseline)
    save_sql("01_reference.sql", baseline_sql)

    print("Создание вариантов Bronze...", flush=True)

    metrics, writes = create_bronze_variants(args.scale)

    print("Проверка вариантов Bronze...", flush=True)

    check_bronze_variants(baseline)

    print("Запуск benchmark...", flush=True)

    run_benchmark(
        args,
        baseline,
        metrics,
        writes,
    )

    print("Создание Silver и Gold...", flush=True)

    create_silver_and_gold(
        baseline,
        metrics,
    )

    print("Проверки качества...", flush=True)

    run_quality_checks()

    print("Проверка schema evolution...", flush=True)

    run_schema_evolution()

    print("Проверка time travel и rollback...", flush=True)

    run_time_travel()

    environment["finished_at"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    save("environment.json", environment)

    print(
        "SUCCESS: варианты Bronze, Gold, проверки качества, "
        "schema evolution и rollback успешно проверены.",
        flush=True,
    )


def parse_arguments():
    """Прочитать аргументы командной строки."""

    parser = argparse.ArgumentParser(
        description=(
            "Загрузка TPC-H Q10, построение медальонных слоёв "
            "и локальный benchmark."
        )
    )

    parser.add_argument(
        "--scale",
        default="sf1",
        choices=[
            "tiny",
            "sf1",
            "sf10",
        ],
        help="Масштаб данных TPC-H.",
    )

    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Количество измеряемых запусков каждого варианта.",
    )

    arguments = parser.parse_args()

    if arguments.repeats < 3:
        parser.error(
            "Требуется не менее трёх измеряемых повторов."
        )

    return arguments


if __name__ == "__main__":
    run(parse_arguments())