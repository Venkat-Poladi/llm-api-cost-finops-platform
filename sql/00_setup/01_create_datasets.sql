-- M6 dataset inventory
-- The Python loader executes dataset creation so the same configuration drives local and cloud builds.

CREATE SCHEMA IF NOT EXISTS `finops-learning-lab.llm_finops_raw`
OPTIONS(location = 'US');

CREATE SCHEMA IF NOT EXISTS `finops-learning-lab.llm_finops_staging`
OPTIONS(location = 'US');

CREATE SCHEMA IF NOT EXISTS `finops-learning-lab.llm_finops_core`
OPTIONS(location = 'US');

CREATE SCHEMA IF NOT EXISTS `finops-learning-lab.llm_finops_mart`
OPTIONS(location = 'US');

CREATE SCHEMA IF NOT EXISTS `finops-learning-lab.llm_finops_control`
OPTIONS(location = 'US');
