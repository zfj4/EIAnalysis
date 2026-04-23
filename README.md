# EIAnalysis
v0.4.1.2<br>

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


## Deploying to PythonAnywhere (free tier)

PythonAnywhere's free tier hosts the app at `yourusername.pythonanywhere.com` with no spin-down. No credit card required.

### 1 — Create a PythonAnywhere account

Sign up at **https://www.pythonanywhere.com** (free Beginner plan).

---

### 2 — Open a Bash console and clone the repo

In the PythonAnywhere dashboard, go to **Consoles → Bash** and run:

```
git clone https://github.com/zfj4/EIAnalysis.git
cd EIAnalysis
```

---

### 3 — Create a virtual environment and install dependencies

```
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r dependencies.txt
```

---

### 4 — Run migrations and collect static files

```
python manage.py migrate
python manage.py collectstatic --noinput
```

---

### 5 — Create the web app

In the PythonAnywhere dashboard:

1. Go to **Web → Add a new web app**
2. Choose **Manual configuration**
3. Choose the Python version matching your venv (3.13)

---

### 6 — Configure the WSGI file

In the Web tab, click the link to your WSGI configuration file and replace its contents with:

```python
import os
import sys

path = '/home/yourusername/EIAnalysis'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'eianalysis.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Replace `yourusername` with your PythonAnywhere username.

---

### 7 — Set environment variables

In the Web tab, under **Environment variables**, add:

| Key | Value |
|---|---|
| `SECRET_KEY` | A long random string (generate one at https://djecrety.ir) |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `yourusername.pythonanywhere.com` |

---

### 8 — Configure the virtualenv path

In the Web tab, under **Virtualenv**, enter:

```
/home/yourusername/EIAnalysis/.venv
```

---

### 9 — Reload the web app

Click **Reload** in the Web tab. Your app will be live at:

```
https://yourusername.pythonanywhere.com
```

---

### Updating the app

When you push changes to GitHub, SSH into PythonAnywhere and run:

```
cd ~/EIAnalysis
git pull
source .venv/bin/activate
pip install -r dependencies.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then click **Reload** in the Web tab.

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
