/**
 * The search form of a student's name, as the sidecar stores it in `students.name_search`
 * (`domain/normalize.py` `name_search`): accents removed, `đ` → `d`, lowercase, single spaces.
 * The student chip uses it to tell whether a typed name is already a student.
 */
export function nameSearch(s: string): string {
  return s
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}
