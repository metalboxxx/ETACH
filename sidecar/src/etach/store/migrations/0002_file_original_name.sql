-- 0002_file_original_name: data-model.md v1.5 §2.8 / §3, the dropped file's name for uploads.
ALTER TABLE files ADD COLUMN original_name TEXT;
