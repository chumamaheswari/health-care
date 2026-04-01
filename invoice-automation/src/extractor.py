"""
Extracts structured invoice data from PDF/image files using Claude API.
"""

import base64
import json
import re
from pathlib import Path

import anthropic
import pdfplumber
from PIL import Image
import pytesseract


SYSTEM_PROMPT = """You are an invoice data extraction specialist.
Extract invoice data from the provided text/image and return ONLY a valid JSON object.
Do not include any explanation or markdown — just the raw JSON.

Required fields (use null if not found):
{
  "vendor_name": "string or null",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD string or null",
  "total_amount": number or null,
  "currency": "string, default USD",
  "line_items": [
    {"description": "string", "quantity": number or null, "unit_price": number or null, "amount": number or null}
  ]
}"""


def _extract_pdf_text(file_path: Path) -> str:
    """Extract raw text from a PDF file."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_image_text(file_path: Path) -> str:
    """Extract text from an image using OCR."""
    img = Image.open(file_path)
    return pytesseract.image_to_string(img)


def _image_to_base64(file_path: Path) -> tuple[str, str]:
    """Convert image to base64 and return (data, media_type)."""
    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def _call_claude(client: anthropic.Anthropic, content: list) -> dict:
    """Send content to Claude and parse JSON response."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")

    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    return json.loads(text)


def extract_invoice(file_path: str | Path, client: anthropic.Anthropic) -> dict:
    """
    Extract structured data from a PDF or image invoice.

    Returns a dict with keys: vendor_name, invoice_number, invoice_date,
    total_amount, currency, line_items, source_file.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        text = _extract_pdf_text(file_path)
        content = [{"type": "text", "text": f"Invoice text:\n\n{text}"}]
    elif suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        # Send image directly to Claude Vision
        data, media_type = _image_to_base64(file_path)
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            },
            {"type": "text", "text": "Extract all invoice data from this image."},
        ]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    result = _call_claude(client, content)
    result["source_file"] = file_path.name
    return result
