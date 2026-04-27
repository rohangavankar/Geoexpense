Start the GeoExpense server and confirm it's fully working.

1. **Kill any existing instance** on port 8000:
   ```
   lsof -ti:8000 | xargs kill -9 2>/dev/null || true
   ```

2. **Start the server**:
   ```
   cd app/backend && PYTHONPATH=. python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Run this in the background.

3. **Wait for it to be ready** — poll until the health check passes (max 15 seconds):
   ```
   for i in $(seq 1 15); do curl -sf http://localhost:8000/api/expenses/summary && break || sleep 1; done
   ```

4. **Verify the app is working correctly**:
   - GET /api/expenses — confirm expenses are returned
   - GET /api/expenses/summary — confirm totals look correct
   - Check the expense count is greater than 0 (sample data loaded)
   - Open http://localhost:8000 and confirm the HTML is served

5. **Report**:
   - The URL the app is running at
   - Number of expenses loaded
   - Total expense amount and tax-deductible amount
   - Any warnings (e.g. ANTHROPIC_API_KEY not set)

If the server fails to start, read the error output and diagnose the root cause — don't just report that it failed.
