# EtymoPath

EtymoPath is a Django vocabulary learning application. It teaches words through historical roots, morphology, word-family exploration, lessons, server-scored assessments, and saved revision intervals.

The starter vocabulary is intentionally small. Every seed word links to a dictionary entry and an etymology source. Pronunciation and syllable fields are omitted when the seed data has not verified them.

## Requirements

- Python 3.12 or later (the current environment uses Python 3.15)
- PowerShell on Windows, or another shell that can run Python
- MySQL is optional; local development uses SQLite

## Set up on Windows PowerShell

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, either change the policy for the current user according to your organization's guidance or invoke `.\.venv\Scripts\python.exe` directly for each command.

## Local SQLite setup

SQLite is the default. No `.env` parser or database server is required. Django reads configuration from process environment variables. To set a local secret and run the development app:

```powershell
$env:DJANGO_DEBUG = "True"
$env:DJANGO_SECRET_KEY = "local-development-only-change-this"
$env:DB_ENGINE = "sqlite"
python manage.py migrate
python manage.py seed_etymopath
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Main pages:

- `/explore/` — root explorer and vocabulary search
- `/journey/` — Beginner, Intermediate, and Advanced lessons
- `/register/` and `/accounts/login/` — accounts
- `/dashboard/`, `/revision/`, and `/progress/` — signed-in learning records
- `/admin/` — Django Admin

Password reset uses Django's built-in views. With the default console email backend, reset messages and links are printed in the server terminal.

## Content and administration

`core/data/roots.json` and `core/data/learning_path.json` hold the curated, structured seed data. Load or refresh it with:

```powershell
python manage.py seed_etymopath
```

The command uses stable slugs and update-or-create operations, so it is safe to repeat. It refreshes the seeded records from those JSON files. Add and maintain content in Django Admin after creating a superuser. The seeded content covers the Latin `scribere` (“write”) and `portare` (“carry”) families. Source URLs are attached to roots and vocabulary entries; unverified pronunciation/syllable values remain blank.

## MySQL configuration

Install the optional driver and create a MySQL database/user with appropriate permissions:

```powershell
pip install -r requirements-mysql.txt
$env:DB_ENGINE = "mysql"
$env:DB_NAME = "etymopath"
$env:DB_USER = "etymopath_user"
$env:DB_PASSWORD = "your-local-password"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
python manage.py migrate
python manage.py seed_etymopath
```

No code changes are required to select MySQL. The database name, credentials, host, and port come from the environment. SQLite remains the fallback when `DB_ENGINE` is unset or set to `sqlite`.

## Tests and checks

```powershell
python manage.py check
python manage.py test
```

The tests cover public pages, registration/login, authorization, case-insensitive partial search, root relationships, idempotent lesson completion, server-side assessment scores, answer persistence, per-user history, and revision scheduling.

## Troubleshooting

- **Missing table errors:** run `python manage.py migrate`.
- **Explorer has no roots or Journey has no lessons:** run `python manage.py seed_etymopath`.
- **Password reset email is not arriving:** local development prints it in the `runserver` terminal. For delivery, configure Django's SMTP email environment settings.
- **MySQL driver error:** select SQLite for local use or install `requirements-mysql.txt` in the active virtual environment.
- **MySQL access denied / unknown database:** create the database and grant the configured database user access before migrating.
- **Static changes do not appear in production:** run `python manage.py collectstatic` and configure the web server to serve `STATIC_ROOT`.

## Production notes

Set `DJANGO_DEBUG=False`, provide a strong `DJANGO_SECRET_KEY`, and set `DJANGO_ALLOWED_HOSTS` to the deployment host names. If the application is behind a proxy with cross-origin forms, set `DJANGO_CSRF_TRUSTED_ORIGINS` to the trusted HTTPS origins. Configure HTTPS and secure cookies at the deployment layer; the settings enable secure session/CSRF cookies when debug is off and permit opting into HTTPS redirects with `SECURE_SSL_REDIRECT=True`. Use a production email backend for password reset. Do not commit `.env`, SQLite databases, uploaded files, or credentials. Run migrations and `collectstatic` as part of deployment.

## Revision rule

This version uses a simple persisted interval rule rather than a sophisticated spaced-repetition algorithm. A “Needs practice” response schedules the word for the next day. A “Remembered” response doubles its current interval, starting at two days and capped at 30. Assessment mistakes are immediately due for revision.
