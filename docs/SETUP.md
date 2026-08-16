# Team LEX Local Development Setup

This guide sets up the current Lex AI prototype for local development.

## Prerequisites

- Git
- Python 3.10 or newer
- Node.js 20.19+ or 22.12+
- npm

The repository contains two application parts:

- Django backend at the repository root
- React/Vite frontend in `frontend/`

## 1. Clone the repository

```bash
git clone https://github.com/AnisaAhmovic/Team-LEX.git
cd Team-LEX
```

## 2. Create the Python virtual environment

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

The `venv/` directory is ignored by Git and should remain local.

## 3. Configure backend environment variables

Create a local `.env` file from the example:

macOS/Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Replace the example `SECRET_KEY` value with a local development value. Do not commit `.env`.

## 4. Install Python dependencies

With the virtual environment active:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The base backend dependencies include Django, Django REST Framework, CORS support and environment variable loading. AI/retrieval dependencies should be added when the related technical choices are implemented and validated.

## 5. Set up the local database

The development backend uses SQLite. Create/update the local database by running:

```bash
python manage.py migrate
```

This creates `db.sqlite3` locally. The database file is ignored by Git.

Optional admin account:

```bash
python manage.py createsuperuser
```

## 6. Run the Django backend

```bash
python manage.py runserver
```

Backend URLs:

- API health check: `http://127.0.0.1:8000/api/health/`
- Compatibility test endpoint: `http://127.0.0.1:8000/api/test/`
- Django admin: `http://127.0.0.1:8000/admin/`

A successful health request should return JSON indicating that the Lex AI API is running.

## 7. Install frontend dependencies

Open a second terminal:

```bash
cd frontend
npm install
```

This creates a local `node_modules/` directory, which is ignored by Git.

## 8. Run the React frontend

```bash
npm run dev
```

Vite normally serves the frontend at:

`http://localhost:5173`

The current React chatbot still uses temporary local responses. Connecting the frontend to the Django API and the RAG workflow is separate integration work.

## 9. Production-style frontend build check

Before merging frontend changes, run:

```bash
npm run build
```

The generated `frontend/dist/` directory is ignored by Git.

## 10. Basic backend checks

Run:

```bash
python manage.py check
python manage.py test
```

These commands should be run before backend changes are merged.

## Git workflow

See [`BRANCHING_STRATEGY.md`](BRANCHING_STRATEGY.md) for the Team LEX branch and pull request process.

## Repository structure

```text
Team-LEX/
├── api/                    Django application/API
├── mysite/                 Django project configuration
├── frontend/               React/Vite Lex AI interface
├── docs/                   Project development documentation
├── manage.py               Django management entry point
├── requirements.txt        Python dependencies
├── .env.example            Local environment template
└── README.md               Project overview
```

## Common setup problems

### Django reports that `SECRET_KEY` is missing

Confirm `.env` exists in the repository root and contains a `SECRET_KEY` value.

### Frontend cannot call the backend

Confirm the Django server is running on port 8000 and the frontend origin is included in `CORS_ALLOWED_ORIGINS` in `.env`.

### Database errors after pulling changes

Run:

```bash
python manage.py migrate
```

### Python package import errors

Confirm the virtual environment is active, then reinstall dependencies:

```bash
pip install -r requirements.txt
```

### Frontend dependency errors

From `frontend/`, run:

```bash
npm install
```
