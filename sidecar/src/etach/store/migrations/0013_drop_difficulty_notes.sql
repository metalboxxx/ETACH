-- 0013_drop_difficulty_notes: data-model v1.23 (step 22.5.4, decision D10: drop). The difficulty
-- notes step is gone and `meta.test_difficulty_notice_comment_by_ai` leaves TestMetadata. Test
-- meta is JSON, so no table changes shape; this table only guards the one-time first-start pass
-- (etach.store.repos.difficulty_pass), which removes that one key from every stored test's meta. It
-- holds one row until the pass has run; the pass deletes it in the same transaction, so it runs
-- once.
CREATE TABLE difficulty_notes_pending (id INTEGER PRIMARY KEY CHECK (id = 1));
INSERT INTO difficulty_notes_pending (id) VALUES (1);
