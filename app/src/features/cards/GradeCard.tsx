/**
 * The grade card (PRD §10.1, step 19): the `grade_card` message of a grade run, body
 * `{run_id, test_id, attempt_id, score_earned, score_possible, uncertain_points}`. The details
 * come from `GET /attempts/{id}/report` (the latest report), refetched when `refreshKey` changes
 * (the thread's run events). Each row has the answers-panel override editor: `PUT
 * /attempts/{id}/answers/{qid}` re-grades on the sidecar; the next `run.done` brings a new card.
 *
 * Only the thread's latest grade card for an attempt is shown in full (`latest`); earlier ones
 * keep their stored score as one line.
 */
import { useCallback, useEffect, useId, useState } from "react";
import { type ApiClient, type Schemas } from "@/api/client";
import { AnswerRow } from "@/features/panels/AnswersPanel";
import type { PanelView } from "@/features/panels/panelView";
import { fmtPoints, numbersOf, ReportSummary, ScoreLine, useAttemptReport } from "@/features/panels/ReportPanel";
import { errorText } from "@/lib/errors";

export interface GradeCardBody {
  run_id?: string;
  test_id?: string;
  attempt_id?: string | null;
  score_earned?: number | null;
  score_possible?: number | null;
  uncertain_points?: number | null;
}

export interface GradeCardProps {
  api: ApiClient;
  body: GradeCardBody;
  latest: boolean;
  refreshKey?: number;
  onOpenPanel?: (view: PanelView) => void;
}

export function GradeCard({ api, body, latest, refreshKey = 0, onOpenPanel }: GradeCardProps) {
  const attemptId = body.attempt_id ?? null;
  if (!latest || !attemptId || !body.test_id) {
    return (
      <div data-testid="grade-card-old" className="rounded-paper border border-border bg-surface px-4 py-2 text-sm text-muted">
        Graded {fmtPoints(body.score_earned)}/{fmtPoints(body.score_possible)}
      </div>
    );
  }
  return (
    <GradeCardFull api={api} attemptId={attemptId} testId={body.test_id} refreshKey={refreshKey} onOpenPanel={onOpenPanel} />
  );
}

function GradeCardFull({
  api,
  attemptId,
  testId,
  refreshKey,
  onOpenPanel,
}: {
  api: ApiClient;
  attemptId: string;
  testId: string;
  refreshKey: number;
  onOpenPanel?: (view: PanelView) => void;
}) {
  const [seq, setSeq] = useState(0);
  const { report, error } = useAttemptReport(api, attemptId, refreshKey * 1000 + seq);
  const [answers, setAnswers] = useState<Schemas["Answer"][]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const ids = useId();

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .get("/attempts/{id}", { path: { id: attemptId }, signal: ctrl.signal })
      .then((d) => setAnswers(d.answers))
      .catch(() => {});
    return () => ctrl.abort();
  }, [api, attemptId, refreshKey, seq]);

  const save = useCallback(
    async (questionId: string, value: string) => {
      setSaveError(null);
      try {
        await api.put("/attempts/{id}/answers/{question_id}", {
          path: { id: attemptId, question_id: questionId },
          body: { value },
        });
        setEditing(null);
        setSeq((n) => n + 1);
      } catch (err) {
        setSaveError(errorText(err));
      }
    },
    [api, attemptId],
  );

  if (!report) {
    return (
      <div data-testid="grade-card" className="rounded-paper border border-border bg-surface p-4 text-sm text-muted">
        {error ?? "Loading the report…"}
      </div>
    );
  }
  const numbers = numbersOf(report);
  const byQ = new Map(answers.map((a) => [a.question_id, a]));
  const rows = [...report.verdicts].sort((a, b) => a.printed_number - b.printed_number);

  return (
    <div
      data-testid="grade-card"
      data-attempt-id={attemptId}
      data-run-id={report.report.run_id}
      className="flex flex-col gap-3 rounded-paper border border-border bg-surface p-4 text-sm text-text"
    >
      <div className="flex items-center gap-3">
        <span className="mark-label font-semibold">Graded ✓</span>
        <ScoreLine report={report} />
        <div className="ml-auto flex gap-2">
          <button
            type="button"
            data-testid="card-open-report"
            aria-describedby={`${ids}-report`}
            title="Opens the grade report beside the student's photos"
            onClick={() => onOpenPanel?.({ kind: "report", attemptId, testId })}
            className="rounded-button border border-border px-3 py-1 hover:bg-hover"
          >
            Report
          </button>
          <button
            type="button"
            data-testid="card-open-keys"
            aria-describedby={`${ids}-keys`}
            title="Opens the key beside the test's photos"
            onClick={() => onOpenPanel?.({ kind: "keys", testId })}
            className="rounded-button border border-border px-3 py-1 hover:bg-hover"
          >
            Key
          </button>
          <span id={`${ids}-report`} hidden>
            Opens the grade report beside the student&apos;s photos
          </span>
          <span id={`${ids}-keys`} hidden>
            Opens the key beside the test&apos;s photos
          </span>
        </div>
      </div>
      <ReportSummary report={report} numbers={numbers} />
      <details data-testid="grade-rows">
        <summary className="cursor-pointer text-muted">Student answers ({rows.length})</summary>
        {saveError && <p role="alert" className="text-danger">{saveError}</p>}
        <div className="flex flex-col gap-1 pt-2">
          {rows.map((v) => {
            const answer: Schemas["Answer"] | undefined = byQ.get(v.question_id);
            const shown = answer
              ? { ...answer, verdict: v.verdict === "ungraded" ? answer.verdict : v.verdict }
              : null;
            return shown ? (
              <AnswerRow
                key={v.question_id}
                answer={shown}
                number={v.printed_number}
                editing={editing === v.question_id}
                onEdit={() => setEditing(v.question_id)}
                onCancel={() => setEditing(null)}
                onSave={(value) => void save(v.question_id, value)}
              />
            ) : null;
          })}
        </div>
      </details>
    </div>
  );
}
