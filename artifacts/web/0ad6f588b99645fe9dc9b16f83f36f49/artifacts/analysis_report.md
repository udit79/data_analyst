# Exploratory Data Analysis

- Rows: 5 before, 5 after transformations.
- Columns: 5.
- Exact duplicate rows removed: 0.

## Dashboard

Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.

## Findings

- Column 'age' has 20% missing values; numeric type.
- Column 'city' has 20% missing values; categorical type.
- No duplicate rows detected.
- All columns have reasonable ranges; no outliers detected.

## Transformations applied

- **age** — Fill missing ages with median to preserve distribution without bias. (conversion: none; missing values: median; outliers: keep; rows removed: 0).
- **city** — Impute missing city with most frequent value and treat as categorical. (conversion: category; missing values: mode; outliers: keep; rows removed: 0).
- Duplicate handling: No duplicate rows present; removal not needed.

## Chart downloads

- [What is the distribution of employee ages? (SVG)](charts/chart_01_histogram.svg) — Shows age spread and confirms imputation effect.
- [Are there any salary outliers? (SVG)](charts/chart_02_box.svg) — Box plot visualizes salary range and potential outliers.
- [How many employees are in each city? (SVG)](charts/chart_03_bar.svg) — Bar chart reveals city frequency after imputation.
- [Is there a relationship between age and salary? (SVG)](charts/chart_04_scatter.svg) — Scatter plot assesses correlation between age and salary.

No model was trained and no train/test split was created.
