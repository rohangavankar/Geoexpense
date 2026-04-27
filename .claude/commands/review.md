Review the GeoExpense codebase for code quality, security, and correctness.

Read these files:
- app/backend/main.py
- app/backend/database.py
- app/backend/sample_data.py
- app/frontend/app.js
- app/frontend/index.html

For each file, check:
1. **Security**: SQL injection, XSS vulnerabilities, exposed secrets, unsafe inputs
2. **Correctness**: edge cases, error handling, data validation at API boundaries
3. **API design**: proper HTTP status codes, consistent response shapes, missing validation
4. **Frontend**: unhandled promise rejections, XSS via innerHTML, missing null checks

After reading all files, provide:
- An overall quality score out of 100
- A prioritized list of issues (🔴 Error / 🟡 Warning / 🟢 Info) with file and line number
- Top 3 concrete improvements to make right now
- What's genuinely well done

Be specific — reference actual function names, line numbers, and variable names.
