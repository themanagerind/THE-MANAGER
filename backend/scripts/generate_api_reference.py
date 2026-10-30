"""
Regenerates HOUSING_BACKEND_COMPLETE_API_REFERENCE.md (repo root) from the
live FastAPI app's OpenAPI schema — CLAUDE.md Section 8 lists this file as
required reading but says to "generate from app.openapi() when needed"
rather than hand-maintain it; this is that generator. Run it after adding
or changing endpoints, before committing, so the doc never drifts from
app/main.py's actual routes.

Usage:
    python -m scripts.generate_api_reference
"""
from collections import defaultdict
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "HOUSING_BACKEND_COMPLETE_API_REFERENCE.md"
METHODS = ("get", "post", "put", "patch", "delete")


def _build_markdown() -> str:
    spec = app.openapi()
    by_tag: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            if method not in METHODS:
                continue
            tag = (op.get("tags") or ["untagged"])[0]
            text = op.get("summary") or (op.get("description") or "").strip().split("\n")[0]
            by_tag[tag].append((method.upper(), path, text.replace("|", "\\|")))

    total = sum(len(v) for v in by_tag.values())
    lines = [
        "# THE-MANAGER — Backend API Reference",
        "",
        f"Auto-generated from `app.openapi()` ({spec['info']['title']}) — {total} endpoints "
        f"across {len(by_tag)} modules. Regenerate with "
        "`python -m scripts.generate_api_reference` instead of hand-editing when endpoints "
        "change (see CLAUDE.md Section 8); the source of truth is always the live OpenAPI "
        "schema, not this file.",
        "",
        "All endpoints are mounted under `/api/v1` and require a Bearer JWT "
        "(`Authorization: Bearer <token>`) unless noted otherwise — see "
        "`app/core/security.py`'s `require_role()` for the exact role check on each one. "
        "Interactive docs (Swagger UI) are available at `/docs` when the server is running.",
        "",
    ]

    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| Method | Path | Summary |")
        lines.append("|---|---|---|")
        for method, path, text in sorted(by_tag[tag], key=lambda x: (x[1], x[0])):
            lines.append(f"| {method} | `{path}` | {text} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.write_text(_build_markdown())
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
