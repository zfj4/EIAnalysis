# EIAnalysis

A single-page epidemiological analysis application built with Django, HTMX, and Tailwind CSS.
Load a JSON data file and run statistical analyses — starting with Tables Analysis powered by the [epiinfo](https://github.com/Epi-Info/epiinfo) library.

---

## Prerequisites

Before you begin, install the following on your machine:

| Software | Version | Download |
|---|---|---|
| Python | 3.11 or later | https://www.python.org/downloads/ |
| PostgreSQL | 14 or later | https://www.postgresql.org/download/ |

During the PostgreSQL installation you will be asked to set a password for the default `postgres` superuser — keep note of it.

> **Using Docker?** If you plan to use Docker (step 7), you can skip these prerequisites entirely — Docker provides its own Python and PostgreSQL environments.

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

## 3 — Create and activate a virtual environment (Skip to 8 if running with Docker)

**Windows**
```
python -m venv .venv
.venv\Scripts\activate
```

**macOS**
```
python3 -m venv .venv
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

## 5 — Create the PostgreSQL database and user

Open a new terminal window and connect to PostgreSQL:

**Windows**
```
psql -U postgres
```

**macOS** (if installed via Homebrew, the default superuser matches your system username)
```
psql postgres
```

Run the following SQL commands, then exit:

```sql
CREATE USER devuser WITH PASSWORD 'devpassword';
CREATE DATABASE eianalysis OWNER devuser;
\q
```

> **Note:** The database name, username, and password are already configured in `eianalysis/settings.py`. If you use different values here, update that file to match.

---

## 6 — Run database migrations

Back in your project terminal (with the virtual environment active):

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

---

## 8 — (Optional) Run with Docker instead of steps 3–7

If you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed, you can skip steps 3 through 8 entirely. Docker creates the virtual environment, installs all dependencies (including epiinfo and PostgreSQL), runs migrations, and starts the server — all automatically.

From the project folder, run:

```
docker compose up --build
```

Docker will:
1. Build a Python 3.13 image and install all dependencies
2. Start a PostgreSQL 17 container
3. Run database migrations automatically
4. Start the app on port 9000

Open your browser and go to `http://127.0.0.1:9000/`

To stop, press `Ctrl+C`. Your database data is preserved in a Docker volume between runs.

> **Note:** On first run, Docker must download the base images (~200 MB). Subsequent starts are fast.

---

## 9 — Load the Salmonellosis sample dataset

1. On the home screen, click **Choose File**
2. Navigate to the `sample_data` folder inside the project directory
3. Select **Salmonellosis.json** and click **Open**
4. Click **Load File**

The page will display a summary showing **309 rows** and all available column names.

---

## 10 — Run Tables Analysis

1. In the left sidebar, click **Tables Analysis**
2. In the **Outcome Variable** dropdown, select **`Ill`**
3. In the **Exposure Variables** list, check **`ChefSalad`** and **`EggSaladSandwich`**
4. Click **Run Analysis**

Results will appear immediately, including:

- Contingency tables for each exposure variable
- **Single Table Analysis** showing Odds Ratio (cross product and MLE), Risk Ratio, and Risk Difference with 95% confidence intervals
- Chi-square tests and exact p-values

Expected values from the reference output:

| Exposure | Risk Ratio | OR (cross product) | OR (MLE) |
|---|---|---|---|
| ChefSalad | 1.2186 | 1.6338 | 1.6311 |
| EggSaladSandwich | 1.1830 | 1.5788 | 1.5765 |

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
