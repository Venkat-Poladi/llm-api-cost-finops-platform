-- M6 dataset inventory
-- The Python loader executes dataset creation so the same configuration drives local and cloud builds.

CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.{{RAW_DATASET}}`
OPTIONS(location = '{{LOCATION}}');

CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.{{STAGING_DATASET}}`
OPTIONS(location = '{{LOCATION}}');

CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.{{CORE_DATASET}}`
OPTIONS(location = '{{LOCATION}}');

CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.{{MART_DATASET}}`
OPTIONS(location = '{{LOCATION}}');

CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.{{CONTROL_DATASET}}`
OPTIONS(location = '{{LOCATION}}');
