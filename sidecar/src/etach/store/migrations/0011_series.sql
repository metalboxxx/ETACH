-- 0011_series: data-model v1.21 (step 22.5.2, decisions D2, D5). The series list becomes a table
-- the teacher edits in Settings, like the school list (0008). It is seeded from the distinct
-- trimmed, non-empty series (`meta.source`) already on tests, oldest first; a case variant of a
-- name already in the list is skipped (the first spelling is kept; Vietnamese capitals are merged
-- in Python, etach.store.repos.series.merge_case_variants). tests keep the name in meta.source.
CREATE TABLE series (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  position INTEGER NOT NULL
);

INSERT OR IGNORE INTO series (name, position)
SELECT name, 0 FROM (
  SELECT trim(json_extract(meta, '$.source')) AS name, created_at, id FROM tests
  WHERE json_extract(meta, '$.source') IS NOT NULL
    AND trim(json_extract(meta, '$.source')) <> ''
  ORDER BY created_at, id
);

UPDATE series SET position = (SELECT COUNT(*) FROM series s2 WHERE s2.id < series.id);

-- The one-time first-start pass over stored tests (etach.store.repos.text_pass): option labels
-- that still carry punctuation are cleaned ("A.." in the test text) and untitled sections take
-- their title from their section skill (D2). This table holds one row until the pass has run;
-- the pass deletes it in the same transaction, so it runs once.
CREATE TABLE test_text_pending (id INTEGER PRIMARY KEY CHECK (id = 1));
INSERT INTO test_text_pending (id) VALUES (1);
