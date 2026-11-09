-- 0005_test_name_answers: data-model v1.13 (the teacher's answers 4-5, step 22.2.7). Remakes each
-- automatic test name once, as TestMetadata.display_name() now makes it: "Unit Test" and
-- "15-minute Test", and an unknown occasion (Other:unknown) left out ("Untitled test" when
-- nothing is left). A name the teacher typed
-- (display_name in edited_fields) is kept; updated_at is left alone. The search row gets the new
-- name. test_name_migration test checks it equals display_name().
WITH n AS (
  SELECT id,
    CASE
      WHEN occasion = 'Other:unknown' THEN NULL
      WHEN occasion LIKE 'Other:%' THEN COALESCE(NULLIF(trim(substr(occasion, 7)), ''), 'Other')
      WHEN occasion = 'MidTerm' THEN 'Mid-term'
      WHEN occasion = 'FinalTerm' THEN 'Final Term'
      WHEN occasion = 'NationalExam' THEN 'National Exam'
      WHEN occasion = 'EntranceExam' THEN 'Entrance Exam'
      WHEN occasion = 'GiftedExam' THEN 'Gifted Exam'
      WHEN occasion = 'UnitTest' THEN 'Unit Test'
      WHEN occasion = 'FifteenMinuteTest' THEN '15-minute Test'
      WHEN occasion = 'GrammarPractice' THEN 'Grammar Practice'
      WHEN occasion = 'TopicPractice' THEN 'Topic Practice'
      ELSE occasion
    END AS occ,
    COALESCE(NULLIF(json_extract(meta, '$.school'), ''), NULLIF(json_extract(meta, '$.source'), '')) AS who,
    NULLIF(json_extract(meta, '$.year'), '') AS yr,
    NULLIF(json_extract(meta, '$.test_number'), '') AS tn,
    json_extract(meta, '$.grade') AS gr,
    json_extract(meta, '$.term') AS te
  FROM tests
  WHERE NOT EXISTS (
    SELECT 1 FROM json_each(tests.meta, '$.edited_fields') WHERE value = 'display_name'
  )
)
UPDATE tests SET display_name = (
  SELECT COALESCE(NULLIF(substr(
    COALESCE(' - Grade ' || n.gr, '')
    || COALESCE(' - ' || n.occ || COALESCE(' ' || n.te, ''), '')
    || COALESCE(' - ' || n.who, '')
    || COALESCE(' - ' || replace(n.yr, '-', char(8211)), '')
    || COALESCE(' - Test ' || n.tn, ''),
    4), ''), 'Untitled test')
  FROM n WHERE n.id = tests.id
)
WHERE id IN (SELECT id FROM n);

UPDATE tests_fts SET
  display_name = (SELECT t.display_name FROM tests t WHERE t.id = tests_fts.test_id);
