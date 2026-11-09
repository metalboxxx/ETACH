-- 0006_key_forms: data-model v1.15 (the teacher's comment 10, step 22.3.4). Sentence keys
-- (rewrite / combine) carry their accepted forms. The forms are made in Python
-- (etach.domain.keys.with_forms), so this migration only lists the tests whose existing keys get
-- them once: etach.store.repos.keys.list_keys upgrades a listed test's keys on its first read
-- (updated_at kept, explanations kept) and removes it from the list.
CREATE TABLE key_forms_pending (test_id TEXT PRIMARY KEY);
INSERT INTO key_forms_pending (test_id) SELECT DISTINCT test_id FROM answer_keys;
