-- 0014_checker_taken_on_levels: data-model v1.24 (step 22.5.5).
-- The checker's answer on an unsure key: when verify_key does not confirm a key, the key keeps
-- what the checker said (JSON: {"status": "disagreed" | "did_not_finish", "answer", "reasoning"});
-- NULL for every other key, including the keys stored before this migration.
ALTER TABLE answer_keys ADD COLUMN checker JSON;

-- The date taken (D11a): the day the student did the paper. The trajectory orders a student's
-- papers by it, then created_at. Stored attempts get the (local) date of created_at; new ones
-- get the date sent with the photos (default today).
ALTER TABLE attempts ADD COLUMN taken_on TEXT;
UPDATE attempts SET taken_on = date(created_at, 'localtime');

-- Levels (D11d): tag_skills gives each question a CEFR level (A1, A2, B1, B2), kept on each of
-- its tag rows; NULL = not given (the tags stored before this migration), so a tag's level
-- falls back to its skill's base level (etach.domain.levels).
ALTER TABLE question_tags ADD COLUMN level TEXT;
