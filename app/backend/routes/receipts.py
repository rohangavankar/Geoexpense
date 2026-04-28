import os
import base64
import json
import re
import uuid
from pathlib import Path

import anthropic
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from database import User
from deps import get_current_user

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def _parse_json(text: str) -> dict:
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


@router.post("/extract")
async def extract_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only JPEG, PNG, WEBP, and GIF images are supported")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(400, "File too large — max 10 MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = UPLOADS_DIR / filename
    path.write_bytes(data)
    receipt_url = f"/uploads/{filename}"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[receipts] ❌ ANTHROPIC_API_KEY not set — skipping Vision")
        return {"receipt_url": receipt_url, "extracted": {}, "error": "ANTHROPIC_API_KEY not set"}

    print(f"[receipts] 📷 Receipt uploaded: {filename} ({len(data)/1024:.1f} KB)")
    print(f"[receipts] 🤖 Sending to Claude Vision...")

    try:
        client = anthropic.Anthropic()
        b64 = base64.standard_b64encode(data).decode()

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": file.content_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract expense information from this receipt. "
                                "Return a JSON object with these fields (use null if not found):\n"
                                "{\n"
                                '  "vendor": "business name",\n'
                                '  "amount": 0.00,\n'
                                '  "date": "YYYY-MM-DD",\n'
                                '  "title": "short description e.g. Lunch at Vendor",\n'
                                '  "city": "city name or null"\n'
                                "}"
                            ),
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text
        print(f"[receipts] ✅ Claude raw response:\n{raw}")

        extracted = _parse_json(raw)

        if extracted.get("amount") is not None:
            try:
                extracted["amount"] = float(str(extracted["amount"]).replace("$", "").replace(",", ""))
            except (ValueError, TypeError):
                extracted["amount"] = None

        print(f"[receipts] 📦 Extracted: {extracted}")
        return {"receipt_url": receipt_url, "extracted": extracted}

    except Exception as e:
        print(f"[receipts] ❌ Error: {e}")
        return {"receipt_url": receipt_url, "extracted": {}, "error": str(e)}
