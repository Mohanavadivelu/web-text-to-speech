"""Write the API's OpenAPI schema to web/src/api/openapi.json.

The web app generates its TypeScript types from this file (`npm run api:types`),
and CI fails if either file is out of date.

    python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.api.main import create_app  # noqa: E402

OUT = ROOT / "web" / "src" / "api" / "openapi.json"


def main() -> int:
    schema = create_app().openapi()
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:  # LF on every OS, like CI
        fh.write(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
