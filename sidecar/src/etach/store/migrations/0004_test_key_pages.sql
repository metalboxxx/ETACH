-- 0004_test_key_pages: data-model v1.12 (teacher's answer 10). The key photos a test was
-- extracted with are kept, so the Key workspace can show them; the file sweep keeps them.
CREATE TABLE IF NOT EXISTS test_key_pages (test_id TEXT NOT NULL REFERENCES tests(id),
  page_no INTEGER NOT NULL, file_id TEXT NOT NULL REFERENCES files(id),
  PRIMARY KEY (test_id, page_no));
