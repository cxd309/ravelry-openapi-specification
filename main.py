"""
Generate docs/openapi.json from api_documentation.html.
"""

import json
from pathlib import Path

from ravelry import parser, generator

HTML_FILE = Path(__file__).parent / "api_documentation.html"
OUTPUT_FILE = Path(__file__).parent / "docs" / "openapi.json"


def main():
    print(f"Parsing: {HTML_FILE}")
    html_content = HTML_FILE.read_text(encoding="utf-8")

    print("Extracting API methods and result objects...")
    parsed = parser.parse(html_content)

    print("Building OpenAPI spec...")
    spec = generator.generate(parsed["api_groups"], parsed["result_objects"])

    OUTPUT_FILE.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"\nWritten: {OUTPUT_FILE} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
