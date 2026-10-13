# Exploratory Data Analysis

- Rows: 31 before, 30 after transformations.
- Columns: 8.
- Exact duplicate rows removed: 1.

## Dashboard

Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.

## Findings

- order_id is a unique identifier with 1 duplicate row; should be removed to avoid redundancy.
- order_date is stored as object; should be converted to datetime for time analysis.
- region, product_category, customer_segment are categorical strings; keep as category.
- units_sold has 1 missing value; impute with median (2.0) to preserve distribution.
- unit_price has 1 missing and 1 outlier (9500); impute missing with median (40.25) and cap outlier using IQR.
- returned is object but numeric boolean; convert to numeric (0/1) and impute missing with mode (0).

## Transformations applied

- **order_date** — Enable date-based analysis and ordering. (conversion: datetime; missing values: keep; outliers: keep; rows removed: 0).
- **returned** — Boolean stored as object; convert to 0/1 and fill missing with most common (0). (conversion: numeric; missing values: mode; outliers: keep; rows removed: 0).
- **unit_price** — Impute missing with median; cap extreme high price (9500) to reduce skew. (conversion: none; missing values: median; outliers: cap_iqr; rows removed: 0).
- **units_sold** — Only 1 missing; median preserves central tendency. (conversion: none; missing values: median; outliers: keep; rows removed: 0).
- Duplicate handling: Exact duplicate rows provide no additional information and inflate row count.

## Chart downloads

- [What is the distribution of unit_price after capping outliers? (SVG)](charts/chart_01_histogram.svg) — Assess effect of outlier handling on price distribution.
- [Are there any remaining outliers in units_sold? (SVG)](charts/chart_02_box.svg) — Validate that units_sold has no extreme values.
- [How many orders are in each region? (SVG)](charts/chart_03_bar.svg) — Understand regional order volume.
- [Is there a relationship between units sold and unit price? (SVG)](charts/chart_04_scatter.svg) — Explore potential correlation between quantity and price.

No model was trained and no train/test split was created.
