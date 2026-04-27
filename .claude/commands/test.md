Run the GeoExpense test suite and fix any failures.

Steps:
1. Check if the server is running on port 8000:
   ```
   curl -s http://localhost:8000/api/expenses/summary
   ```
   If it's not running, start it:
   ```
   cd app/backend && PYTHONPATH=. python -m uvicorn main:app --port 8000 &
   sleep 3
   ```

2. Run the existing tests:
   ```
   TEST_BASE_URL=http://localhost:8000 python -m pytest tests/test_api.py -v --tb=short
   ```

3. Report results: how many passed, which failed and why.

4. If any tests failed:
   - Read the relevant source code to understand the root cause
   - Fix the issue in the source (not by weakening the test)
   - Re-run the failing tests to confirm they pass

5. If $ARGUMENTS is provided, also write a new test for that specific scenario and add it to tests/test_api.py.

Always run tests against the live server, not mocks.
