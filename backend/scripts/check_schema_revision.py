"""Print a read-only current-schema compatibility report.

Run before stamping an existing database:
    python -m scripts.check_schema_revision
"""

from __future__ import annotations

import asyncio
import json

from app.database import engine
from app.infrastructure.db.schema_preflight import inspect_schema
import app.models.chat  # noqa: F401,E402
import app.models.document  # noqa: F401,E402
import app.models.execution  # noqa: F401,E402
import app.models.evaluation  # noqa: F401,E402
import app.models.paper  # noqa: F401,E402
import app.models.project  # noqa: F401,E402
import app.models.research  # noqa: F401,E402
import app.models.user  # noqa: F401,E402


async def main() -> int:
    report = await inspect_schema(engine)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    await engine.dispose()
    return 0 if report.compatible else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
