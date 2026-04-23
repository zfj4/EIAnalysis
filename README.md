# EIAnalysis
v0.4.1.3<br>

A single-page epidemiological analysis application built with Django, HTMX, and Tailwind CSS.
Load a JSON or CSV data file and run statistical analyses. Powered by the [epiinfo](https://github.com/Epi-Info/epiinfo) library.
<br><br>
The EIAnalysis application serves as an interface for the <a href="https://github.com/Epi-Info/epiinfo">epiinfo</a> Python package and provides much of the data management and analysis functionality as the <a href="https://github.com/Epi-Info/Epi-Info-Community-Edition">Epi Info 7</a> Analysis Dashboard.
<br><br>
Download and setup instructions are below. A tutorial using included sample data is <a href="https://github.com/zfj4/EIAnalysis/wiki/Tutorial">here</a>.

---

## Prerequisites

Before you begin, install the following on your machine:

| Software | Version | Download |
|---|---|---|
| Python | 3.11 or later | https://www.python.org/downloads/ |

No database server or Docker installation is required. EIAnalysis uses SQLite, which is included with Python.

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

This installs Django, the epiinfo analysis library, and its dependencies (scipy, etc.).

---

## 5 — Run database migrations

```
python manage.py migrate
```

This creates the SQLite database file (`db.sqlite3`) and sets up Django's session and admin tables.

---

## 6 — Start the development server

```
python manage.py runserver9000
```

The server starts on port 9000 because port 8000 is reserved for another application.

Open your browser and go to:

```
http://127.0.0.1:9000/
```

You should see the EIAnalysis home screen with a **Load Data File** button.

Code changes take effect immediately.

---

## 7 — Try it out

See the **[wiki](https://github.com/zfj4/EIAnalysis/wiki)** for step-by-step walkthroughs showing how to load each sample dataset and run each analysis, with expected output values.

---

## Running the test suite

```
python manage.py test core --settings=eianalysis.test_settings
```

Tests use an in-memory SQLite database.

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
│   ├── settings.py              # SQLite database configuration
│   └── test_settings.py        # Overrides DB to in-memory SQLite for tests
├── sample_data/
│   └── Salmonellosis.json       # Sample dataset (309 records)
├── templates/core/
│   └── partials/                # HTMX-swappable HTML fragments
├── dependencies.txt             # pip install -r dependencies.txt
└── manage.py
```
