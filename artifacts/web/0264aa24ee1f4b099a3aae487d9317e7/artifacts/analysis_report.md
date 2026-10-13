# Exploratory Data Analysis

- Rows: 5 before, 5 after transformations.
- Columns: 5.
- Exact duplicate rows removed: 0.

## Dashboard

Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.

## Findings

- Column 'age' has 20% missing values; numeric column can be imputed with mean (32.5).
- Column 'city' has 20% missing values; categorical column can be imputed with mode (Chicago).
- No duplicate rows detected.
- No outliers detected in numeric columns.

## Transformations applied

- **age** — Impute missing ages with the column mean to retain all rows. (conversion: none; missing values: mean; outliers: keep; rows removed: 0).
- **city** — Impute missing city with most frequent value and treat as categorical. (conversion: category; missing values: mode; outliers: keep; rows removed: 0).
- **name** — Treat names as categorical identifiers. (conversion: category; missing values: keep; outliers: keep; rows removed: 0).
- **salary** — Ensure salary is numeric for analysis. (conversion: numeric; missing values: keep; outliers: keep; rows removed: 0).
- Duplicate handling: No exact duplicate rows present in the dataset.

## Chart downloads

- [What is the distribution of employee salaries? (SVG)](charts/chart_01_histogram.svg) — Histogram shows salary spread and central tendency.
- [Are there any age outliers after imputation? (SVG)](charts/chart_02_box.svg) — Box plot visualizes age distribution and potential outliers.
- [How many employees are in each city? (SVG)](charts/chart_03_bar.svg) — Bar chart displays count per city, useful after imputing missing city.
- [Is there a relationship between age and salary? (SVG)](charts/chart_04_scatter.svg) — Scatter plot can reveal correlation between age and salary.

No model was trained and no train/test split was created.
