-- 0007_occasions: data-model v1.17 (step 22.3.7, PRD v7.2). The occasion list becomes a table the
-- teacher edits in Settings. It is seeded with the ten built-in occasions: the label is the plain
-- English name shown in the Occasion editor and chips (step 22.2.1), the short name is the one the
-- Test name uses (step 22.2.7). Built-ins can be renamed and moved, never deleted. A teacher
-- occasion's code is "Custom:<id>". No test name changes here: the seed gives today's names.
CREATE TABLE occasions (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  short_name TEXT NOT NULL,
  position INTEGER NOT NULL,
  builtin INTEGER NOT NULL
);

INSERT INTO occasions (code, label, short_name, position, builtin) VALUES
  ('MidTerm', 'Mid-term test', 'Mid-term', 0, 1),
  ('FinalTerm', 'Final-term test', 'Final Term', 1, 1),
  ('NationalExam', 'National exam', 'National Exam', 2, 1),
  ('EntranceExam', 'Entrance exam', 'Entrance Exam', 3, 1),
  ('GiftedExam', 'Gifted students'' exam', 'Gifted Exam', 4, 1),
  ('UnitTest', 'Unit test', 'Unit Test', 5, 1),
  ('FifteenMinuteTest', '15-minute test', '15-minute Test', 6, 1),
  ('GrammarPractice', 'Grammar practice', 'Grammar Practice', 7, 1),
  ('TopicPractice', 'Topic practice', 'Topic Practice', 8, 1),
  ('Placement', 'Placement test', 'Placement', 9, 1);

-- search rows: the occasion's label is searchable too (db._meta_text ends with code, then label)
UPDATE tests_fts SET meta_text = trim(meta_text || ' ' || (
  SELECT o.label FROM tests t JOIN occasions o ON o.code = t.occasion WHERE t.id = tests_fts.test_id))
WHERE EXISTS (
  SELECT 1 FROM tests t JOIN occasions o ON o.code = t.occasion WHERE t.id = tests_fts.test_id);
