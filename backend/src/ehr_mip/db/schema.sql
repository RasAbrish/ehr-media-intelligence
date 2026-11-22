-- Generated from docs/03-DATA-MODEL.md section 4.2. Keep the two in sync.
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pipeline_runs (
  run_id TEXT PRIMARY KEY, stage TEXT NOT NULL,
  started_at TEXT NOT NULL, finished_at TEXT, stats_json TEXT);

CREATE TABLE IF NOT EXISTS patients (
  patient_key TEXT PRIMARY KEY, mrn TEXT NOT NULL,
  family_name TEXT, given_names TEXT, birth_date TEXT, gender TEXT NOT NULL,
  identity_conflict INTEGER NOT NULL DEFAULT 0, data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_patients_mrn ON patients(mrn);
CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(family_name, given_names);

CREATE TABLE IF NOT EXISTS encounters (
  encounter_key TEXT PRIMARY KEY,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  encounter_class TEXT, period_start TEXT, data_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS documents (
  document_key TEXT PRIMARY KEY,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  encounter_key TEXT REFERENCES encounters(encounter_key),
  doc_type TEXT NOT NULL, document_date TEXT, content_hash TEXT NOT NULL, data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_key, document_date);

CREATE TABLE IF NOT EXISTS lab_results (
  result_key TEXT PRIMARY KEY,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  report_key TEXT NOT NULL, loinc TEXT, collected_at TEXT, data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_labs_patient ON lab_results(patient_key, collected_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT REFERENCES pipeline_runs(run_id), record_id TEXT NOT NULL, patient_key TEXT,
  stage TEXT NOT NULL, field TEXT, rule TEXT NOT NULL, before TEXT, after TEXT,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')), message TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_log(patient_key);
CREATE INDEX IF NOT EXISTS idx_audit_rule ON audit_log(rule, severity);

CREATE TABLE IF NOT EXISTS quarantine (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT REFERENCES pipeline_runs(run_id),
  source_locator TEXT NOT NULL, reason TEXT NOT NULL, payload_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS fhir_bundles (
  patient_key TEXT PRIMARY KEY REFERENCES patients(patient_key) ON DELETE CASCADE,
  bundle_json TEXT NOT NULL, bundle_hash TEXT NOT NULL,
  is_valid INTEGER NOT NULL, error_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS fhir_resources (
  resource_id TEXT PRIMARY KEY,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  resource_type TEXT NOT NULL, resource_date TEXT, title TEXT, subtype TEXT,
  text_content TEXT, resource_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_res_patient ON fhir_resources(patient_key, resource_type, resource_date);

CREATE TABLE IF NOT EXISTS validation_issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_key TEXT REFERENCES patients(patient_key) ON DELETE CASCADE,
  resource_type TEXT, resource_id TEXT, path TEXT,
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
  code TEXT NOT NULL, message TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_vi_severity ON validation_issues(severity, code);

CREATE TABLE IF NOT EXISTS summary_cache (
  cache_key TEXT PRIMARY KEY,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  bundle_hash TEXT NOT NULL, model TEXT, prompt_version TEXT NOT NULL,
  provider TEXT NOT NULL, summary_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_summary_patient ON summary_cache(patient_key, created_at DESC);

-- AI telemetry: no prompt or output content, ids and numbers only
CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_key TEXT REFERENCES patients(patient_key) ON DELETE CASCADE,
  cache_key TEXT, provider TEXT NOT NULL, model TEXT, prompt_version TEXT NOT NULL,
  input_tokens INTEGER, output_tokens INTEGER, cost_usd_estimate REAL,
  latency_ms INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL CHECK (status IN ('ok','retried','fallback','failed')),
  guardrail_notes_count INTEGER NOT NULL DEFAULT 0, word_count INTEGER, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_llm_calls_time ON llm_calls(created_at);

CREATE TABLE IF NOT EXISTS summary_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_key TEXT NOT NULL REFERENCES patients(patient_key) ON DELETE CASCADE,
  cache_key TEXT NOT NULL REFERENCES summary_cache(cache_key) ON DELETE CASCADE,
  prompt_version TEXT NOT NULL,
  rating TEXT NOT NULL CHECK (rating IN ('helpful','not_helpful')),
  reason TEXT CHECK (reason IN ('inaccurate','missing_information','too_long','unclear','other')),
  comment TEXT CHECK (length(comment) <= 280),
  client_id_hash TEXT,           -- sha256 of an anonymous browser id, for one-vote-per-client
  created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_feedback_client ON summary_feedback(cache_key, client_id_hash);

-- Sign-in (ADR-013). Only the SHA-256 of a session token is stored.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
