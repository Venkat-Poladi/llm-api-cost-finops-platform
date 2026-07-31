# M17 — Power BI Semantic Model

## Part A — Run the cloud semantic layer

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m17.ps1
```

This creates five dimensions and five reporting facts in `llm_finops_mart`.

## Part B — Load tables into Power BI

Use the Google BigQuery connector and import:

### Dimensions

- `dim_ai_date`
- `dim_ai_provider`
- `dim_ai_model`
- `dim_ai_application`
- `dim_ai_experiment`

### Facts

- `fact_ai_financial_monthly`
- `fact_ai_usage_monthly`
- `fact_ai_unit_economics_monthly`
- `fact_ai_optimization_monthly`
- `fact_ai_experiment_current`

### Existing control marts

- `mart_ai_control_status`
- `mart_ai_pipeline_status`

## Part C — Create relationships

Open:

`powerbi/semantic_model/relationships.csv`

Create every relationship exactly as listed:

- one-to-many;
- dimension on the one side;
- fact on the many side;
- single-direction filtering;
- active.

Do not create fact-to-fact relationships.

## Part D — Date settings

1. Mark `dim_ai_date` as the date table using `dim_ai_date[date]`.
2. Sort `month_name` by `month_number`.
3. Sort `month_short_name` by `month_number`.
4. Sort `year_month` by `year_month_sort`.

## Part E — Create the measures table

Create this calculated table:

```DAX
_Measures =
DATATABLE(
    "Measure Holder",
    STRING,
    {
        { "Measures" }
    }
)
```

Hide `_Measures[Measure Holder]`.

Create every measure from:

`powerbi/semantic_model/measures.dax`

Store all measures in `_Measures`.

## Part F — Formatting and folders

Use:

`powerbi/semantic_model/measure_formatting.csv`

Apply the listed:

- display folder;
- format string.

## Part G — Hide technical fields

Use:

`powerbi/semantic_model/hidden_columns.csv`

Hide every listed technical key.

Keep business fields visible.

## Final model rule

The model must look like several clean stars sharing conformed dimensions.

It must not look like a spiderweb.
