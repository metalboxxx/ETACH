-- 0001_init: data-model.md v1.2 §3 (tables) and §4 (view), copied verbatim.
-- The pragmas (foreign_keys, journal_mode=WAL) are set per connection in etach.store.db.connect().

-- people & tests
CREATE TABLE students (id TEXT PRIMARY KEY, full_name TEXT NOT NULL, name_search TEXT NOT NULL,
  class_name TEXT, school TEXT, grade INTEGER, notes TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE INDEX students_name ON students(name_search);

CREATE TABLE tests (id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
  occasion TEXT NOT NULL, grade INTEGER, year TEXT, school TEXT, term INTEGER, test_number TEXT,
  created_by_ai INTEGER NOT NULL DEFAULT 0, parent_test_id TEXT REFERENCES tests(id),
  meta JSON NOT NULL, content JSON NOT NULL, content_schema_version INTEGER NOT NULL,
  fingerprint TEXT NOT NULL, points_possible REAL NOT NULL,
  source_run_id TEXT UNIQUE, merged_into TEXT REFERENCES tests(id),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX tests_grade ON tests(grade) WHERE merged_into IS NULL;

CREATE TABLE test_pages (test_id TEXT NOT NULL REFERENCES tests(id), page_no INTEGER NOT NULL,
  file_id TEXT NOT NULL REFERENCES files(id), PRIMARY KEY (test_id, page_no));
  -- question ranges per page are derived from Question.page_no

CREATE TABLE answer_keys (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  accepted JSON NOT NULL, reason_vi TEXT, source TEXT NOT NULL, status TEXT NOT NULL,
  confidence REAL, updated_at TEXT NOT NULL, PRIMARY KEY (test_id, question_id));

CREATE TABLE question_tags (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  tag TEXT NOT NULL, PRIMARY KEY (test_id, question_id, tag));
CREATE INDEX question_tags_tag ON question_tags(tag);

-- attempts
CREATE TABLE attempts (id TEXT PRIMARY KEY, test_id TEXT NOT NULL REFERENCES tests(id),
  thread_id TEXT NOT NULL REFERENCES threads(id), student_id TEXT REFERENCES students(id),
  student_name_read TEXT, class_read TEXT, source_run_id TEXT NOT NULL UNIQUE,
  superseded_by TEXT REFERENCES attempts(id), status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
  score_earned REAL, score_possible REAL, created_at TEXT NOT NULL);
CREATE INDEX attempts_test ON attempts(test_id);
CREATE INDEX attempts_student ON attempts(student_id);
CREATE INDEX attempts_thread ON attempts(thread_id);

CREATE TABLE attempt_pages (attempt_id TEXT NOT NULL REFERENCES attempts(id), page_no INTEGER NOT NULL,
  file_id TEXT NOT NULL REFERENCES files(id), source_file_id TEXT NOT NULL REFERENCES files(id),
  rotation INTEGER NOT NULL, PRIMARY KEY (attempt_id, page_no));

CREATE TABLE answers (attempt_id TEXT NOT NULL REFERENCES attempts(id), question_id TEXT NOT NULL,
  printed_number INTEGER, page_no INTEGER, value TEXT, value_norm TEXT, location TEXT NOT NULL,
  confidence REAL NOT NULL, low_trust INTEGER NOT NULL DEFAULT 0, reading_unsure INTEGER NOT NULL DEFAULT 0,
  alt_value TEXT, alt_question_id TEXT, verdict TEXT NOT NULL DEFAULT 'ungraded',
  near_miss INTEGER NOT NULL DEFAULT 0, points_awarded REAL, teacher_override TEXT,
  PRIMARY KEY (attempt_id, question_id));

CREATE TABLE grade_reports (attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
  run_id TEXT NOT NULL REFERENCES runs(id), weak_points JSON NOT NULL, careless_notes JSON NOT NULL,
  summary_vi TEXT NOT NULL, teacher_questions JSON NOT NULL, uncertain_points REAL NOT NULL,
  created_at TEXT NOT NULL);           -- one current report per attempt; re-grade replaces it

CREATE TABLE explanations (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  wrong_answer_norm TEXT NOT NULL, error_type TEXT NOT NULL, text_vi TEXT NOT NULL,
  status TEXT NOT NULL, llm_call_id TEXT REFERENCES llm_calls(id),
  PRIMARY KEY (test_id, question_id, wrong_answer_norm));

-- conversation & workflow
CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, test_id TEXT REFERENCES tests(id),
  kind TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
CREATE TABLE messages (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
  role TEXT NOT NULL, kind TEXT NOT NULL, body JSON, created_at TEXT NOT NULL);
CREATE INDEX messages_thread ON messages(thread_id, created_at);

CREATE TABLE runs (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
  kind TEXT NOT NULL, input JSON NOT NULL, status TEXT NOT NULL,
  started_at TEXT, finished_at TEXT, error TEXT);
CREATE INDEX runs_status ON runs(status);
CREATE TABLE steps (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), node TEXT NOT NULL,
  item TEXT, try_no INTEGER NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT);
CREATE INDEX steps_run ON steps(run_id, started_at);
CREATE TABLE llm_calls (id TEXT PRIMARY KEY, step_id TEXT NOT NULL REFERENCES steps(id), role TEXT, model TEXT,
  prompt_hash TEXT, request JSON, response_text TEXT, thinking_text TEXT, logprobs JSON, status TEXT NOT NULL,
  tokens_in INTEGER, tokens_out INTEGER, ms INTEGER, created_at TEXT NOT NULL);
CREATE INDEX llm_calls_step ON llm_calls(step_id);
-- LangGraph's SqliteSaver creates its own checkpoint tables in the same file.

-- misc
CREATE TABLE review_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL,
  test_id TEXT REFERENCES tests(id), attempt_id TEXT REFERENCES attempts(id), question_id TEXT,
  dedupe_key TEXT NOT NULL UNIQUE, proposal JSON NOT NULL, resolution JSON,
  followup_run_id TEXT REFERENCES runs(id), status TEXT NOT NULL,
  created_at TEXT NOT NULL, resolved_at TEXT);
CREATE INDEX review_open ON review_items(status, created_at);
CREATE INDEX review_attempt ON review_items(attempt_id);

CREATE TABLE files (id TEXT PRIMARY KEY, path TEXT NOT NULL, kind TEXT NOT NULL,
  derived_from TEXT REFERENCES files(id), mime TEXT, width INTEGER, height INTEGER, created_at TEXT NOT NULL);
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

-- search: English display names for now; accent removal via remove_diacritics
-- (Vietnamese search words and the đ→d fold are deferred, PRD §2)
CREATE VIRTUAL TABLE tests_fts USING fts5(test_id UNINDEXED, display_name, meta_text,
  tokenize = 'unicode61 remove_diacritics 2');
-- queries use per-token prefix matching: "grade 8 final test 1" → grade* 8* final* test* 1*,
-- so "final" finds "FinalTerm"

-- data-model §4: derived view, weak points
CREATE VIEW student_skill_stats AS
SELECT a.student_id, qt.tag AS skill_tag,
       SUM(ans.verdict IN ('correct','incorrect'))              AS seen,      -- "?" answers don't count
       SUM(ans.verdict = 'incorrect')                           AS wrong,
       SUM(ans.verdict = 'incorrect' AND e.error_type = 'gap')  AS gap_errors,
       MAX(a.created_at)                                        AS last_seen
FROM answers ans
JOIN attempts a       ON a.id = ans.attempt_id AND a.superseded_by IS NULL
JOIN question_tags qt ON qt.test_id = a.test_id AND qt.question_id = ans.question_id
LEFT JOIN explanations e ON e.test_id = a.test_id AND e.question_id = ans.question_id
                        AND e.wrong_answer_norm = ans.value_norm
WHERE a.student_id IS NOT NULL
GROUP BY a.student_id, qt.tag;
