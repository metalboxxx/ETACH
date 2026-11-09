/**
 * The Students tab under the sidebar switch (PRD §10 "Delete and Students", v5.3; step 22.2.3).
 *
 * `GET /students?q=` lists the students with their class and thread count; the search uses the
 * sidecar's `name_search` form, so Vietnamese names match with or without accents. Clicking a
 * row (or Enter / Space on it) opens the student's skills and threads in the main panel
 * (`onOpenStudent`; step 22.5.5 checklist (c), R22.5.5.11). "Edit" changes
 * the name and class in place: `Enter` saves (`PATCH /students/{id}`), `Escape` cancels.
 * "Delete…" (`onDelete`; step 22.3.3, D1): the shell asks first, naming the threads that go,
 * then deletes; focus moves to the row now in its place, or to the search box.
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { useFocusAfterDelete } from "@/hooks/useFocusAfterDelete";
import { SchoolCombobox } from "@/components/SchoolCombobox";
import { errorText } from "@/lib/errors";
import { loadSchools, useSchools } from "@/lib/schools";

type StudentSummary = Schemas["StudentSummary"];

export interface StudentsTabProps {
  api: ApiClient | null;
  /** Opens the student's skills view in the main panel (R22.5.5.11). */
  onOpenStudent?: (studentId: string, name: string) => void;
  /** The student whose skills view is open: its row is marked current. */
  activeStudentId?: string | null;
  /** Changes when the list should reload (run events, deletes, student edits elsewhere). */
  refreshKey?: number;
  /** Debounce for typing, in ms. */
  debounceMs?: number;
  /** A student's name, class or school was saved (the open skills view reloads). */
  onStudentChanged?: () => void;
  /** "Delete…" on a row. Without it, no Delete button. */
  onDelete?: (studentId: string, name: string) => void;
}

export function StudentsTab({
  api,
  onOpenStudent,
  activeStudentId,
  refreshKey = 0,
  debounceMs = 200,
  onDelete,
  onStudentChanged,
}: StudentsTabProps) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<StudentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [seq, setSeq] = useState(0);
  useSchools(api ?? undefined); // step 22.4.2: the School field picks from the school list
  const root = useRef<HTMLDivElement>(null);
  const ids = useMemo(() => rows?.map((s) => s.id) ?? null, [rows]);
  // After a delete, focus goes to the row now in its place, or to the search box (F3).
  const markDeleted = useFocusAfterDelete(ids, (id) => {
    const el = id
      ? root.current?.querySelector<HTMLElement>(
          `[data-testid="student-row"][data-student-id="${CSS.escape(id)}"] [data-testid="student-item"]`,
        )
      : root.current?.querySelector<HTMLElement>('[data-testid="students-search"]');
    el?.focus();
  });

  useEffect(() => {
    if (!api) return;
    const q = query.trim();
    const ctrl = new AbortController();
    const timer = setTimeout(
      () => {
        api
          .get("/students", { query: q ? { q } : {}, signal: ctrl.signal })
          .then((r) => {
            setRows(Array.isArray(r) ? r : []);
            setError(null);
          })
          .catch((err: unknown) => {
            if (!ctrl.signal.aborted) setError(errorText(err));
          });
      },
      q ? debounceMs : 0,
    );
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [api, query, refreshKey, seq, debounceMs]);

  const save = async (id: string, fullName: string, className: string, school: string) => {
    if (!api) return;
    await api.patch("/students/{id}", {
      path: { id },
      body: { full_name: fullName, class_name: className, school: school || null },
    });
    setSeq((n) => n + 1);
    onStudentChanged?.();
    // a new school typed here joins the list in the sidecar (step 22.4.2)
    void loadSchools(api).catch(() => undefined);
  };

  return (
    <div ref={root} className="flex flex-col gap-2" data-testid="students-tab">
      <input
        type="search"
        data-testid="students-search"
        aria-label="Search students"
        placeholder="Search students…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-paper border border-input bg-surface px-2 py-1 text-sm text-text placeholder:text-muted focus-visible:outline-2 focus-visible:outline-focus"
      />
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
      {rows === null ? (
        api ? (
          <span>Loading…</span>
        ) : null
      ) : rows.length === 0 ? (
        <span data-testid="students-empty">
          {query.trim() ? "No students match." : "No students yet. They appear when a paper gets a student."}
        </span>
      ) : (
        <ul className="flex flex-col gap-1" data-testid="students-list">
          {rows.map((s) => (
            <li key={s.id} data-testid="student-row" data-student-id={s.id}>
              {editing === s.id ? (
                <StudentEdit
                  student={s}
                  onCancel={() => setEditing(null)}
                  onSave={async (name, cls, school) => {
                    await save(s.id, name, cls, school);
                    setEditing(null);
                  }}
                />
              ) : (
                <div
                  className={
                    "group flex items-center rounded-paper text-text " +
                    (s.id === activeStudentId ? "bg-tint-strong" : "hover:bg-tint")
                  }
                >
                  <button
                    type="button"
                    data-testid="student-item"
                    aria-current={s.id === activeStudentId ? "page" : undefined}
                    onClick={() => onOpenStudent?.(s.id, s.full_name)}
                    className="flex min-w-0 flex-1 items-center gap-2 rounded-paper px-2 py-1 text-left text-sm focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate" data-testid="student-name">
                        {s.full_name}
                      </span>
                      <span className="block truncate text-xs text-muted" data-testid="student-class">
                        {s.class_name ? `Class ${s.class_name}` : "No class"}
                      </span>
                    </span>
                    {/* A name on a plain span is not read; the count is read as text (F4). */}
                    <span
                      data-testid="student-thread-count"
                      aria-hidden="true"
                      className="shrink-0 rounded-full bg-hover px-1.5 text-xs text-muted"
                    >
                      {s.thread_count}
                    </span>
                    <span className="sr-only">
                      {s.thread_count === 1 ? " 1 thread" : ` ${s.thread_count} threads`}
                    </span>
                  </button>
                  <button
                    type="button"
                    data-testid="student-edit-button"
                    aria-label={`Edit ${s.full_name}`}
                    onClick={() => setEditing(s.id)}
                    className="shrink-0 rounded-button px-2 py-1 text-xs text-muted hover:bg-tint-strong hover:text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                  >
                    Edit
                  </button>
                  {onDelete && (
                    <button
                      type="button"
                      data-testid="student-delete-button"
                      aria-label={`Delete ${s.full_name}…`}
                      onClick={() => {
                        markDeleted(s.id);
                        onDelete(s.id, s.full_name);
                      }}
                      className="shrink-0 rounded-button px-2 py-1 text-xs text-danger hover:bg-tint-strong focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
                    >
                      Delete…
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Name, class and school in place: `Enter` saves, `Escape` cancels; focus returns to the row's Edit. */
function StudentEdit({
  student,
  onSave,
  onCancel,
}: {
  student: StudentSummary;
  onSave: (fullName: string, className: string, school: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(student.full_name);
  const [cls, setCls] = useState(student.class_name ?? "");
  const [school, setSchool] = useState(student.school ?? "");
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const submit = async () => {
    if (busy.current) return;
    const clean = name.split(/\s+/).filter(Boolean).join(" ");
    if (!clean) {
      setError("Type the student's name.");
      return;
    }
    busy.current = true;
    try {
      await onSave(clean, cls.trim(), school.split(/\s+/).filter(Boolean).join(" "));
      refocus(student.id);
    } catch (err) {
      setError(`Could not save: ${errorText(err)}`);
    } finally {
      busy.current = false;
    }
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void submit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onCancel();
      refocus(student.id);
    }
  };
  return (
    <div className="flex flex-col gap-1 rounded-paper border border-accent-strong bg-surface p-2" data-testid="student-edit-row">
      <label className="text-xs text-muted" htmlFor={`student-name-${student.id}`}>
        Name
      </label>
      <input
        autoFocus
        id={`student-name-${student.id}`}
        data-testid="student-edit-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={onKeyDown}
        className="rounded-paper border border-input bg-surface px-2 py-1 text-sm text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
      />
      <label className="text-xs text-muted" htmlFor={`student-class-${student.id}`}>
        Class
      </label>
      <input
        id={`student-class-${student.id}`}
        data-testid="student-edit-class"
        value={cls}
        onChange={(e) => setCls(e.target.value)}
        onKeyDown={onKeyDown}
        className="rounded-paper border border-input bg-surface px-2 py-1 text-sm text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
      />
      <label className="text-xs text-muted" htmlFor={`student-school-${student.id}`}>
        School
      </label>
      <SchoolCombobox
        id={`student-school-${student.id}`}
        testId="student-edit-school"
        value={school}
        onChange={setSchool}
        onKeyDown={onKeyDown}
        className="w-full rounded-paper border border-input bg-surface px-2 py-1 text-sm text-text focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
      />
      <div className="flex justify-end gap-2 pt-1 text-xs">
        <button
          type="button"
          data-testid="student-edit-cancel"
          onClick={() => {
            onCancel();
            refocus(student.id);
          }}
          className="rounded-button border border-border px-2 py-1 hover:bg-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
        >
          Cancel
        </button>
        <button
          type="button"
          data-testid="student-edit-save"
          onClick={() => void submit()}
          className="rounded-button bg-accent px-2 py-1 text-accent-text enabled:hover:bg-accent-hover enabled:active:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          Save
        </button>
      </div>
      <p className="text-xs text-muted">Enter saves · Esc cancels</p>
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

function refocus(studentId: string) {
  requestAnimationFrame(() =>
    document
      .querySelector<HTMLElement>(
        `[data-testid="student-row"][data-student-id="${CSS.escape(studentId)}"] [data-testid="student-edit-button"]`,
      )
      ?.focus(),
  );
}
