# EIAnalysis
v0.1.3<br>

A single-page epidemiological analysis application built with Django, HTMX, and Tailwind CSS.
Load a JSON data file and run statistical analyses. Powered by the [epiinfo](https://github.com/Epi-Info/epiinfo) library.

---

## Prerequisites

Before you begin, install the following on your machine:

| Software | Version | Download |
|---|---|---|
| Python | 3.11 or later | https://www.python.org/downloads/ |
| Docker Desktop | latest | https://www.docker.com/products/docker-desktop/ |

Docker is used to run the PostgreSQL database. Python runs the Django development server directly on your machine, so code changes take effect immediately without rebuilding anything.

---

## 1 — Download and extract the project

1. Go to **https://github.com/zfj4/EIAnalysis**
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to a folder of your choice, e.g. `C:\Projects\EIAnalysis` (Windows) or `~/Projects/EIAnalysis` (macOS)

---

## 2 — Open a terminal in the project folder

**Windows (PowerShell or Command Prompt)**
```
cd C:\Projects\EIAnalysis
```

**macOS (Terminal)**
```
cd ~/Projects/EIAnalysis
```

---

## 3 — Create and activate a virtual environment

**Windows**
```
python -m venv .venv
```
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```
```
.venv\Scripts\activate
```

**macOS**
```
python3 -m venv .venv
```
```
source .venv/bin/activate
```

You should see `(.venv)` at the start of your prompt.

---

## 4 — Install dependencies

```
pip install -r dependencies.txt
```

This installs Django, psycopg2-binary (PostgreSQL driver), and the epiinfo analysis library along with its dependencies (scipy, etc.).

---

## 5 — Start the database

Make sure Docker Desktop is running, then from the project folder:

```
docker compose up -d
```

Docker will start a PostgreSQL 17 container on port 5432. Your database data is preserved in a Docker volume between runs.

> **Note:** On first run, Docker must download the PostgreSQL image (~60 MB). Subsequent starts are fast.

To stop the database: `docker compose down`

---

## 6 — Run database migrations

```
python manage.py migrate
```

You should see a series of `OK` lines as Django creates its tables.

---

## 7 — Start the development server

```
python manage.py runserver9000
```

The server starts on port 9000 because port 8000 is reserved for another application.

Open your browser and go to:

```
http://127.0.0.1:9000/
```

You should see the EIAnalysis home screen with a **Load Data File** button.

Code changes take effect immediately — no Docker rebuild needed.

---

## 8 — Try it out

See the **[wiki](https://github.com/zfj4/EIAnalysis/wiki)** for step-by-step walkthroughs showing how to load each sample dataset and run each analysis, with expected output values.

---


## Running the test suite

```
python manage.py test core --settings=eianalysis.test_settings
```

Tests use an in-memory SQLite database — no live PostgreSQL connection required.

---

## Project structure

```
EIAnalysis/
├── core/                        # Main Django app
│   ├── management/commands/
│   │   └── runserver9000.py     # Custom command: serves on port 9000
│   ├── tests.py                 # Full test suite (unit + integration)
│   ├── urls.py
│   └── views.py
├── eianalysis/                  # Django project settings
│   ├── settings.py              # Configure DB credentials here
│   └── test_settings.py        # Overrides DB to SQLite for tests
├── sample_data/
│   └── Salmonellosis.json       # Sample dataset (309 records)
├── templates/core/
│   └── partials/                # HTMX-swappable HTML fragments
├── dependencies.txt             # pip install -r dependencies.txt
└── manage.py
```
