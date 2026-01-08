from pathlib import Path

from app.config import load_settings
from app.db import get_connection


def main() -> None:
    settings = load_settings()
    sqlite_path = Path(settings.sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    sql_path = Path(__file__).with_name("init_db.sql")
    sql = sql_path.read_text(encoding="utf-8")

    conn = get_connection(str(sqlite_path))
    conn.executescript(sql)
    conn.close()
    print(f"Initialized database at {sqlite_path}")


if __name__ == "__main__":
    main()