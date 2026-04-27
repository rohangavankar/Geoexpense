Validate that the GeoExpense project is correctly set up and ready to run.

Run these checks and report pass/fail for each:

**Dependencies**
```
pip install -r requirements.txt --dry-run 2>&1 | grep -E "Would install|already satisfied|error"
python -c "import fastapi, uvicorn, sqlalchemy, anthropic, httpx; print('All imports OK')"
```

**Syntax**
```
python -m py_compile app/backend/main.py app/backend/database.py app/backend/sample_data.py
```

**Environment**
- Check if ANTHROPIC_API_KEY is set (don't print the value)
- Warn if it's missing (AI categorization will be skipped)

**Server smoke test**
Start the server, hit /api/expenses/summary, then stop it:
```
cd app/backend && PYTHONPATH=. python -m uvicorn main:app --port 8765 &
sleep 3
curl -sf http://localhost:8765/api/expenses/summary && echo "API OK" || echo "API FAILED"
kill %1 2>/dev/null
```

**Frontend**
Confirm these files exist and are non-empty:
- app/frontend/index.html
- app/frontend/app.js
- app/frontend/styles.css

After all checks, summarize: what's good, what needs fixing, and the exact command to start the app.
