import subprocess
import sys
import time
from pathlib import Path


script_directory = Path(__file__).resolve().parent
project_directory = script_directory.parent

# Позволяет импортировать run_lab.py из папки scripts.
sys.path.insert(0, str(script_directory))

from run_lab import query


# Ожидаем готовности Trino: максимум 60 попыток по 2 секунды.
for attempt in range(60):
    try:
        query("SELECT 1", "bi_readiness")
        print("Trino готов к проверке BI.")
        break
    except Exception as exc:
        if attempt == 59:
            raise RuntimeError(
                "Trino не стал доступен за 120 секунд."
            ) from exc

        time.sleep(2)


# Запускаем check_app.py внутри работающего контейнера bi.
subprocess.run(
    [
        "docker",
        "compose",
        "exec",
        "-T",
        "bi",
        "python",
        "/app/check_app.py",
    ],
    check=True,
    cwd=project_directory,
)

print("Проверка BI успешно завершена.")