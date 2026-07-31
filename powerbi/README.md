# Power BI Project

This directory contains the source-controlled Power BI Project used for the
LLM API Cost FinOps platform.

## Contents

- `llm-api-cost-finops.pbip` opens the complete Power BI project.
- `llm-api-cost-finops.Report/` contains the report pages and visual definitions.
- `llm-api-cost-finops.SemanticModel/` contains the TMDL semantic model,
  relationships, measures, formatting, and model metadata.
- `semantic_model/` contains reviewer-friendly relationship, measure,
  formatting, and visibility documentation.

The report includes four analytical pages:

1. AI Cost Intelligence
2. Token Economics & Reliability
3. Allocation, Chargeback & Reconciliation
4. Optimization & Experiment Controls

The repository excludes local Power BI settings and cached model data.
The report uses controlled synthetic data, and optimization amounts are
modeled opportunities rather than realized savings.
