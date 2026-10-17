import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


# Запускаем Streamlit-приложение.
app = AppTest.from_file(
    "/app/app.py",
    default_timeout=180,
).run()


# Проверяем, что приложение запустилось без ошибок.
assert not app.exception, f"Исключения при запуске: {app.exception}"
assert not app.error, f"Ошибки интерфейса при запуске: {app.error}"

# В Bronze должны отображаться:
# 1. Предпросмотр выбранной таблицы.
# 2. Агрегация выручки по странам.
assert len(app.dataframe) >= 2, (
    f"Ожидалось не менее двух таблиц, получено: {len(app.dataframe)}"
)


observed = {}

bronze_tables = [
    "customer",
    "orders",
    "lineitem",
    "nation",
]


# Проверяем предпросмотр каждой Bronze-таблицы.
for table_name in bronze_tables:
    app.selectbox[0].set_value(table_name).run(timeout=180)

    assert not app.exception, (
        f"Исключение при открытии {table_name}: {app.exception}"
    )
    assert not app.error, (
        f"Ошибка интерфейса при открытии {table_name}: {app.error}"
    )

    dataframe = app.dataframe[0].value

    expected_rows = 25 if table_name == "nation" else 100

    assert len(dataframe) == expected_rows, (
        f"Таблица {table_name}: ожидалось {expected_rows} строк, "
        f"получено {len(dataframe)}"
    )

    observed[table_name] = {
        "rows_shown": len(dataframe),
        "columns": list(dataframe.columns),
    }


# В TPC-H используется 25 стран, поэтому агрегат должен содержать 25 строк.
nation_dataframe = app.dataframe[1].value

assert len(nation_dataframe) == 25, (
    "Агрегат по странам должен содержать 25 строк, "
    f"получено: {len(nation_dataframe)}"
)


# Переключаем приложение на Gold.
app.radio[0].set_value("Gold").run(timeout=180)

assert not app.exception, (
    f"Исключение при открытии Gold: {app.exception}"
)
assert not app.error, (
    f"Ошибка интерфейса при открытии Gold: {app.error}"
)

gold_dataframe = app.dataframe[0].value

assert len(gold_dataframe) == 20, (
    "Gold-витрина должна содержать 20 строк, "
    f"получено: {len(gold_dataframe)}"
)


# Формируем результат проверки.
result = {
    "bronze": observed,
    "nation_aggregate_rows": len(nation_dataframe),
    "gold_rows": len(gold_dataframe),
    "ui_errors": 0,
}


# Сохраняем результат в JSON.
results_directory = Path("/results")
results_directory.mkdir(parents=True, exist_ok=True)

result_path = results_directory / "bi_check.json"

result_path.write_text(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )
)