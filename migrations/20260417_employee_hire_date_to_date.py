from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "instance" / "job.db"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    backup_name = f"job.db.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = DB_PATH.with_name(backup_name)
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        column_info = cur.execute("PRAGMA table_info(employee)").fetchall()
        hire_date_info = next((row for row in column_info if row[1] == "hire_date"), None)
        if hire_date_info and hire_date_info[2].upper() == "DATE":
            print("Migration skipped: employee.hire_date already has DATE type.")
            return

        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")

        cur.execute(
            """
            CREATE TABLE employee_new (
                id INTEGER PRIMARY KEY,
                last_name VARCHAR(150) NOT NULL,
                first_name VARCHAR(150) NOT NULL,
                middle_name VARCHAR(150),
                email VARCHAR(255) NOT NULL UNIQUE,
                phone VARCHAR(150) NOT NULL UNIQUE,
                hire_date DATE,
                is_active BOOLEAN,
                position_id INTEGER,
                FOREIGN KEY(position_id) REFERENCES position(id)
            )
            """
        )

        cur.execute(
            """
            INSERT INTO employee_new (
                id, last_name, first_name, middle_name, email, phone, hire_date, is_active, position_id
            )
            SELECT
                id,
                last_name,
                first_name,
                middle_name,
                email,
                phone,
                CASE
                    WHEN hire_date IS NULL THEN NULL
                    ELSE substr(hire_date, 1, 10)
                END,
                is_active,
                position_id
            FROM employee
            """
        )

        cur.execute("DROP TABLE employee")
        cur.execute("ALTER TABLE employee_new RENAME TO employee")

        conn.commit()
        print("Migration applied: employee.hire_date DATETIME -> DATE")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.execute("PRAGMA foreign_keys=ON")
        conn.close()


if __name__ == "__main__":
    main()
