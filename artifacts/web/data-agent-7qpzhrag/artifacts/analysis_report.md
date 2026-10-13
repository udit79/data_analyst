# Exploratory Data Analysis

- Rows: 31 before, 30 after transformations.
- Columns: 8.
- Exact duplicate rows removed: 1.

## Dashboard

Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.

## Findings

- Dataset has 31 rows and 8 columns with 1 exact duplicate row.
- Missing values: units_sold (1), unit_price (1), customer_segment (1), returned (1).
- unit_price shows high positive skew and 1 IQR outlier.
- returned column is object type but contains boolean values; should be numeric.
- order_date is stored as object; should be datetime.
- Categorical columns (region, product_category, customer_segment) have low cardinality.

## Transformations applied

- **customer_segment** — Categorical segment with one missing; mode imputation retains most common class. (conversion: category; missing values: mode; outliers: keep; rows removed: 0).
- **order_date** — Date stored as string; conversion enables time-based analysis. (conversion: datetime; missing values: keep; outliers: keep; rows removed: 0).
- **order_id** — Identifier column; keep as string. (conversion: string; missing values: keep; outliers: keep; rows removed: 0).
- **product_category** — Low-cardinality categorical product category. (conversion: category; missing values: keep; outliers: keep; rows removed: 0).
- **region** — Low-cardinality categorical region field. (conversion: category; missing values: keep; outliers: keep; rows removed: 0).
- **returned** — Boolean stored as object; convert to 0/1 numeric. Impute missing with mode (most common value). (conversion: numeric; missing values: mode; outliers: keep; rows removed: 0).
- **unit_price** — Numeric price with one missing and a high skew; median imputation and IQR capping reduce outlier impact. (conversion: none; missing values: median; outliers: cap_iqr; rows removed: 0).
- **units_sold** — Numeric count with a single missing; median preserves distribution. (conversion: none; missing values: median; outliers: keep; rows removed: 0).
- Duplicate handling: Exact duplicate rows provide no additional information and can bias analyses.

## Chart downloads

- [What is the distribution of unit_price after handling outliers? (SVG)](charts/chart_01_histogram.svg) — Histogram reveals price spread and effect of capping outliers.
- [Are there remaining extreme unit_price values after capping? (SVG)](charts/chart_02_box.svg) — Box plot visualizes residual outliers and spread.
- [How many orders belong to each product category? (SVG)](charts/chart_03_bar.svg) — Bar chart shows category frequency for sales composition.
- [Is there a relationship between units sold and unit price? (SVG)](charts/chart_04_scatter.svg) — Scatter plot explores correlation between quantity and price.

No model was trained and no train/test split was created.
