-- 0015_key_photo_status: data-model v1.25 (step 22.5.6). A key read from the key photo is no longer
-- `ai_verified` without a second model call: it gets the status `from_key_photo`. Statuses are
-- TEXT, so no table changes shape; this table only guards the one-time first-start pass
-- (etach.store.repos.key_photo_pass), which moves the stored key-photo keys that no check verified
-- to `from_key_photo`. It holds one row until the pass has run; the pass deletes it in the same
-- transaction, so it runs once.
CREATE TABLE key_photo_pending (id INTEGER PRIMARY KEY CHECK (id = 1));
INSERT INTO key_photo_pending (id) VALUES (1);
