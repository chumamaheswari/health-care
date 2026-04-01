"""
Validates extracted invoice data against business rules.
"""

from dataclasses import dataclass, field


MIN_AMOUNT = 200.0

REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total_amount"]


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_invoice(invoice: dict, existing_invoice_numbers: set[str]) -> ValidationResult:
    """
    Validate a single invoice dict. Returns a ValidationResult.

    Rules:
    1. All required fields must be present and non-null.
    2. total_amount must be > $200.
    3. invoice_number must not be a duplicate.
    """
    errors = []
    warnings = []

    # Rule 1: Required fields
    for field_name in REQUIRED_FIELDS:
        if not invoice.get(field_name):
            errors.append(f"Missing required field: '{field_name}'")

    # Rule 2: Amount threshold
    amount = invoice.get("total_amount")
    if amount is not None:
        try:
            amount = float(amount)
            if amount <= MIN_AMOUNT:
                errors.append(
                    f"total_amount ${amount:.2f} is not above the ${MIN_AMOUNT:.2f} threshold"
                )
        except (TypeError, ValueError):
            errors.append(f"total_amount is not a valid number: {amount!r}")

    # Rule 3: Duplicate detection
    inv_num = invoice.get("invoice_number")
    if inv_num and str(inv_num) in existing_invoice_numbers:
        errors.append(f"Duplicate invoice number detected: '{inv_num}'")

    # Warnings for missing optional data
    if not invoice.get("line_items"):
        warnings.append("No line items found")
    if not invoice.get("currency"):
        warnings.append("Currency not detected, defaulting to USD")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
