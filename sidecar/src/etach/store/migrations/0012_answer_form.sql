-- 0012_answer_form: data-model v1.22 (step 22.5.3, decision D9). The 11 question types become the
-- answer form (choice / word / sentence / writing) and the context (single / paragraph). Test
-- content is JSON, so no table changes shape; this table only guards the one-time first-start
-- pass over the stored tests (etach.store.repos.answer_form_pass), which maps every question and
-- keeps its old type in `old_type`. It holds one row until the pass has run; the pass deletes it
-- in the same transaction, so it runs once.
CREATE TABLE answer_form_pending (id INTEGER PRIMARY KEY CHECK (id = 1));
INSERT INTO answer_form_pending (id) VALUES (1);
