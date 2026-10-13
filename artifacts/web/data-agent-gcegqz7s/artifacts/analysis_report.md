# Exploratory Data Analysis

- Rows: 5 before, 5 after transformations.
- Columns: 5.
- Exact duplicate rows removed: 0.

## Dashboard

Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.

## Findings

- Column 'age' has 20% missing values; median is 32.5.
- Column 'city' has 20% missing values; mode is 'Chicago'.
- No duplicate rows detected.
- No numeric outliers detected in any column.

## Transformations applied

- **age** — Impute missing ages with median to preserve distribution. (conversion: none; missing values: median; outliers: keep; rows removed: 0).
- **city** — Impute missing city with most frequent value to avoid bias. (conversion: none; missing values: mode; outliers: keep; rows removed: 0).
- Duplicate handling: No duplicate rows based on all columns.

## Chart downloads

- [What is the distribution of ages after imputation? (SVG)](charts/chart_01_histogram.svg) — Shows age spread and confirms imputation effect.
- [Are there any salary outliers? (SVG)](charts/chart_02_box.svg) — Box plot visualizes salary range and potential outliers.
- [How many records per city after imputation? (SVG)](charts/chart_03_bar.svg) — Bar chart reveals city frequency distribution.
- [Is there a relationship between age and salary? (SVG)](charts/chart_04_scatter.svg) — Scatter plot can indicate correlation between age and salary.

No model was trained and no train/test split was created.
