/**
 * The grade report (PRD §10.1, step 19): `GET /attempts/{id}/report`. `ReportSummary` (score,
 * unsure points, teacher questions, weak points, careless notes) is shared by the grade card in
 * the conversation and this printable panel. Print hides the chrome (`no-print`) and marks the
 * `?` rows (`data-mark="?"`, `styles/print.css`).
 */
import { useEffect, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { errorText } from "@/lib/errors";
import { SaveAsWord } from "@/components/SaveAsWord";
import { LaterAfterBasics } from "@/components/LaterAfterBasics";
import { skillLabel } from "@/lib/skills";
import { MarkBadge, UNSURE_GRADE } from "./AnswersPanel";

export type AttemptReport = Schemas["AttemptReport"];
type Verdict = Schemas["ReportVerdict"];

/** The verdict cell's text: the mark, or "AI unsure grade" for an uncertain grade (answer 2). */
export function verdictLabel(v: Pick<Verdict, "verdict">): string {
  return v.verdict === "uncertain" ? UNSURE_GRADE : verdictMark(v);
}

/** ✓ / ✗ / ? / –: the row's `data-mark` (print styles and tests); never shown as text. */
export function verdictMark(v: Pick<Verdict, "verdict">): string {
  switch (v.verdict) {
    case "correct":
      return "✓";
    case "incorrect":
      return "✗";
    case "uncertain":
      return "?";
    default:
      return "–";
  }
}

/** `7.5` / `9` / `0.25`: up to two decimals, no trailing zeros. */
export function fmtPoints(n: number | null | undefined): string {
  if (n === null || n === undefined) return "–";
  return String(Math.round(n * 100) / 100);
}

export function useAttemptReport(api: ApiClient, attemptId: string, refreshKey = 0) {
  const [report, setReport] = useState<AttemptReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    api
      .get("/attempts/{id}/report", { path: { id: attemptId }, signal: ctrl.signal })
      .then((r) => {
        setReport(r);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!ctrl.signal.aborted) setError(errorText(err));
      });
    return () => ctrl.abort();
  }, [api, attemptId, refreshKey]);
  return { report, error };
}

export function ScoreLine({ report }: { report: AttemptReport }) {
  const a = report.attempt;
  const unsure = report.report.uncertain_points;
  return (
    <div className="flex flex-wrap items-baseline gap-3">
      <span data-testid="grade-score" className="font-serif text-2xl text-text">
        {fmtPoints(a.score_earned)}/{fmtPoints(a.score_possible)}
      </span>
      <span data-testid="grade-unsure" data-points={unsure} className={unsure ? "mark-label font-semibold" : "text-muted"}>
        {fmtPoints(unsure)} unsure
      </span>
    </div>
  );
}

/** A weak point whose code the skill list does not have (the sidecar names every known one). */
export const OTHER_SKILL = "Other skill";

type Explanation = AttemptReport["explanations"][number];
type WeakPoint = AttemptReport["report"]["weak_points"][number];

/**
 * Step 22.5.5b (D11c, D11e): each weak point with its level and its label ("This paper only"
 * while there is not enough evidence), in the sidecar's order (basics first).
 */
function WeakPointList({ list }: { list: WeakPoint[] }) {
  if (!list.length) return null;
  return (
    <ul className="list-disc pl-5">
      {list.map((w) => {
        const tags = [w.level, skillLabel(w.label)?.toLowerCase()].filter(Boolean).join(", ");
        return (
          <li key={w.skill_tag} data-testid="weak-point" data-skill={w.skill_tag} data-label={w.label ?? undefined}>
            <span className="font-medium">{w.skill_name || OTHER_SKILL}</span>
            {tags && (
              <span className="text-muted" data-testid="weak-point-tags">
                {" "}
                ({tags})
              </span>
            )}
            : {w.wrong}/{w.seen} wrong
            {w.note_vi && <span> — {w.note_vi}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** Explanations in the paper's order: printed number, then the wrong answer (step 22.4.6). */
export function inPrintedOrder(list: Explanation[], numbers: Map<string, number>): Explanation[] {
  const n = (e: Explanation) => numbers.get(e.question_id) ?? Number.MAX_SAFE_INTEGER;
  return [...list].sort((a, b) => n(a) - n(b) || cmp(a.wrong_answer_norm, b.wrong_answer_norm));
}

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Teacher questions, weak points (by skill name; the internal code is only `data-skill`) and
 * careless notes, then the explanations. The sidecar already replaced taxonomy codes in the AI text.
 */
export function ReportSummary({ report, numbers }: { report: AttemptReport; numbers: Map<string, number> }) {
  const r = report.report;
  return (
    <div className="flex flex-col gap-3">
      {r.summary_vi && <p data-testid="grade-summary">{r.summary_vi}</p>}
      {r.teacher_questions.length > 0 && (
        <section>
          <h3 className="font-semibold">Questions for the student</h3>
          <ol className="list-decimal pl-5">
            {r.teacher_questions.map((q, i) => (
              <li key={i} data-testid="teacher-question">
                {q.question_vi}
                {q.what_answers_mean_vi && <span className="text-muted"> — {q.what_answers_mean_vi}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
      {r.weak_points.length > 0 && (
        <section>
          <h3 className="font-semibold">Weak points</h3>
          <WeakPointList list={r.weak_points.filter((w) => !w.held_back)} />
          <LaterAfterBasics count={r.weak_points.filter((w) => w.held_back).length} testId="weak-later">
            <WeakPointList list={r.weak_points.filter((w) => w.held_back)} />
          </LaterAfterBasics>
        </section>
      )}
      {r.careless_notes.length > 0 && (
        <section>
          <h3 className="font-semibold">Careless mistakes</h3>
          <ul className="list-disc pl-5">
            {r.careless_notes.map((n, i) => (
              <li key={i} data-testid="careless-note">
                {n}
              </li>
            ))}
          </ul>
        </section>
      )}
      {report.explanations.length > 0 && (
        <section>
          <h3 className="font-semibold">Explanations</h3>
          <ul className="flex flex-col gap-1">
            {inPrintedOrder(report.explanations, numbers).map((e) => (
              <li key={`${e.question_id}|${e.wrong_answer_norm}`} data-testid="explanation" className="print-break-inside-avoid">
                <span className="text-muted">{numbers.get(e.question_id) ?? "?"}.</span> {e.text_vi}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function numbersOf(report: AttemptReport): Map<string, number> {
  return new Map(report.verdicts.map((v) => [v.question_id, v.printed_number]));
}

export interface ReportPanelProps {
  api: ApiClient;
  attemptId: string;
  refreshKey?: number;
  print?: () => void;
}

/** The printable report: every graded row by printed number, `?` rows marked. */
export function ReportPanel({ api, attemptId, refreshKey = 0, print }: ReportPanelProps) {
  const { report, error } = useAttemptReport(api, attemptId, refreshKey);
  if (!report) {
    return error ? <p role="alert" className="text-danger">{error}</p> : <p className="text-muted">Loading…</p>;
  }
  const rows = [...report.verdicts].sort((a, b) => a.printed_number - b.printed_number);
  return (
    <div data-testid="report-panel" className="flex flex-col gap-4">
      <div className="no-print flex flex-wrap items-center gap-2" data-testid="report-toolbar">
        <button
          type="button"
          data-testid="report-print"
          onClick={() => (print ?? (() => window.print()))()}
          className="main-label rounded-button border border-border px-3 py-1 hover:bg-hover"
        >
          Print
        </button>
        <SaveAsWord
          what="grade report"
          testId="report-save-docx"
          save={() => api.post("/attempts/{id}/report/export", { path: { id: attemptId } })}
        />
      </div>
      <ScoreLine report={report} />
      <table className="w-full border-collapse" data-testid="report-rows">
        <tbody>
          {rows.map((v) => (
            <tr
              key={v.question_id}
              data-testid="report-row"
              data-mark={verdictMark(v)}
              className={"report-row border-b border-border " + (v.verdict === "uncertain" ? "bg-unsure/15" : "")}
            >
              <td className="w-10 py-0.5 text-right text-muted">{v.printed_number}.</td>
              <td className="px-3 py-0.5">{v.value ?? "(blank)"}</td>
              <td
                className={
                  v.verdict === "uncertain"
                    ? "whitespace-nowrap px-2 text-center text-xs font-semibold mark-label"
                    : "w-8 text-center"
                }
                data-testid="report-mark"
              >
                <MarkBadge mark={verdictLabel(v)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ReportSummary report={report} numbers={numbersOf(report)} />
    </div>
  );
}
