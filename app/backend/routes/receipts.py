import os
import base64
import json
import uuid
from pathlib import Path

import anthropic
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles

from database import User
from deps import get_current_user

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

UPLOADS_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


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

    # Save file
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = UPLOADS_DIR / filename
    path.write_bytes(data)
    receipt_url = f"/uploads/{filename}"

    # Send to Claude Vision
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"receipt_url": receipt_url, "extracted": {}}

    try:
        client = anthropic.Anthropic()
        b64 = base64.standard_b64encode(data).decode()
        media_type = file.content_type

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract expense information from this receipt. "
                                "Return ONLY a raw JSON object with these fields "
                                "(use null if not found): "
                                "{\"vendor\": \"...\", \"amount\": 0.00, \"date\": \"YYYY-MM-DD\", "
                                "\"title\": \"short description\", \"city\": \"city name or null\"}"
                            ),
                        },
                    ],
                },
                {"role": "assistant", "content": "{"},
            ],
        )

        raw = "{" + response.content[0].text
        extracted = json.loads(raw)
        return {"receipt_url": receipt_url, "extracted": extracted}

    except Exception as e:
        print(f"Receipt extraction error: {e}")
        return {"receipt_url": receipt_url, "extracted": {}}
