-- 0003_test_name_pattern: data-model v1.11 (decision C). Remakes each stored test name with the
-- teacher's pattern, as TestMetadata.display_name() makes it ("Grade 8 - Final Term 1 - <school,
-- else source> - <year> - Test 7"), once, and leaves updated_at alone. A name the teacher edited
-- (display_name in edited_fields) is kept. The search row gets the new name and the occasion
-- code (db._meta_text keeps the codes searchable). test_name_migration test checks it equals
-- display_name().
WITH n AS (
  SELECT id,
    CASE
      WHEN occasion LIKE 'Other:%' THEN COALESCE(NULLIF(trim(substr(occasion, 7)), ''), 'Other')
      WHEN occasion = 'MidTerm' THEN 'Mid-term'
      WHEN occasion = 'FinalTerm' THEN 'Final Term'
      WHEN occasion = 'NationalExam' THEN 'National Exam'
      WHEN occasion = 'EntranceExam' THEN 'Entrance Exam'
      WHEN occasion = 'GiftedExam' THEN 'Gifted Exam'
      WHEN occasion = 'UnitTest' THEN 'Unit'
      WHEN occasion = 'FifteenMinuteTest' THEN '15-minute'
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
  SELECT COALESCE('Grade ' || n.gr || ' - ', '') || n.occ || COALESCE(' ' || n.te, '')
    || COALESCE(' - ' || n.who, '')
    || COALESCE(' - ' || replace(n.yr, '-', char(8211)), '')
    || COALESCE(' - Test ' || n.tn, '')
  FROM n WHERE n.id = tests.id
)
WHERE id IN (SELECT id FROM n);

UPDATE tests_fts SET
  display_name = (SELECT t.display_name FROM tests t WHERE t.id = tests_fts.test_id),
  meta_text = trim(meta_text || ' ' || (SELECT t.occasion FROM tests t WHERE t.id = tests_fts.test_id));
