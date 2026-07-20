#!/usr/bin/env python3
"""Render supplied synthetic PDF first pages for the verified web source viewer."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
SOURCE_DIR = ROOT / "synthetic_documents" / "documents"
OUTPUT_DIR = ROOT / "web" / "previews"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_path in sorted(SOURCE_DIR.glob("*.pdf")):
        subprocess.run(
            ["pdftoppm", "-f", "1", "-singlefile", "-png", "-r", "144", str(pdf_path), str(OUTPUT_DIR / pdf_path.stem)],
            check=True,
        )


if __name__ == "__main__":
    main()
