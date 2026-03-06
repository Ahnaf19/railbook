Audit documentation for sync with current codebase and fix any drift.

Steps:
1. Read all router files (`backend/app/*/router.py`) to get the current endpoint list
2. Compare against `docs/api/API_REFERENCE.md` and `README.md` API table — flag missing/outdated endpoints
3. Read `backend/app/models.py` and compare against `docs/architecture/DATABASE.md` — flag schema drift
4. Read `docs/postman/railbook.postman_collection.json` — verify all endpoints exist in the collection
5. Check `docs/api/ERROR_CODES.md` against actual HTTPException raises in service files
6. Report what's out of sync
7. Fix all drift by updating the documentation files
8. Do NOT change source code — only update docs to match current code
