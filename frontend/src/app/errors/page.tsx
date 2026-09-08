'use client'
import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertTriangle, Search, ChevronDown, ChevronUp,
  CheckCircle2, XCircle, Clock, Zap, Database,
  RefreshCw, Shield, Copy, ExternalLink, Filter,
} from 'lucide-react'

// ── Design tokens ───────────────────────────────────────────────────────────────
const T = {
  bg:     '#080F1C',
  card:   '#0D1F35',
  border: '#1A3A5C',
  accent: '#0EA5E9',
  text:   '#E2E8F0',
  muted:  '#64748B',
  sub:    '#94A3B8',
}

// ── Error catalog data ─────────────────────────────────────────────────────────
type Severity = 'critical' | 'high' | 'medium' | 'low'
type Platform = 'postgresql' | 'snowflake' | 'bigquery' | 'mysql' | 'mongodb' | 'redshift' | 'kafka' | 'flink' | 'spark' | 'duckdb' | 'all'

interface ErrorSignature {
  pattern: string
  example: string
}

interface AnomalyEntry {
  type: string
  label: string
  severity: Severity
  category: 'data_quality' | 'infrastructure' | 'streaming' | 'schema' | 'performance' | 'access'
  platforms: Platform[]
  description: string
  impact: string
  rootCauses: string[]
  actions: string[]
  autoHealable: boolean
  signatures: ErrorSignature[]
  mttrMinutes: { before: number; after: number }
}

const CATALOG: AnomalyEntry[] = [
  {
    type: 'ZERO_LOAD',
    label: 'Zero Load',
    severity: 'critical',
    category: 'infrastructure',
    platforms: ['postgresql', 'snowflake', 'bigquery', 'mysql', 'mongodb', 'redshift', 'duckdb'],
    description: 'Pipeline completed without loading any records. The run succeeded (no exception) but wrote 0 rows to the destination.',
    impact: 'Destination table is stale. Downstream models, dashboards, and ML features are reading yesterday\'s data silently.',
    rootCauses: [
      'Source database is unreachable (firewall, DNS, credentials expired)',
      'Source table was truncated or renamed upstream',
      'Query filter too restrictive — no rows match the WHERE clause',
      'Network timeout during data fetch — partial read discarded',
      'Schema mismatch caused silent write failure in the destination connector',
    ],
    actions: [
      'Check source DB connectivity: ping host, verify port, test credentials',
      'Run SELECT COUNT(*) on the source table directly — confirm rows exist',
      'Review pipeline logs for connection timeout or auth errors',
      'Inspect ETL WHERE clause — ensure date filter covers expected window',
      'If recurring: set up a pre-flight row count check before the load step',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'could not connect to server', example: 'could not connect to server: Connection refused (0.0.0.0:5432)' },
      { pattern: 'SSL connection has been closed', example: 'SSL connection has been closed unexpectedly' },
      { pattern: 'streaming query stopped', example: '[Spark] streaming query stopped: exception in micro-batch' },
      { pattern: 'driver crashed', example: '[Spark] executor lost after driver crashed: OOM' },
      { pattern: 'not found: dataset', example: 'Not found: Dataset my-project:raw_data' },
    ],
    mttrMinutes: { before: 90, after: 8 },
  },
  {
    type: 'ROW_COUNT_DROP',
    label: 'Row Count Drop',
    severity: 'high',
    category: 'data_quality',
    platforms: ['postgresql', 'snowflake', 'bigquery', 'mysql', 'redshift', 'all'],
    description: 'The number of rows loaded in this run dropped more than 20% compared to the 7-day rolling average for the same pipeline.',
    impact: 'Reports and dashboards will show incomplete data. Aggregations will be understated. SLA commitments may be missed.',
    rootCauses: [
      'Source table truncated mid-pipeline by a concurrent DDL operation',
      'Upstream API rate limit hit — partial page of results returned',
      'Date partition filter is off by one — previous day\'s data being reloaded',
      'Source CDC stream has a gap (missed events during Kafka rebalance)',
      'ETL job killed mid-run due to memory limit — partial load committed',
    ],
    actions: [
      'Compare row count in source vs destination for today\'s date partition',
      'Check pipeline logs for out-of-memory or timeout signals',
      'Review Kafka consumer lag — look for rebalance events in the same window',
      'Verify that the source partition/date filter is using the correct boundary',
      'Re-run the affected pipeline for the impacted date range',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'incremental load', example: 'Incremental load produced 0 new rows for partition 2024-01-15' },
      { pattern: 'consumer group rebalance', example: 'Kafka consumer group rebalance triggered during batch read' },
      { pattern: 'executor lost', example: '[Spark] executor lost: exit code 137 (OOM)' },
    ],
    mttrMinutes: { before: 60, after: 7 },
  },
  {
    type: 'NULL_SPIKE',
    label: 'Null Spike',
    severity: 'high',
    category: 'data_quality',
    platforms: ['all'],
    description: 'The null rate for one or more columns jumped more than 10 percentage points above the 7-day baseline in a single run.',
    impact: 'Downstream aggregations will produce incorrect results. ML feature pipelines will receive NaN inputs. NOT NULL constraints in the warehouse may start failing.',
    rootCauses: [
      'Source schema changed — a previously non-null column is now optional',
      'ETL transformation has a bug — JOIN producing nulls on non-matching rows',
      'Source API started returning empty/null fields for certain record types',
      'Lookup table used in transformation is missing rows (referential null)',
      'dbt incremental model not handling late-arriving records correctly',
    ],
    actions: [
      'Identify which columns spiked using: SELECT col, COUNT(*) FILTER (WHERE col IS NULL) FROM table',
      'Check if a schema change landed on the source side in the same time window',
      'Review JOIN conditions in the ETL — look for LEFT JOINs producing unintended nulls',
      'If a lookup table is involved, check its row count and last refresh time',
      'Add a NOT NULL assertion to your dbt schema.yml for critical columns',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'null rate', example: 'NULL rate for column customer_id jumped from 0.2% to 38.4%' },
    ],
    mttrMinutes: { before: 45, after: 6 },
  },
  {
    type: 'PIPELINE_DELAY',
    label: 'Pipeline Delay',
    severity: 'medium',
    category: 'performance',
    platforms: ['all'],
    description: 'Pipeline execution time exceeded 2× the 7-day rolling average for this pipeline, but did not breach the SLA target yet.',
    impact: 'Downstream pipelines that depend on this one will start late. If the delay continues, it will escalate to an SLA_BREACH.',
    rootCauses: [
      'Database is under heavy load — long queue times on shared warehouse',
      'Full table scan triggered because query planner chose the wrong index',
      'Large data volume spike — more rows than usual for this time period',
      'Snowflake warehouse was suspended and had cold-start resume time',
      'Spark executor back pressure due to skewed partitions',
      'RocksDB state backend compaction running during the Flink checkpoint',
    ],
    actions: [
      'Check source DB query plan: run EXPLAIN ANALYZE on the main ETL query',
      'Review Snowflake query history for queue wait times',
      'Look for partition skew in Spark UI — repartition if one task takes 10× longer',
      'Add CLUSTER BY or SORT KEY to the destination table for the most common filter columns',
      'If recurring at the same hour: schedule the pipeline during off-peak hours',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'back pressure', example: '[Flink] operator back pressure detected: 89% input buffer full' },
      { pattern: 'micro-batch processing time exceeded', example: '[Spark] micro-batch processing time exceeded trigger interval' },
      { pattern: 'query exceeded memory limit', example: 'Snowflake: query exceeded per-query memory limit' },
      { pattern: 'max_allowed_packet', example: 'MySQL: Got a packet bigger than max_allowed_packet bytes' },
      { pattern: 'rocksdb compaction error', example: '[Flink] RocksDB compaction error during checkpoint' },
    ],
    mttrMinutes: { before: 30, after: 5 },
  },
  {
    type: 'CONSECUTIVE_FAILURES',
    label: 'Consecutive Failures',
    severity: 'critical',
    category: 'infrastructure',
    platforms: ['all'],
    description: 'The same pipeline has failed 2 or more times in a row without a successful run in between.',
    impact: 'The destination table has not been updated. Every hour this runs without fixing the root cause, data staleness compounds.',
    rootCauses: [
      'Credentials rotated without updating the secret in the pipeline config',
      'Deadlock in the source DB — concurrent writes blocking reads',
      'Network instability between the ETL worker and the database host',
      'Schema mismatch — column type changed in source, pipeline fails on INSERT',
      'Airflow worker ran out of disk space — temp files causing silent failure',
    ],
    actions: [
      'Check the last error message in the incident panel — note the exact exception',
      'Rotate and re-enter credentials if error mentions "authentication failed"',
      'If deadlock: check pg_stat_activity for long-running blocking transactions',
      'Compare source table schema with destination — look for type mismatches',
      'Check ETL worker disk usage: df -h on the Airflow worker node',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'deadlock detected', example: 'ERROR: deadlock detected in transaction 47823' },
      { pattern: 'lock wait timeout exceeded', example: 'MySQL: Lock wait timeout exceeded; try restarting transaction' },
      { pattern: 'write conflict', example: 'MongoDB: write conflict in transaction, retry' },
      { pattern: 'operator chaining failed', example: '[Flink] operator chaining failed: task exception in slot 0' },
      { pattern: 'job vertex failed', example: '[Flink] job vertex failed: exception in source operator' },
      { pattern: 'stream query terminated with exception', example: '[Spark] StreamingQuery terminated with exception: AnalysisException' },
    ],
    mttrMinutes: { before: 75, after: 9 },
  },
  {
    type: 'SCHEMA_DRIFT',
    label: 'Schema Drift',
    severity: 'high',
    category: 'schema',
    platforms: ['snowflake', 'bigquery', 'postgresql', 'mysql', 'duckdb'],
    description: 'A column was added, removed, or changed type in the source table without a corresponding migration in the destination.',
    impact: 'Inserts will fail or silently truncate data. Downstream dbt models referencing the changed column will break. BI reports may show errors.',
    rootCauses: [
      'Source team deployed a new API version with a changed response shape',
      'DBA added or dropped a column without notifying the data team',
      'Snowflake stream or BigQuery table has SCHEMA_EVOLUTION enabled and auto-added a column',
      'ORM migration ran in staging and was promoted to prod — changing column types',
      'CDC connector (Debezium) propagated a source DDL change without version bump',
    ],
    actions: [
      'Run a column diff between source and destination: compare INFORMATION_SCHEMA on both sides',
      'Update the destination table schema to match: ALTER TABLE + backfill if needed',
      'Add a dbt source schema test to catch this automatically next time',
      'If using Snowflake streams: check if SCHEMA_EVOLUTION added unexpected columns',
      'Coordinate with source team: require a PR review whenever source schema changes',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'schema evolution', example: 'Snowflake: schema evolution detected — column "order_total" type changed FLOAT → DOUBLE' },
      { pattern: 'schema mismatch', example: 'BigQuery: schema mismatch in streaming insert destination table' },
      { pattern: 'catalog error', example: 'DuckDB: Catalog Error: column "customer_uuid" does not exist' },
    ],
    mttrMinutes: { before: 60, after: 8 },
  },
  {
    type: 'CDC_LAG',
    label: 'CDC Lag',
    severity: 'high',
    category: 'streaming',
    platforms: ['mysql', 'mongodb', 'snowflake', 'kafka', 'flink'],
    description: 'Change Data Capture (CDC) lag exceeds 5 minutes. The destination is falling behind the source in near-real-time replication.',
    impact: 'Real-time dashboards will show stale data. Event-driven workflows triggered by DB changes will fire late. SLA on data freshness will be missed.',
    rootCauses: [
      'MySQL binlog is in STATEMENT mode instead of ROW mode — Debezium cannot read it',
      'MongoDB oplog is too small and wrapped around — CDC consumer lost its position',
      'Snowflake stream became stale (14 days without consumption)',
      'Kafka consumer group is lagging — too many partitions, not enough consumers',
      'Flink watermark stalled because a source partition stopped producing events',
    ],
    actions: [
      'For MySQL: check binlog_format = "ROW" via SHOW VARIABLES LIKE "binlog_format"',
      'For MongoDB: increase oplog size or ensure consumers run at least once per day',
      'For Snowflake: re-create the stream on the source table to reset staleness',
      'For Kafka: add more consumer instances or increase partition parallelism',
      'For Flink: check for idle sources — enable allowedLateness or set a watermark idle timeout',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'stream has become stale', example: 'Snowflake: stream MY_STREAM has become stale after 14 days' },
      { pattern: 'oplog is too small', example: 'MongoDB: oplog is too small to guarantee consistency for change stream' },
      { pattern: 'changestream cursor timeout', example: 'MongoDB: changestream cursor timeout after 30s of inactivity' },
      { pattern: 'binlog format is not row', example: 'Debezium: MySQL binlog format is not ROW — cannot use CDC connector' },
      { pattern: 'watermark stalled', example: '[Flink] watermark stalled at 1700000000000 for partition kafka-3' },
      { pattern: 'streaming buffer not available', example: 'BigQuery: streaming buffer not available for table raw.orders' },
    ],
    mttrMinutes: { before: 45, after: 7 },
  },
  {
    type: 'SLA_BREACH',
    label: 'SLA Breach',
    severity: 'critical',
    category: 'performance',
    platforms: ['all'],
    description: 'Pipeline duration exceeded 3× the configured SLA target for this pipeline. Example: kafka_consumer SLA is 5 min but took 25 min.',
    impact: 'Contractual data delivery SLAs are being violated. Executive dashboards are out of date. Downstream pipelines are blocked waiting for this one.',
    rootCauses: [
      'Unexpected data volume spike — 10× normal record count this run',
      'Warehouse cluster was resizing during the run',
      'Source DB replication lag caused slow reads',
      'Long GC pauses on the ETL worker JVM (Spark driver)',
      'Airflow task queue was full — task waited 30 min before a worker picked it up',
    ],
    actions: [
      'Check the actual pipeline duration in the incident detail panel',
      'Review source record counts for this run vs 7-day average — flag if > 2× normal',
      'Check Airflow task queue depth: look for "queued" tasks older than 5 minutes',
      'For Spark: check the driver log for GC warnings or executor lost events',
      'Consider auto-scaling: if data volume is growing, increase warehouse size for peak hours',
    ],
    autoHealable: false,
    signatures: [
      { pattern: 'sla_target exceeded', example: 'kafka_consumer: SLA breach — ran for 1847s (target: 300s, breach threshold: 900s)' },
    ],
    mttrMinutes: { before: 90, after: 12 },
  },
  {
    type: 'DATA_TYPE_MISMATCH',
    label: 'Data Type Mismatch',
    severity: 'high',
    category: 'schema',
    platforms: ['redshift', 'snowflake', 'bigquery', 'postgresql'],
    description: 'A value in the source data cannot be cast to the destination column\'s declared type. The row is rejected at load time.',
    impact: 'Rejected rows are silently dropped unless STL_LOAD_ERRORS (Redshift) or streaming insert errors are monitored. Counts will be understated.',
    rootCauses: [
      'Source sends a string like "N/A" for a column declared as NUMERIC in Redshift',
      'Timestamp format changed from ISO 8601 to Unix epoch between source versions',
      'Boolean represented as "yes"/"no" string instead of true/false',
      'Currency values include "$" symbol — fails FLOAT cast',
      'Decimal precision changed in source — truncation error on INSERT',
    ],
    actions: [
      'Query Redshift STL_LOAD_ERRORS for rejected rows: SELECT * FROM stl_load_errors ORDER BY starttime DESC LIMIT 20',
      'Cast problematic columns explicitly in the ETL: CAST(NULLIF(col, \'N/A\') AS NUMERIC)',
      'Add a type-check step before loading: assert no non-numeric values in numeric columns',
      'Review source schema changelog for any precision or type changes',
      'Use VARIANT/JSON column as staging, then validate and cast before promoting to typed columns',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'stl_load_errors', example: 'Redshift stl_load_errors: invalid input for column "revenue" (DECIMAL)' },
      { pattern: 'transaction marker', example: 'Kafka: transaction marker offset does not match expected schema type' },
    ],
    mttrMinutes: { before: 45, after: 6 },
  },
  {
    type: 'INCREMENTAL_SYNC_FAILURE',
    label: 'Incremental Sync Failure',
    severity: 'high',
    category: 'data_quality',
    platforms: ['all'],
    description: 'The incremental pipeline loaded 0 records today, but loaded records yesterday at the same time. New rows exist in the source but were not picked up.',
    impact: 'The watermark (last_sync_at) is stuck. All new and updated records since the last successful run are missing from the destination.',
    rootCauses: [
      'Watermark column (updated_at) is not indexed — query times out before returning results',
      'Source records use a created_at timestamp instead of updated_at — updates are missed',
      'ETL job crashed after updating the watermark but before writing records',
      'Kafka consumer offset reset manually — messages already consumed are skipped',
      'Spark state store key not found — stateful aggregation lost its checkpoint',
    ],
    actions: [
      'Check the current watermark value in etl_watermarks table for this pipeline',
      'Run the source query manually with the watermark applied — confirm it returns rows',
      'Verify the watermark column (updated_at) is indexed on the source table',
      'If watermark is ahead of data: reset it to the last known good timestamp',
      'For Kafka: check if __consumer_offsets shows the group at the correct position',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'state store key not found', example: '[Spark] state store key not found for aggregation window' },
      { pattern: 'offset does not exist', example: '[Spark] offset does not exist in checkpoint: partition 5 offset 10023' },
      { pattern: 'consumer group rebalance', example: 'Kafka: consumer group rebalance triggered — offsets reset to earliest' },
    ],
    mttrMinutes: { before: 50, after: 7 },
  },
  {
    type: 'RATE_LIMIT_HIT',
    label: 'Rate Limit Hit',
    severity: 'medium',
    category: 'access',
    platforms: ['snowflake', 'bigquery', 'mysql', 'redshift'],
    description: 'The pipeline hit a resource quota or rate limit — too many connections, too many API calls, or not enough warehouse credits.',
    impact: 'Pipeline is throttled or rejected entirely. Depending on retry strategy, this may cause a delay or a full pipeline failure.',
    rootCauses: [
      'Multiple pipelines scheduled at the same time are competing for the same warehouse',
      'BigQuery free-tier quota exceeded for the day',
      'Snowflake warehouse suspended after inactivity and took too long to resume under load',
      'MySQL max_connections limit reached — new connections are refused',
      'ETL job is not using connection pooling — opens one connection per row batch',
    ],
    actions: [
      'Stagger pipeline schedules to avoid concurrent runs on the same warehouse',
      'For BigQuery: check current usage vs quota in GCP Console → IAM & Admin → Quotas',
      'For Snowflake: use AUTO_SUSPEND = 60 and set an appropriate warehouse size',
      'For MySQL: increase max_connections or use PgBouncer/ProxySQL for connection pooling',
      'Add exponential backoff to all DB connection retry logic in the ETL code',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'too many connections', example: 'PostgreSQL: FATAL: too many connections remaining for non-superuser roles' },
      { pattern: 'warehouse suspended', example: 'Snowflake: warehouse COMPUTE_WH suspended due to inactivity (AUTO_SUSPEND)' },
      { pattern: 'account does not have enough credits', example: 'Snowflake: account does not have enough credits to execute this query' },
      { pattern: 'quota exceeded', example: 'BigQuery: Quota exceeded for project: bigquery-slot-quota' },
      { pattern: 'table is full', example: 'MySQL: The table "orders_staging" is full — disk quota reached' },
    ],
    mttrMinutes: { before: 30, after: 4 },
  },
  {
    type: 'CASCADING_FAILURE',
    label: 'Cascading Failure',
    severity: 'critical',
    category: 'infrastructure',
    platforms: ['all'],
    description: '3 or more pipelines are failing simultaneously within a 30-minute window. This indicates a shared infrastructure problem rather than pipeline-specific bugs.',
    impact: 'Multiple destination tables are stale at the same time. The failure may be masking a database outage, network partition, or credential rotation.',
    rootCauses: [
      'Database host is down or unreachable (all pipelines targeting the same host fail)',
      'Secrets rotation was applied globally — all pipelines using the old secret now fail',
      'Kubernetes namespace eviction killed all ETL pods simultaneously',
      'Shared Airflow database is full or unreachable — no tasks can be scheduled',
      'VPN or network peering route was dropped — ETL workers can\'t reach source DBs',
    ],
    actions: [
      'Check infrastructure status first: can you connect to the source DB from a terminal?',
      'Look at ALL failing pipelines — if they all target the same host, the host is the problem',
      'Check Airflow scheduler logs for "database unreachable" or "pod evicted"',
      'If secrets were recently rotated: verify the new secret is propagated to all pipeline configs',
      'Escalate to infrastructure team if > 3 pipelines are failing with the same error',
    ],
    autoHealable: false,
    signatures: [
      { pattern: 'multiple pipeline failures', example: '5 pipelines failed between 14:00–14:30 UTC: ingest_nyc_taxi, ingest_ecommerce, dbt_run, kafka_consumer, flink_job' },
    ],
    mttrMinutes: { before: 120, after: 15 },
  },
  {
    type: 'DUPLICATE_SPIKE',
    label: 'Duplicate Spike',
    severity: 'medium',
    category: 'data_quality',
    platforms: ['postgresql', 'snowflake', 'bigquery', 'kafka'],
    description: 'Duplicate row rate exceeded 5% compared to the 7-day baseline. Previously distinct primary keys are appearing multiple times in the destination.',
    impact: 'Aggregations (SUM, COUNT) will double-count. Unique user counts will be inflated. dbt uniqueness tests will fail.',
    rootCauses: [
      'ETL is running full-table reload but not deduplicating before INSERT',
      'Kafka at-least-once delivery caused messages to be reprocessed after a broker restart',
      'Upsert logic has a bug — UPDATE was replaced by INSERT without checking existence',
      'Source system re-generated IDs after a rollback — old IDs reappeared',
      'Idempotency key not being used in the destination INSERT (no ON CONFLICT clause)',
    ],
    actions: [
      'Count duplicates: SELECT id, COUNT(*) FROM table GROUP BY id HAVING COUNT(*) > 1',
      'Add ON CONFLICT (id) DO UPDATE SET … to all INSERT statements in the ETL',
      'For Kafka: ensure idempotent producer is enabled and consumer reads in exactly-once mode',
      'Run a one-time dedup: DELETE FROM table WHERE ctid NOT IN (SELECT MIN(ctid) FROM table GROUP BY id)',
      'Add a dbt unique test on the primary key so duplicates surface in CI before reaching prod',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'duplicate key value violates', example: 'PostgreSQL: duplicate key value violates unique constraint "orders_pkey"' },
    ],
    mttrMinutes: { before: 40, after: 5 },
  },
  {
    type: 'CHECKPOINT_FAILURE',
    label: 'Checkpoint Failure',
    severity: 'critical',
    category: 'streaming',
    platforms: ['flink', 'spark', 'kafka'],
    description: 'A streaming job could not complete its checkpoint or save its state. Without a valid checkpoint, the job cannot recover from failure without data loss or reprocessing.',
    impact: 'If the job crashes, it will need to replay from the last good checkpoint — potentially reprocessing hours of events and producing duplicates.',
    rootCauses: [
      'State backend (RocksDB or HDFS) is out of disk space',
      'Checkpoint timeout exceeded — job is under back pressure and can\'t drain in time',
      'Kafka offset for a partition is out of range — checkpoint references a deleted segment',
      'Flink savepoint storage path is unavailable (S3 bucket deleted, NFS mount dropped)',
      'Spark streaming offset does not match what is stored in the checkpoint directory',
    ],
    actions: [
      'Increase checkpoint timeout in Flink: execution.checkpointing.timeout = 10min',
      'Free disk space on the RocksDB state backend nodes',
      'For Kafka: check that the topic retention period is longer than the checkpoint interval',
      'For Spark: delete corrupted checkpoint directory and restart from the latest clean one',
      'Enable incremental checkpointing in Flink to reduce checkpoint size and time',
    ],
    autoHealable: true,
    signatures: [
      { pattern: 'checkpoint failed', example: '[Flink] checkpoint failed: exceeded timeout of 120000ms' },
      { pattern: 'checkpoint timeout exceeded', example: '[Flink] checkpoint timeout exceeded (120s) — back pressure detected on source' },
      { pattern: 'savepoint could not be created', example: '[Flink] savepoint could not be created: S3 path not accessible' },
      { pattern: 'offset out of range', example: 'Kafka: offset out of range for partition 3 — earliest available: 50000' },
      { pattern: 'offset does not exist', example: '[Spark] offset does not exist in checkpoint: partition kafka-5 at offset 10024' },
    ],
    mttrMinutes: { before: 60, after: 9 },
  },
  {
    type: 'PARTITION_SKEW',
    label: 'Partition Skew',
    severity: 'medium',
    category: 'performance',
    platforms: ['spark', 'bigquery', 'redshift', 'snowflake'],
    description: 'One Spark partition or warehouse slot is processing 5× more data than the average. This causes a stragglers effect where all tasks wait for one slow partition to finish.',
    impact: 'Pipeline runs significantly longer than expected. In Spark, one executor stalls the entire stage. In Redshift, one compute node becomes the bottleneck.',
    rootCauses: [
      'JOIN key has a highly skewed value distribution (e.g., one customer_id = 40% of all rows)',
      'Spark default 200 shuffle partitions are too few for the data size',
      'Redshift DISTKEY chosen incorrectly — all rows hashing to the same node',
      'BigQuery partitioning is on a low-cardinality column (e.g., boolean flag)',
      'Flink KeyedStream has a "hot key" — one key gets all the traffic',
    ],
    actions: [
      'Use Spark AQE (Adaptive Query Execution) to auto-coalesce small partitions: spark.sql.adaptive.enabled=true',
      'Salting: add a random suffix to the skewed join key before the shuffle, remove it after',
      'For Redshift: change DISTKEY to a high-cardinality column or use DISTSTYLE EVEN',
      'For Flink: implement a two-phase aggregation for hot keys (pre-aggregate then merge)',
      'Profile the partition size distribution: check Spark UI → Stage → Task metrics for max vs median task duration',
    ],
    autoHealable: false,
    signatures: [
      { pattern: 'partition skew', example: 'Partition skew detected: max_rows=892400, avg_rows=178300, ratio=5.0x for pipeline ingest_nyc_taxi' },
      { pattern: 'shuffle fetch failed', example: '[Spark] shuffle fetch failed: BlockManagerId executor-12 (host:port)' },
    ],
    mttrMinutes: { before: 45, after: 10 },
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────────
const SEVERITY_META: Record<Severity, { color: string; bg: string; label: string }> = {
  critical: { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',  label: 'Critical' },
  high:     { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', label: 'High' },
  medium:   { color: '#0EA5E9', bg: 'rgba(14,165,233,0.12)', label: 'Medium' },
  low:      { color: '#10B981', bg: 'rgba(16,185,129,0.12)', label: 'Low' },
}

const CATEGORY_META: Record<string, { color: string; label: string }> = {
  data_quality:   { color: '#7C3AED', label: 'Data Quality' },
  infrastructure: { color: '#EF4444', label: 'Infrastructure' },
  streaming:      { color: '#F59E0B', label: 'Streaming' },
  schema:         { color: '#0EA5E9', label: 'Schema' },
  performance:    { color: '#10B981', label: 'Performance' },
  access:         { color: '#EC4899', label: 'Access' },
}

const ALL_PLATFORMS: Platform[] = ['postgresql','snowflake','bigquery','mysql','mongodb','redshift','kafka','flink','spark','duckdb']

function SeverityBadge({ severity }: { severity: Severity }) {
  const m = SEVERITY_META[severity]
  return (
    <span style={{
      background: m.bg, color: m.color,
      border: `1px solid ${m.color}40`,
      borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700,
      letterSpacing: '0.05em', textTransform: 'uppercase',
    }}>
      {m.label}
    </span>
  )
}

function PlatformTag({ p }: { p: string }) {
  const colors: Record<string, string> = {
    postgresql: '#3B82F6', snowflake: '#38BDF8', bigquery: '#34D399',
    mysql:      '#F59E0B', mongodb:   '#22C55E', redshift: '#EC4899',
    kafka:      '#F97316', flink:     '#A78BFA', spark:    '#FB923C',
    duckdb:     '#94A3B8', all:       '#64748B',
  }
  const color = colors[p] || '#64748B'
  return (
    <span style={{
      background: `${color}18`, color: color, border: `1px solid ${color}35`,
      borderRadius: 5, padding: '1px 7px', fontSize: 10, fontWeight: 600,
      textTransform: 'uppercase', letterSpacing: '0.04em',
    }}>{p}</span>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }
  return (
    <button onClick={copy} style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.muted, padding: '2px 4px' }} title="Copy">
      {copied ? <CheckCircle2 size={13} color="#10B981" /> : <Copy size={13} />}
    </button>
  )
}

function ErrorCard({ entry }: { entry: AnomalyEntry }) {
  const [open, setOpen] = useState(false)
  const s = SEVERITY_META[entry.severity]
  const cat = CATEGORY_META[entry.category]
  const mttrSaved = Math.round(((entry.mttrMinutes.before - entry.mttrMinutes.after) / entry.mttrMinutes.before) * 100)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: T.card, border: `1px solid ${T.border}`,
        borderRadius: 12, overflow: 'hidden',
        borderLeft: `3px solid ${s.color}`,
      }}
    >
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 12,
          color: T.text, textAlign: 'left',
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 12, background: `${s.color}18`, color: s.color, padding: '2px 8px', borderRadius: 4, letterSpacing: '0.05em' }}>
              {entry.type}
            </span>
            <SeverityBadge severity={entry.severity} />
            <span style={{ fontSize: 11, color: cat.color, background: `${cat.color}18`, padding: '2px 7px', borderRadius: 4, border: `1px solid ${cat.color}30` }}>
              {cat.label}
            </span>
            {entry.autoHealable && (
              <span style={{ fontSize: 11, color: '#10B981', background: 'rgba(16,185,129,0.1)', padding: '2px 7px', borderRadius: 4, border: '1px solid rgba(16,185,129,0.3)' }}>
                ✦ Auto-Healable
              </span>
            )}
          </div>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>{entry.label}</div>
          <div style={{ color: T.sub, fontSize: 13, lineHeight: 1.5 }}>{entry.description}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, minWidth: 100 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: T.muted, marginBottom: 2 }}>MTTR BEFORE→AFTER</div>
            <div style={{ fontSize: 13, color: T.text }}>
              <span style={{ color: '#EF4444', textDecoration: 'line-through' }}>{entry.mttrMinutes.before}m</span>
              <span style={{ color: T.muted }}> → </span>
              <span style={{ color: '#10B981', fontWeight: 700 }}>{entry.mttrMinutes.after}m</span>
              <span style={{ color: '#10B981', fontSize: 11 }}> −{mttrSaved}%</span>
            </div>
          </div>
          {open ? <ChevronUp size={16} color={T.muted} /> : <ChevronDown size={16} color={T.muted} />}
        </div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '0 20px 20px', borderTop: `1px solid ${T.border}` }}>

              {/* Platforms */}
              <div style={{ marginTop: 16, marginBottom: 16, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: T.muted, marginRight: 4 }}>AFFECTS:</span>
                {entry.platforms.map(p => <PlatformTag key={p} p={p} />)}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

                {/* Impact */}
                <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 11, color: '#EF4444', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <XCircle size={12} /> BUSINESS IMPACT
                  </div>
                  <p style={{ fontSize: 13, color: T.sub, margin: 0, lineHeight: 1.6 }}>{entry.impact}</p>
                </div>

                {/* Root Causes */}
                <div style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 11, color: '#F59E0B', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={12} /> ROOT CAUSES
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {entry.rootCauses.map((c, i) => (
                      <li key={i} style={{ fontSize: 13, color: T.sub, marginBottom: 5, lineHeight: 1.5 }}>{c}</li>
                    ))}
                  </ul>
                </div>

                {/* Actions */}
                <div style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 11, color: '#10B981', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={12} /> REMEDIATION STEPS
                  </div>
                  <ol style={{ margin: 0, paddingLeft: 18 }}>
                    {entry.actions.map((a, i) => (
                      <li key={i} style={{ fontSize: 13, color: T.sub, marginBottom: 5, lineHeight: 1.5 }}>{a}</li>
                    ))}
                  </ol>
                </div>

                {/* Error Signatures */}
                <div style={{ background: 'rgba(14,165,233,0.06)', border: '1px solid rgba(14,165,233,0.2)', borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 11, color: '#0EA5E9', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Database size={12} /> ERROR SIGNATURES
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {entry.signatures.map((sig, i) => (
                      <div key={i}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                          <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#0EA5E9', background: 'rgba(14,165,233,0.15)', padding: '1px 6px', borderRadius: 4 }}>
                            {sig.pattern}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 4 }}>
                          <code style={{ fontFamily: 'monospace', fontSize: 11, color: T.muted, background: '#0A1929', padding: '4px 8px', borderRadius: 4, flex: 1, wordBreak: 'break-word', lineHeight: 1.5 }}>
                            {sig.example}
                          </code>
                          <CopyButton text={sig.example} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function ErrorCatalogPage() {
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [platformFilter, setPlatformFilter] = useState<Platform | 'all'>('all')
  const [autoHealOnly, setAutoHealOnly] = useState(false)

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return CATALOG.filter(e => {
      if (severityFilter !== 'all' && e.severity !== severityFilter) return false
      if (categoryFilter !== 'all' && e.category !== categoryFilter) return false
      if (platformFilter !== 'all' && !e.platforms.includes(platformFilter) && !e.platforms.includes('all')) return false
      if (autoHealOnly && !e.autoHealable) return false
      if (!q) return true
      return (
        e.type.toLowerCase().includes(q) ||
        e.label.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.rootCauses.some(r => r.toLowerCase().includes(q)) ||
        e.actions.some(a => a.toLowerCase().includes(q)) ||
        e.signatures.some(s => s.pattern.toLowerCase().includes(q) || s.example.toLowerCase().includes(q))
      )
    })
  }, [search, severityFilter, categoryFilter, platformFilter, autoHealOnly])

  const stats = useMemo(() => ({
    total: CATALOG.length,
    critical: CATALOG.filter(e => e.severity === 'critical').length,
    autoHealable: CATALOG.filter(e => e.autoHealable).length,
    avgMttrBefore: Math.round(CATALOG.reduce((s, e) => s + e.mttrMinutes.before, 0) / CATALOG.length),
    avgMttrAfter: Math.round(CATALOG.reduce((s, e) => s + e.mttrMinutes.after, 0) / CATALOG.length),
  }), [])

  const filterBtn = (active: boolean, label: string, onClick: () => void, color = T.accent) => (
    <button
      onClick={onClick}
      style={{
        padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
        cursor: 'pointer', border: `1px solid ${active ? color : T.border}`,
        background: active ? `${color}20` : 'transparent',
        color: active ? color : T.muted, transition: 'all 0.15s',
      }}
    >{label}</button>
  )

  return (
    <div style={{ minHeight: '100vh', background: T.bg, color: T.text, padding: '28px 32px', fontFamily: 'Inter, system-ui, sans-serif' }}>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10, background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={18} color="#EF4444" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Error Catalog</h1>
            <p style={{ margin: 0, color: T.muted, fontSize: 13 }}>All anomaly types — root causes, impact, and actionable remediation steps</p>
          </div>
        </div>
        <div style={{ height: 2, background: 'linear-gradient(90deg, #EF4444 0%, #7C3AED 50%, transparent 100%)', borderRadius: 1, marginTop: 16 }} />
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Anomaly Types', value: stats.total, color: '#0EA5E9' },
          { label: 'Critical', value: stats.critical, color: '#EF4444' },
          { label: 'Auto-Healable', value: `${stats.autoHealable}/${stats.total}`, color: '#10B981' },
          { label: 'Avg MTTR Before', value: `${stats.avgMttrBefore}m`, color: '#F59E0B' },
          { label: 'Avg MTTR After', value: `${stats.avgMttrAfter}m`, color: '#10B981' },
        ].map(s => (
          <div key={s.label} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, color: T.muted, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Search + Filters */}
      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <Search size={16} color={T.muted} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by type, description, root cause, or error signature…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: T.text, fontSize: 14, caretColor: T.accent,
            }}
          />
          {search && <button onClick={() => setSearch('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.muted }}><XCircle size={14} /></button>}
          <span style={{ fontSize: 12, color: T.muted }}>{filtered.length} / {CATALOG.length}</span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Filter size={13} color={T.muted} />
          <span style={{ fontSize: 11, color: T.muted }}>Severity:</span>
          {filterBtn(severityFilter === 'all', 'All', () => setSeverityFilter('all'))}
          {(['critical','high','medium','low'] as Severity[]).map(s =>
            filterBtn(severityFilter === s, SEVERITY_META[s].label, () => setSeverityFilter(s), SEVERITY_META[s].color)
          )}
          <span style={{ width: 1, height: 18, background: T.border, margin: '0 4px' }} />
          <span style={{ fontSize: 11, color: T.muted }}>Category:</span>
          {filterBtn(categoryFilter === 'all', 'All', () => setCategoryFilter('all'))}
          {Object.entries(CATEGORY_META).map(([k, v]) =>
            filterBtn(categoryFilter === k, v.label, () => setCategoryFilter(k), v.color)
          )}
          <span style={{ width: 1, height: 18, background: T.border, margin: '0 4px' }} />
          <button
            onClick={() => setAutoHealOnly(v => !v)}
            style={{
              padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', border: `1px solid ${autoHealOnly ? '#10B981' : T.border}`,
              background: autoHealOnly ? 'rgba(16,185,129,0.15)' : 'transparent',
              color: autoHealOnly ? '#10B981' : T.muted,
            }}
          >
            ✦ Auto-Healable Only
          </button>
        </div>
      </div>

      {/* Error list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 0', color: T.muted }}>
            <AlertTriangle size={32} style={{ opacity: 0.4, marginBottom: 12 }} />
            <div style={{ fontSize: 15 }}>No anomaly types match your filters.</div>
          </div>
        ) : (
          filtered.map(entry => <ErrorCard key={entry.type} entry={entry} />)
        )}
      </div>
    </div>
  )
}
