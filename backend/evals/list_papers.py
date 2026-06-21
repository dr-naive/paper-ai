from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="列出本地 SQLite 中可用于评测的论文")
    parser.add_argument("--database", default="paperai.db", help="SQLite 数据库路径")
    args = parser.parse_args()
    database = Path(args.database)
    if not database.exists():
        print(f"数据库不存在：{database.resolve()}")
        return 1

    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT p.id, p.title,
                   (SELECT COUNT(*) FROM sections s WHERE s.paper_id = p.id),
                   (SELECT COUNT(*) FROM tables t WHERE t.paper_id = p.id)
            FROM papers p
            ORDER BY p.uploaded_at DESC
            """
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        print("当前数据库没有论文。")
        return 0

    print(f"{'paper_id':36}  {'章节':>4}  {'表格':>4}  标题")
    print("-" * 110)
    for paper_id, title, section_count, table_count in rows:
        print(f"{paper_id:36}  {section_count:>4}  {table_count:>4}  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
