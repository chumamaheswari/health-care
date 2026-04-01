"""
Stores processed invoice data in SQLite, CSV, and JSON formats.
"""

import csv
import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "output" / "invoices.db"
CSV_PATH = Path(__file__).parent.parent / "output" / "invoices.csv"
JSON_PATH = Path(__file__).parent.parent / "output" / "invoices.json"

CSV_FIELDS = [
    "id", "vendor_name", "invoice_number", "invoice_date",
    "total_amount", "currency", "source_file", "processed_at",
]


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create the database and tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name     TEXT,
            invoice_number  TEXT UNIQUE,
            invoice_date    TEXT,
            total_amount    REAL,
            currency        TEXT DEFAULT 'USD',
            source_file     TEXT,
            processed_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS line_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id  INTEGER REFERENCES invoices(id),
            description TEXT,
            quantity    REAL,
            unit_price  REAL,
            amount      REAL
        )
    """)
    conn.commit()
    return conn


def save_invoice(invoice: dict, conn: sqlite3.Connection) -> int:
    """Insert an invoice (and its line items) into the database. Returns the new row id."""
    cur = conn.execute(
        """
        INSERT INTO invoices (vendor_name, invoice_number, invoice_date,
                              total_amount, currency, source_file)
        VALUES (:vendor_name, :invoice_number, :invoice_date,
                :total_amount, :currency, :source_file)
        """,
        {
            "vendor_name":    invoice.get("vendor_name"),
            "invoice_number": invoice.get("invoice_number"),
            "invoice_date":   invoice.get("invoice_date"),
            "total_amount":   invoice.get("total_amount"),
            "currency":       invoice.get("currency", "USD"),
            "source_file":    invoice.get("source_file"),
        },
    )
    invoice_id = cur.lastrowid

    for item in invoice.get("line_items") or []:
        conn.execute(
            """
            INSERT INTO line_items (invoice_id, description, quantity, unit_price, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (invoice_id, item.get("description"), item.get("quantity"),
             item.get("unit_price"), item.get("amount")),
        )

    conn.commit()
    return invoice_id


def get_all_invoice_numbers(conn: sqlite3.Connection) -> set[str]:
    """Return all invoice numbers already in the database."""
    rows = conn.execute("SELECT invoice_number FROM invoices").fetchall()
    return {row["invoice_number"] for row in rows if row["invoice_number"]}


def export_csv(conn: sqlite3.Connection, csv_path: Path = CSV_PATH) -> None:
    """Export all invoices to a CSV file."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        "SELECT id, vendor_name, invoice_number, invoice_date, "
        "total_amount, currency, source_file, processed_at FROM invoices"
    ).fetchall()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])


def export_json(conn: sqlite3.Connection, json_path: Path = JSON_PATH) -> None:
    """Export all invoices (with line items) to a JSON file."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    invoices = conn.execute(
        "SELECT id, vendor_name, invoice_number, invoice_date, "
        "total_amount, currency, source_file, processed_at FROM invoices"
    ).fetchall()

    output = []
    for inv in invoices:
        inv_dict = dict(inv)
        items = conn.execute(
            "SELECT description, quantity, unit_price, amount "
            "FROM line_items WHERE invoice_id = ?",
            (inv_dict["id"],),
        ).fetchall()
        inv_dict["line_items"] = [dict(i) for i in items]
        output.append(inv_dict)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
