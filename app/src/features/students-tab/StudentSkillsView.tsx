/**
 * "Skills — {student}" in the main panel (step 22.5.5 checklist (c), R22.5.5.11; teacher,
 * 2026-10-25). Clicking a student in the Students tab opens it in the conversation's place, as a
 * test opened from the Tests tab does; like that test it has no Back button (D1): the sidebar is
 * the way out (a thread, another student, another sidebar tab, or Esc).
 *
 * `GET /students/{id}` gives the skills basics first (D11b): a table of level, skill (the full
 * name, wrapping), label (D11) and the share right on each paper in date-taken order, each share
 * showing its date on hover or focus. Weak skills above the lowest weak level wait behind
 * "Later, after the basics (N)" (D11e). The student's threads follow, each opening its thread
 * (they used to open under the student's row in the sidebar).
 */
import { useEffect, useState, type ReactNode } from "react";
import type { ApiClient, Schemas } from "@/api/client";
import { HoverTip } from "@/components/HoverTip";
import { LaterAfterBasics } from "@/components/LaterAfterBasics";
import { errorText } from "@/lib/errors";
import { showDate, skillLabel } from "@/lib/skills";

type StudentDetail = Schemas["StudentDetail"];
type StudentSkill = Schemas["StudentSkill"];

export interface StudentSkillsViewProps {
  api: ApiClient;
  studentId: string;
  /** The name from the sidebar row, shown until the student loads. */
  name: string;
  /** Changes when the student should reload (run events, edits). */
  refreshKey?: number;
  onOpenThread: (threadId: string) => void;
}

/** The view's title: "Skills — Lan". */
export const skillsTitle = (name: string) => `Skills — ${name}`;

export function StudentSkillsView({ api, studentId, name, refreshKey = 0, onOpenThread }: StudentSkillsViewProps) {
  const [detail, setDetail] = useState<{ id: string; data: StudentDetail } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .get("/students/{id}", { path: { id: studentId }, signal: ctrl.signal })
      .then((d) => {
        setDetail({ id: studentId, data: d });
        setError(null);
      })
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [api, studentId, refreshKey]);

  const data = detail?.id === studentId ? detail.data : null;
  const shownName = data?.student.full_name ?? name;
  const className = data?.student.class_name;
  const skills = data?.skills ?? [];
  const now = skills.filter((s) => !s.held_back);
  const later = skills.filter((s) => s.held_back);

  return (
    <main
      data-testid="student-view"
      data-student-id={studentId}
      aria-labelledby={`student-view-title-${studentId}`}
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <header className="border-b border-border bg-panel px-4 py-2">
        <h2
          id={`student-view-title-${studentId}`}
          tabIndex={-1}
          data-testid="student-view-title"
          className="font-serif text-base text-text focus:outline-none"
        >
          {skillsTitle(shownName)}
        </h2>
        <p className="text-xs text-muted">{className ? `Class ${className}` : data ? "No class" : " "}</p>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="flex max-w-4xl flex-col gap-6">
          {error ? (
            <p role="alert" className="text-sm text-danger">
              Could not load the skills: {error}
            </p>
          ) : !data ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : skills.length === 0 ? (
            <p data-testid="student-skills-empty" className="text-sm text-muted">
              No skills yet. They appear once one of this student's papers is graded.
            </p>
          ) : (
            <section data-testid="student-skills" className="flex flex-col gap-2">
              <SkillTable
                skills={now}
                caption={
                  <>
                    Basics first. Papers shows the share right on each paper, oldest first; hover or focus a share for
                    the date the paper was taken.
                  </>
                }
              />
              <LaterAfterBasics count={later.length} testId="skills-later">
                <SkillTable skills={later} caption={<span className="sr-only">Later, after the basics</span>} />
              </LaterAfterBasics>
            </section>
          )}
          {data && (
            <section data-testid="student-threads" aria-labelledby={`student-threads-title-${studentId}`}>
              <h3 id={`student-threads-title-${studentId}`} className="pb-1 text-sm font-semibold text-text">
                Threads
              </h3>
              {data.threads.length === 0 ? (
                <p className="text-sm text-muted">No threads.</p>
              ) : (
                <ul className="flex flex-col gap-0.5">
                  {data.threads.map((t) => (
                    <li key={t.id}>
                      <button
                        type="button"
                        data-testid="student-thread"
                        data-thread-id={t.id}
                        onClick={() => onOpenThread(t.id)}
                        className="rounded-button px-2 py-1 text-left text-sm text-text underline-offset-4 hover:bg-hover hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      >
                        {t.shown_title}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

/** Label colours from the tokens (step 22.5.5b): brick words for the weak labels; "improved" on a
 *  green badge and "inconsistent" on an ochre one, both with dark text (PRD §10.1 v8.13). The
 *  label's words always say it, so colour never carries the meaning alone. */
const BADGE = "inline-block rounded-full px-1.5 text-text print:bg-transparent";
const LABEL_TONE: Partial<Record<StudentSkill["label"], string>> = {
  slipped: "text-danger",
  consistently_weak: "text-danger",
  inconsistent: BADGE + " bg-unsure",
  improved: BADGE + " bg-correct",
};

const cell = "px-3 py-1.5 align-top";

function SkillTable({ skills, caption }: { skills: StudentSkill[]; caption: ReactNode }) {
  if (!skills.length) return null;
  return (
    // No scrolling wrapper: it would clip the share tips; the skill names wrap instead. Fixed
    // column widths keep the "Later" table lined up with the first.
    <table className="w-full table-fixed border-collapse text-left text-sm" data-testid="student-skills-table">
        <caption className="pb-2 text-left text-sm text-muted">{caption}</caption>
        <thead>
          <tr className="border-b border-border text-xs text-muted">
            <th scope="col" className={cell + " w-16 font-medium"}>
              Level
            </th>
            <th scope="col" className={cell + " font-medium"}>
              Skill
            </th>
            <th scope="col" className={cell + " w-48 font-medium"}>
              Label
            </th>
            <th scope="col" className={cell + " w-56 font-medium"}>
              Papers
            </th>
          </tr>
        </thead>
        <tbody>
          {skills.map((s) => (
            <tr
              key={s.skill_tag}
              data-testid="student-skill"
              data-skill={s.skill_tag}
              data-label={s.label}
              className="border-b border-border last:border-b-0"
            >
              <td className={cell + " text-muted"} data-testid="student-skill-level">
                {s.level ?? (
                  <>
                    <span aria-hidden="true">–</span>
                    <span className="sr-only">No level</span>
                  </>
                )}
              </td>
              <th scope="row" className={cell + " font-normal break-words text-text"} data-testid="student-skill-name">
                {s.skill_name || s.skill_tag}
              </th>
              <td className={cell} data-testid="student-skill-label">
                <span className={LABEL_TONE[s.label] ?? "text-muted"}>{skillLabel(s.label)}</span>
              </td>
              <td className={cell} data-testid="student-skill-papers">
                <PaperShares skill={s} />
              </td>
            </tr>
          ))}
        </tbody>
    </table>
  );
}

/** "25% · 40% · 30%": each share a focusable label whose date shows on hover or focus. */
function PaperShares({ skill }: { skill: StudentSkill }) {
  if (!skill.papers.length) return <span className="text-muted">No papers yet</span>;
  return (
    <span className="flex flex-wrap items-baseline gap-x-1 gap-y-0.5">
      {skill.papers.map((p, i) => (
        <span key={p.attempt_id} className="inline-flex items-baseline gap-x-1">
          {i > 0 && (
            <span aria-hidden="true" className="text-muted">
              ·
            </span>
          )}
          <HoverTip
            testId="student-skill-share"
            tipTestId="student-skill-date"
            width="w-64"
            alignEnd={i === skill.papers.length - 1 && skill.papers.length > 1}
            className="text-text tabular-nums"
            tip={
              <span>
                Taken {showDate(p.taken_on)}: {Math.round(p.share * 100)}% right, {p.counted === 1 ? "1 question" : `${p.counted} questions`}
              </span>
            }
          >
            {Math.round(p.share * 100)}%
          </HoverTip>
        </span>
      ))}
    </span>
  );
}
