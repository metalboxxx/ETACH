-- 0010_regrade_pending: data-model v1.20 (PRD v8.1 "Re-grade after checking keys", step 22.4.5).
-- A teacher key change (PUT /tests/{id}/keys/{qid}, the key Review fixes) on a test with graded
-- attempts adds the test here instead of queueing key_verified runs at once.
-- POST /tests/{id}/regrade queues 1 grade run per graded attempt and deletes the row.
CREATE TABLE regrade_pending (test_id TEXT PRIMARY KEY REFERENCES tests(id) ON DELETE CASCADE,
  since TEXT NOT NULL);
