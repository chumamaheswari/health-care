"""
Main orchestrator for the invoice automation pipeline.

Usage:
    python src/main.py [--invoices-dir PATH] [--push] [--repo PATH] [--branch BRANCH]

Steps:
    1. Scan invoices/ directory for PDF/image files.
    2. Extract structured data with Claude API.
    3. Validate each invoice.
    4. Save valid invoices to SQLite, export CSV + JSON.
    5. Optionally commit and push output files to GitHub.
"""

import argparse
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from extractor import extract_invoice
from validator import validate_invoice
from storage import init_db, save_invoice, get_all_invoice_numbers, export_csv, export_json
from github_pusher import push_to_github

load_dotenv()

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp"}

OUTPUT_DIR = Path(__file__).parent.parent / "output"
CSV_PATH = OUTPUT_DIR / "invoices.csv"
JSON_PATH = OUTPUT_DIR / "invoices.json"


def find_invoices(directory: Path) -> list[Path]:
    return [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def run(
    invoices_dir: Path,
    push: bool = False,
    repo_path: Path | None = None,
    branch: str = "main",
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Check your .env file.")

    client = anthropic.Anthropic(api_key=api_key)
    conn = init_db()
    existing_numbers = get_all_invoice_numbers(conn)

    files = find_invoices(invoices_dir)
    if not files:
        print(f"No invoice files found in {invoices_dir}")
        return

    print(f"Found {len(files)} invoice file(s) to process.\n")

    results = {"processed": 0, "valid": 0, "invalid": 0, "errors": 0}

    for file_path in files:
        print(f"── {file_path.name}")

        # Step 1: Extract
        try:
            invoice = extract_invoice(file_path, client)
        except Exception as exc:
            print(f"   [ERROR] Extraction failed: {exc}\n")
            results["errors"] += 1
            continue

        results["processed"] += 1

        # Step 2: Validate
        validation = validate_invoice(invoice, existing_numbers)

        for warning in validation.warnings:
            print(f"   [WARN]  {warning}")

        if not validation.is_valid:
            results["invalid"] += 1
            for error in validation.errors:
                print(f"   [FAIL]  {error}")
            print()
            continue

        # Step 3: Save
        invoice_id = save_invoice(invoice, conn)
        existing_numbers.add(str(invoice.get("invoice_number", "")))
        results["valid"] += 1

        print(f"   [OK]    Saved as invoice #{invoice_id} | "
              f"{invoice.get('vendor_name')} | "
              f"${invoice.get('total_amount'):.2f}")
        print()

    # Step 4: Export
    export_csv(conn, CSV_PATH)
    export_json(conn, JSON_PATH)
    print(f"Exported → {CSV_PATH.name}, {JSON_PATH.name}")

    # Step 5: Push to GitHub
    if push:
        effective_repo = repo_path or Path(os.getenv("GITHUB_REPO_PATH", "."))
        effective_branch = branch or os.getenv("GITHUB_BRANCH", "main")
        try:
            push_to_github(
                repo_path=effective_repo,
                files_to_add=[CSV_PATH, JSON_PATH],
                commit_message=(
                    f"chore: update invoice data — "
                    f"{results['valid']} new, {results['invalid']} rejected"
                ),
                branch=effective_branch,
            )
        except Exception as exc:
            print(f"[ERROR] GitHub push failed: {exc}")

    conn.close()
    print(
        f"\nSummary: {results['processed']} processed, "
        f"{results['valid']} valid, "
        f"{results['invalid']} invalid, "
        f"{results['errors']} extraction errors."
    )


def main():
    parser = argparse.ArgumentParser(description="Invoice automation pipeline")
    parser.add_argument(
        "--invoices-dir",
        type=Path,
        default=Path(__file__).parent.parent / "invoices",
        help="Directory containing invoice PDF/image files",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Commit and push output files to GitHub after processing",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Path to the local git repository (overrides GITHUB_REPO_PATH in .env)",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Git branch to push to (default: main)",
    )
    args = parser.parse_args()
    run(args.invoices_dir, push=args.push, repo_path=args.repo, branch=args.branch)


if __name__ == "__main__":
    main()
