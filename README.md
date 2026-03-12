# EIAnalysis

A single-page epidemiological analysis application built with Django, HTMX, and Tailwind CSS.
Load a JSON data file and run statistical analyses — starting with Tables Analysis powered by the [epiinfo](https://github.com/Epi-Info/epiinfo) library.

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

## 8 — Load the Salmonellosis sample dataset

1. On the home screen, click **Choose File**
2. Navigate to the `sample_data` folder inside the project directory
3. Select **Salmonellosis.json** and click **Open**
4. Click **Load File**

The page will display a summary showing **309 rows** and all available column names.

---

## 9 — Run Tables Analysis

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

## 10 — Run Logistic Regression

1. In the left sidebar, click **Logistic Regression**
2. In the **Outcome Variable** dropdown, select **`Ill`**
3. In the **Exposure Variables** list, check **`ChefSalad`** and **`EggSaladSandwich`**
4. Leave **Match Variable** set to **— none —** (unmatched analysis)
5. Leave **Interaction Variables** unchecked (no interaction term)
6. Click **Run Analysis**

Results will appear immediately, including:

- A terms table showing Odds Ratio, 95% CI, Coefficient, S.E., Z-Statistic, and P-Value for each exposure variable and the CONSTANT
- Model fit statistics: convergence status, iterations, final −2 × log-likelihood, and cases included
- Score and Likelihood Ratio test statistics

Expected values from the reference output:

| Term | Odds Ratio | 95% CI Lower | 95% CI Upper | P-Value |
|---|---|---|---|---|
| ChefSalad | 3.1424 | 1.6046 | 6.1539 | 0.0008 |
| EggSaladSandwich | 2.8343 | 1.5300 | 5.2506 | 0.0009 |

| Statistic | Value |
|---|---|
| Iterations | 4 |
| Final −2 × Log-Likelihood | 393.3736 |
| Cases Included | 309 |
| Score (df=2) | 14.7777 (p=0.0006) |
| Likelihood Ratio (df=2) | 15.5999 (p=0.0004) |

To include an interaction term, check **`ChefSalad`** and **`EggSaladSandwich`** under **Interaction Variables** before running. An additional table will appear showing the interaction odds ratios holding each variable fixed.

---

## 11 — Run Log-Binomial Regression

1. In the left sidebar, click **Log-Binomial Regression**
2. In the **Outcome Variable** dropdown, select **`Ill`**
3. In the **Exposure Variables** list, check **`ChefSalad`** and **`EggSaladSandwich`**
4. Leave **Interaction Variables** unchecked (no interaction term)
5. Click **Run Analysis**

Results will appear immediately, including:

- A terms table showing Risk Ratio, 95% CI, Coefficient, S.E., Z-Statistic, and P-Value for each exposure variable and the CONSTANT
- Model fit statistics: convergence status, iterations, final log-likelihood, and cases included

Expected values from the reference output:

| Term | Risk Ratio | 95% CI Lower | 95% CI Upper | P-Value |
|---|---|---|---|---|
| ChefSalad | 1.3992 | 1.1155 | 1.7550 | 0.0037 |
| EggSaladSandwich | 1.3325 | 1.1251 | 1.5780 | 0.0009 |

| Statistic | Value |
|---|---|
| Iterations | 7 |
| Final Log-Likelihood | −197.8080 |
| Cases Included | 309 |

To include an interaction term, check **`ChefSalad`** and **`EggSaladSandwich`** under **Interaction Variables** before running. An additional table will appear showing the interaction risk ratios holding each variable fixed.

---

## 12 — Run Linear Regression

This example uses the `BabyBloodPressure.json` sample dataset included in the `sample_data` folder. Load it first (step 8), then:

1. In the left sidebar, click **Linear Regression**
2. In the **Outcome Variable** dropdown, select **`SystolicBlood`**
3. In the **Exposure Variables** list, check **`AgeInDays`** and **`Birthweight`**
4. Leave **Interaction Variables** unchecked (no interaction term)
5. Click **Run Analysis**

Results will appear immediately, including:

- A terms table showing Coefficient, 95% LCL/UCL, Standard Error, F-test, and P-Value for each predictor and the CONSTANT
- Correlation coefficient (R²)
- Analysis of Variance table: Regression, Residuals, and Total rows with df, Sum of Squares, Mean Square, and F-statistic

Expected values from the reference output:

| Variable | Coefficient | 95% LCL | 95% UCL | P-Value |
|---|---|---|---|---|
| AgeInDays | 5.888 | 4.418 | 7.357 | < 0.0001 |
| Birthweight | 0.126 | 0.051 | 0.200 | 0.0029 |
| CONSTANT | 53.450 | 43.660 | 63.241 | < 0.0001 |

| Statistic | Value |
|---|---|
| R² | 0.88 |
| Regression F (df=2) | 48.081 |
| Residuals df | 13 |

To include an interaction term, check **`AgeInDays`** and **`Birthweight`** under **Interaction Variables** before running. The interaction term `AgeInDays*Birthweight` will appear in the terms table. With the interaction, R² rises to 0.92.

---

## 13 — Run Means Analysis

This example uses the `Oswego.json` sample dataset included in the `sample_data` folder. Load it first (step 8), then:

1. In the left sidebar, click **Means Analysis**
2. In the **Means Of** dropdown, select **`AGE`**
3. In the **Cross-tabulate** dropdown, select **`ILL`**
4. Click **Run Analysis**

Results will appear immediately, including:

- **Descriptive Statistics** table: Obs, Total, Mean, Variance, and Std Dev for each value of the cross-tabulate variable
- **Percentiles** table: Minimum, 25%, Median, 75%, Maximum, and Mode for each group
- **T-Test**: Pooled and Satterthwaite mean differences, 95% confidence limits, t values, and p-values (shown only when there are exactly two groups)
- **ANOVA**: Between/Within/Total SS, df, MS, and F-statistic with p-value
- **Bartlett's Test** for inequality of variances
- **Kruskal-Wallis** nonparametric test

Expected values from the reference output:

| Group (ILL) | Obs | Mean Age | Std Dev |
|---|---|---|---|
| 0 | 29 | 32.9310 | 20.5842 |
| 1 | 46 | 39.2609 | 21.8464 |

| Statistic | Value |
|---|---|
| T-Test pooled mean diff | −6.3298 (p=0.2156) |
| ANOVA F (df=1) | 1.5604 (p=0.2156) |
| Kruskal-Wallis H (df=1) | 1.1612 (p=0.2812) |

If no Cross-tabulate variable is selected, only the Descriptive Statistics tables are displayed for the dataset as a whole.

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
