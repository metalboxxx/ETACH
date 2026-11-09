-- 0009_equal_points: data-model v1.19 (PRD D13 v8.0, step 22.4.4). The score is always out of
-- 10: every graded question is worth 10 / N. The rewrite of stored tests is done in Python
-- (etach.store.repos.points.run_equal_points_pass) at the first start after this migration: it
-- cleans option letters, sets equal points, closes open points_assumed items and stale
-- validator_failed items, and re-scores every graded attempt from its stored verdicts (no model
-- call). This table holds one row until that pass has run; the pass deletes it in the same
-- transaction, so it runs once.
CREATE TABLE equal_points_pending (id INTEGER PRIMARY KEY CHECK (id = 1));
INSERT INTO equal_points_pending (id) VALUES (1);
