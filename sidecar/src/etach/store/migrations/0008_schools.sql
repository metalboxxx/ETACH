-- 0008_schools: data-model v1.18 (step 22.4.2, PRD v7.3). The school list becomes a table the
-- teacher edits in Settings. It is seeded from the distinct trimmed, non-empty schools already on
-- tests, then on students, oldest first; a case variant of a name already in the list is skipped
-- (the first spelling is kept). tests.school and students.school keep the name as text.
CREATE TABLE schools (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  position INTEGER NOT NULL
);

INSERT OR IGNORE INTO schools (name, position)
SELECT name, 0 FROM (
  SELECT trim(school) AS name, 0 AS src, created_at, id FROM tests
  WHERE school IS NOT NULL AND trim(school) <> ''
  UNION ALL
  SELECT trim(school) AS name, 1 AS src, created_at, id FROM students
  WHERE school IS NOT NULL AND trim(school) <> ''
  ORDER BY src, created_at, id
);

UPDATE schools SET position = (SELECT COUNT(*) FROM schools s2 WHERE s2.id < schools.id);
