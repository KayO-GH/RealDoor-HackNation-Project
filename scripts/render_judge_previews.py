#!/usr/bin/env python3
"""Render supplied synthetic PDF first pages for the public source drawer."""

from pathlib import Path

import fitz


ROOT = Path(__file__).parents[1]
SOURCE_DIR = ROOT / "synthetic_documents" / "documents"
OUTPUT_DIR = ROOT / "public" / "previews"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_path in sorted(SOURCE_DIR.glob("*.pdf")):
        document = fitz.open(pdf_path)
        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(OUTPUT_DIR / f"{pdf_path.stem}.png")
        document.close()


if __name__ == "__main__":
    main()
