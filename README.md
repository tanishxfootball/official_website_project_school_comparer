# EduCompare India

A simple Flask app to compare schools, filter by location/board/fee, and add reviews.

## Quick Start (Windows PowerShell)

1. Create and activate virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. (Optional) set secret key:
```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
```

4. Run app:
```powershell
python app.py
```

Open: `http://127.0.0.1:5000`

## Notes

- Database file uses SQLite (`instance/schools.db`).
- Search can be shared/bookmarked via query params on `/`.
- Admin page requires a user with `is_admin=True` in database.
