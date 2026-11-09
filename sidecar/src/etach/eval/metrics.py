"""Eval metrics (llm-design §8). Pure functions: no database, no files, no model calls.

Every metric keeps its counts (numerator / denominator, or edits / reference length), so the
harness can add them up over fixtures (a micro-average) and ``value`` gives the ratio. A ratio
over nothing is ``None`` and becomes an empty CSV cell.

Questions are matched by their **question key** (:func:`question_keys`): the printed number as
text (``"7"``), or ``"7#2"`` for the second question printed with number 7 in the same test
(the counting runs over the stored sections in order; listening sections are not stored).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from etach.domain.keys import sentence_forms
from etach.domain.normalize import value_norm

__all__ = [
    "AnswerCounts",
    "CalibrationCounts",
    "GradeKeyCounts",
    "KeyCounts",
    "NodeUsage",
    "Ratio",
    "ReadAnswer",
    "ReadKey",
    "SavedKey",
    "SimpleGroup",
    "SimpleQuestion",
    "SimpleSection",
    "StructureCounts",
    "TextCounts",
    "VerdictCounts",
    "answer_counts",
    "calibration_counts",
    "cer",
    "grade_key_counts",
    "key_counts",
    "levenshtein",
    "question_keys",
    "score_match",
    "structure_counts",
    "text_counts",
    "verdict_counts",
    "wilson_interval",
]


# --- CER -----------------------------------------------------------------------------------


def levenshtein(a: str, b: str) -> int:
    """Edit distance (insert, delete, substitute; each costs 1) over code points."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def cer(ref: str, hyp: str) -> float:
    """Character error rate: ``levenshtein(ref, hyp) / len(ref)``. An empty reference gives 0.0
    when the hypothesis is empty too, else 1.0."""
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


@dataclass
class TextCounts:
    """Summed edits over summed reference lengths (a corpus CER)."""

    edits: int = 0
    ref_len: int = 0

    def add(self, other: TextCounts) -> TextCounts:
        return TextCounts(self.edits + other.edits, self.ref_len + other.ref_len)

    @property
    def value(self) -> float | None:
        return None if self.ref_len == 0 else self.edits / self.ref_len


def text_counts(pairs: Iterable[tuple[str, str]]) -> TextCounts:
    out = TextCounts()
    for ref, hyp in pairs:
        out = out.add(TextCounts(levenshtein(ref, hyp), len(ref)))
    return out


# --- ratios and the Wilson interval --------------------------------------------------------


@dataclass
class Ratio:
    hits: int = 0
    total: int = 0

    def add(self, other: Ratio) -> Ratio:
        return Ratio(self.hits + other.hits, self.total + other.total)

    def count(self, ok: bool) -> None:
        self.total += 1
        self.hits += int(ok)

    @property
    def value(self) -> float | None:
        return None if self.total == 0 else self.hits / self.total


def wilson_interval(hits: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """The Wilson score interval (95 % by default) for ``hits / total``; (0, 1) when total = 0."""
    if total <= 0:
        return (0.0, 1.0)
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# --- the common shape for structure --------------------------------------------------------


@dataclass
class SimpleQuestion:
    printed_number: int
    answer_form: str  # choice | word | sentence | writing (step 22.5.3)
    stem: str | None = None
    options: list[str] | None = None
    cue: str | None = None
    page_no: int | None = None
    #: the canonical number (``Question.number``) the code gave; ``None`` on the expected side
    #: (:func:`canonical_numbers` works it out from the order, as ``renumber`` does).
    number: int | None = None


@dataclass
class SimpleGroup:
    stimulus: str | None = None
    questions: list[SimpleQuestion] = field(default_factory=list)


@dataclass
class SimpleSection:
    printed_title: str
    groups: list[SimpleGroup] = field(default_factory=list)
    skill: str | None = None
    graded: bool = True  # ``False`` for writing: numbered after the graded sections

    @property
    def questions(self) -> list[SimpleQuestion]:
        return [q for g in self.groups for q in g.questions]

    @classmethod
    def flat(
        cls, printed_title: str, questions: list[SimpleQuestion], skill: str | None = None
    ) -> SimpleSection:
        """One group, no stimulus."""
        return cls(printed_title, [SimpleGroup(None, list(questions))], skill)


def question_keys(printed_numbers: Iterable[int]) -> list[str]:
    """``"7"`` for the first question printed 7, ``"7#2"`` for the second, and so on."""
    seen: Counter[int] = Counter()
    out: list[str] = []
    for n in printed_numbers:
        seen[n] += 1
        out.append(str(n) if seen[n] == 1 else f"{n}#{seen[n]}")
    return out


def _keyed(sections: Sequence[SimpleSection]) -> dict[str, SimpleQuestion]:
    qs = [q for s in sections for q in s.questions]
    return dict(zip(question_keys(q.printed_number for q in qs), qs, strict=True))


_BLANK = re.compile(r"_{2,}|…{2,}|\.{4,}")
_UNDERLINE = re.compile(r"<u>(.*?)</u>", re.S)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def _spans(pattern: re.Pattern[str], text: str | None) -> Counter[str]:
    return Counter(value_norm(m) for m in pattern.findall(text or ""))


def _blanks(text: str | None) -> int:
    return len(_BLANK.findall(text or ""))


def _all_text(q: SimpleQuestion) -> str:
    return " ".join([q.stem or "", *(q.options or []), q.cue or ""])


@dataclass
class StructureCounts:
    """Structure accuracy, one :class:`Ratio` per dimension.

    - ``section_count`` / ``question_count``: partial credit, ``min(expected, read)`` hits over
      ``max(expected, read)`` (7 sections expected, 6 read = 6/7; 36 vs 34 questions = 34/36),
      summed over fixtures; a count of 0 on both sides adds nothing. Questions are counted by
      key, so a duplicate key is one question on both sides;
    - ``groups``: per expected section, the matched actual section has the same number of groups
      and a stimulus in the same groups (a section is matched by its first question's key);
    - ``skill``: per expected section with a ``skill``, the matched section has the same skill;
    - ``question_match``: expected questions that have a question with the same key;
    - over the matched questions: ``types`` (the same **answer form**, step 22.5.3; the name and
      the ``structure_types`` column are kept because history columns are only appended),
      ``option_count`` (same number of
      options; none = 0), ``option_text`` (every option text equal after ``value_norm``),
      ``blanks`` (the same number of ``____`` runs in stem + options + cue);
    - ``underline`` / ``bold``: the same ``<u>…</u>`` / ``**…**`` spans (after ``value_norm``),
      counted only over matched questions where either side has one;
    - ``text``: the corpus CER of stem, options and cue (a missing question = all deleted);
    - ``stimulus``: the corpus CER of the stimulus texts over the matched groups (a group is
      matched by its first question's key) where either side has a stimulus.

    ``overall`` is the mean of the dimension ratios that are defined.

    ``form_confusion`` counts the matched questions by ``"<expected form>→<read form>"`` (the
    confusion of forms; not a ratio, so not in ``overall`` or the history row).
    """

    section_count: Ratio = field(default_factory=Ratio)
    question_count: Ratio = field(default_factory=Ratio)
    question_match: Ratio = field(default_factory=Ratio)
    types: Ratio = field(default_factory=Ratio)
    option_count: Ratio = field(default_factory=Ratio)
    option_text: Ratio = field(default_factory=Ratio)
    blanks: Ratio = field(default_factory=Ratio)
    underline: Ratio = field(default_factory=Ratio)
    bold: Ratio = field(default_factory=Ratio)
    groups: Ratio = field(default_factory=Ratio)
    skill: Ratio = field(default_factory=Ratio)
    text: TextCounts = field(default_factory=TextCounts)
    stimulus: TextCounts = field(default_factory=TextCounts)
    form_confusion: dict[str, int] = field(default_factory=dict)

    DIMENSIONS = (
        "section_count",
        "question_count",
        "groups",
        "skill",
        "question_match",
        "types",
        "option_count",
        "option_text",
        "blanks",
        "underline",
        "bold",
    )

    def add(self, other: StructureCounts) -> StructureCounts:
        confusion = Counter(self.form_confusion)
        confusion.update(other.form_confusion)
        out = StructureCounts(
            text=self.text.add(other.text),
            stimulus=self.stimulus.add(other.stimulus),
            form_confusion=dict(sorted(confusion.items())),
        )
        for name in self.DIMENSIONS:
            setattr(out, name, getattr(self, name).add(getattr(other, name)))
        return out

    def ratios(self) -> dict[str, float | None]:
        return {name: getattr(self, name).value for name in self.DIMENSIONS}

    @property
    def form_accuracy(self) -> float | None:
        """Matched questions whose answer form is the expected one (= ``types``)."""
        return self.types.value

    @property
    def overall(self) -> float | None:
        values = [v for v in self.ratios().values() if v is not None]
        return None if not values else sum(values) / len(values)


# --- answer-number errors (step 22.5.7) ----------------------------------------------------

#: The largest CER at which two questions' texts (stem, options, cue) are taken as the same
#: question when aligning by content.
ALIGN_MAX_CER = 0.3


def canonical_numbers(sections: Sequence[SimpleSection]) -> list[int]:
    """The canonical number of each question, in stored order, by ``renumber``'s rule: 1..N over
    the graded sections in order, then the writing sections."""
    order = [i for i, s in enumerate(sections) if s.graded] + [
        i for i, s in enumerate(sections) if not s.graded
    ]
    first: dict[int, int] = {}
    nxt = 1
    for i in order:
        first[i] = nxt
        nxt += len(sections[i].questions)
    out: list[int] = []
    for i, s in enumerate(sections):
        out.extend(range(first[i], first[i] + len(s.questions)))
    return out


@dataclass
class NumberCounts:
    """Answer-number errors (step 22.5.7), over the questions aligned **by content**: each
    expected question, in order, is paired with the not-yet-paired read question whose text
    (stem, options and cue, after ``value_norm``) is closest, if its CER is at most
    :data:`ALIGN_MAX_CER` (questions with no text are not aligned). Over the pairs:

    - ``reading``: the read **printed** number (what the model returned; the code keeps it)
      differs from the paper's printed number: the model misread the number;
    - ``renumbering``: the read **canonical** number (``Question.number``, the code's numbering)
      differs from the expected canonical number (:func:`canonical_numbers` on the expected
      sections): the question sits on another number in the app, e.g. after a question left out
      or added before it, or a section numbered in another place.

    Both are error rates (``hits`` = errors); a pair may count in both.
    """

    reading: Ratio = field(default_factory=Ratio)
    renumbering: Ratio = field(default_factory=Ratio)

    def add(self, other: NumberCounts) -> NumberCounts:
        return NumberCounts(
            self.reading.add(other.reading), self.renumbering.add(other.renumbering)
        )


def number_counts(
    expected: Sequence[SimpleSection], actual: Sequence[SimpleSection]
) -> NumberCounts:
    exp = [q for s in expected for q in s.questions]
    exp_nos = canonical_numbers(expected)
    act = [q for s in actual for q in s.questions]
    act_nos = [
        q.number if q.number is not None else n
        for q, n in zip(act, canonical_numbers(actual), strict=True)
    ]
    act_text = [value_norm(_all_text(q)) for q in act]
    used: set[int] = set()
    out = NumberCounts()
    for e, e_no in zip(exp, exp_nos, strict=True):
        e_text = value_norm(_all_text(e))
        if not e_text:
            continue
        best: tuple[float, int] | None = None
        for j, a_text in enumerate(act_text):
            if j in used or not a_text:
                continue
            d = cer(e_text, a_text)
            if d <= ALIGN_MAX_CER and (best is None or d < best[0]):
                best = (d, j)
        if best is None:
            continue
        j = best[1]
        used.add(j)
        out.reading.count(act[j].printed_number != e.printed_number)
        out.renumbering.count(act_nos[j] != e_no)
    return out


def _count_ratio(expected: int, read: int) -> Ratio:
    """Partial credit for a count: ``min / max`` (an exact count = 1, none read = 0)."""
    return Ratio(min(expected, read), max(expected, read))


def structure_counts(
    expected: Sequence[SimpleSection], actual: Sequence[SimpleSection]
) -> StructureCounts:
    out = StructureCounts()
    out.section_count = _count_ratio(len(expected), len(actual))
    exp_q = _keyed(expected)
    act_q = _keyed(actual)
    out.question_count = _count_ratio(len(exp_q), len(act_q))
    text_pairs: list[tuple[str, str]] = []
    for key, e in exp_q.items():
        a = act_q.get(key)
        out.question_match.count(a is not None)
        if a is None:
            text_pairs.append((_all_text(e), ""))
            continue
        text_pairs.append((_all_text(e), _all_text(a)))
        out.types.count(e.answer_form == a.answer_form)
        pair = f"{e.answer_form}→{a.answer_form}"
        out.form_confusion[pair] = out.form_confusion.get(pair, 0) + 1
        e_opts = e.options or []
        a_opts = a.options or []
        out.option_count.count(len(e_opts) == len(a_opts))
        if e_opts or a_opts:
            out.option_text.count(
                [value_norm(o) for o in e_opts] == [value_norm(o) for o in a_opts]
            )
        e_text, a_text = _all_text(e), _all_text(a)
        out.blanks.count(_blanks(e_text) == _blanks(a_text))
        for ratio, pattern in ((out.underline, _UNDERLINE), (out.bold, _BOLD)):
            e_spans, a_spans = _spans(pattern, e_text), _spans(pattern, a_text)
            if e_spans or a_spans:
                ratio.count(e_spans == a_spans)
    out.text = text_counts(text_pairs)
    _group_counts(out, expected, actual)
    return out


def _group_counts(
    out: StructureCounts, expected: Sequence[SimpleSection], actual: Sequence[SimpleSection]
) -> None:
    """``groups``, ``skill`` and ``stimulus``: sections and groups are matched by the key of
    their first question (a section or group without questions by position)."""

    def where(sections: Sequence[SimpleSection]) -> dict[str, tuple[int, int]]:
        keys = iter(question_keys(q.printed_number for s in sections for q in s.questions))
        out: dict[str, tuple[int, int]] = {}
        for si, s in enumerate(sections):
            for gi, g in enumerate(s.groups):
                for _ in g.questions:
                    out[next(keys)] = (si, gi)
        return out

    exp_at = where(expected)
    act_at = where(actual)
    first = {pos: key for key, pos in reversed(list(exp_at.items()))}
    pairs: list[tuple[str, str]] = []
    for si, e in enumerate(expected):
        key = next((first[(si, gi)] for gi in range(len(e.groups)) if (si, gi) in first), None)
        if key is not None:
            a_si = act_at[key][0] if key in act_at else None
        else:
            a_si = si if si < len(actual) else None
        a = None if a_si is None else actual[a_si]
        out.groups.count(
            a is not None
            and [g.stimulus is not None for g in e.groups]
            == [g.stimulus is not None for g in a.groups]
        )
        if e.skill is not None:
            out.skill.count(a is not None and a.skill == e.skill)
        for gi, g in enumerate(e.groups):
            gkey = first.get((si, gi))
            ag = None
            if gkey is not None and gkey in act_at:
                asi, agi = act_at[gkey]
                ag = actual[asi].groups[agi]
            elif gkey is None and a is not None and gi < len(a.groups):
                ag = a.groups[gi]
            if ag is None:
                continue
            if g.stimulus is not None or ag.stimulus is not None:
                pairs.append((g.stimulus or "", ag.stimulus or ""))
    out.stimulus = text_counts(pairs)


# --- answers and calibration ---------------------------------------------------------------


@dataclass
class ReadAnswer:
    """What the app read for one question: ``value`` (None = blank) and the ``?`` flag."""

    value: str | None
    reading_unsure: bool = False


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    v = value_norm(value)
    return v or None


def _same_answer(expected: str | None, read: ReadAnswer | None) -> bool:
    got = None if read is None else _norm(read.value)
    return _norm(expected) == got


@dataclass
class AnswerCounts:
    """Answer-reading accuracy: an exact match after ``value_norm``; both blank counts."""

    accuracy: Ratio = field(default_factory=Ratio)

    def add(self, other: AnswerCounts) -> AnswerCounts:
        return AnswerCounts(self.accuracy.add(other.accuracy))


def answer_counts(
    expected: Mapping[str, str | None], read: Mapping[str, ReadAnswer]
) -> AnswerCounts:
    out = AnswerCounts()
    for key, value in expected.items():
        out.accuracy.count(_same_answer(value, read.get(key)))
    return out


@dataclass
class CalibrationCounts:
    """``wrong_flagged`` = wrong readings flagged ``?`` over all wrong readings (+ Wilson);
    ``correct_flagged`` = right readings flagged ``?`` over all right readings (the cost)."""

    wrong_flagged: Ratio = field(default_factory=Ratio)
    correct_flagged: Ratio = field(default_factory=Ratio)

    def add(self, other: CalibrationCounts) -> CalibrationCounts:
        return CalibrationCounts(
            self.wrong_flagged.add(other.wrong_flagged),
            self.correct_flagged.add(other.correct_flagged),
        )

    @property
    def interval(self) -> tuple[float, float] | None:
        r = self.wrong_flagged
        return None if r.total == 0 else wilson_interval(r.hits, r.total)


def calibration_counts(
    expected: Mapping[str, str | None], read: Mapping[str, ReadAnswer]
) -> CalibrationCounts:
    """A question with no reading at all counts as wrong and not flagged."""
    out = CalibrationCounts()
    for key, value in expected.items():
        got = read.get(key)
        flagged = bool(got is not None and got.reading_unsure)
        if _same_answer(value, got):
            out.correct_flagged.count(flagged)
        else:
            out.wrong_flagged.count(flagged)
    return out


# --- keys ----------------------------------------------------------------------------------


@dataclass
class ReadKey:
    accepted: list[str]
    from_key_photo: bool = False


@dataclass
class KeyCounts:
    """``accuracy``: expected key entries whose saved accepted set equals it (after
    ``value_norm``). ``mapping``: over key-photo runs only, expected key entries that got a
    ``from_key_photo`` key on the right question with the right value."""

    accuracy: Ratio = field(default_factory=Ratio)
    mapping: Ratio = field(default_factory=Ratio)

    def add(self, other: KeyCounts) -> KeyCounts:
        return KeyCounts(self.accuracy.add(other.accuracy), self.mapping.add(other.mapping))


def _key_set(values: Iterable[str]) -> set[str]:
    return {v for v in (value_norm(x) for x in values) if v}


_SENTENCE_WORDS = 4  # the metrics see no question type: a key this long is a sentence


def _same_key(got: Sequence[str], want: Sequence[str]) -> bool:
    """The saved key equals the expected one (``value_norm`` sets), where the expected key also
    gets the sentence forms every key write adds to a rewrite/combine key (data-model §2.4
    v1.15, step 22.3.4), so results stay comparable with the rows before the forms. The given
    opening words are not in the fixture's key; they are taken as the part of the expected
    sentence before each saved answer that ends it."""
    if _key_set(got) == _key_set(want):
        return True
    words = want[0].split() if want else []
    if len(words) < _SENTENCE_WORDS or not got:  # forms are for sentence keys only
        return False
    given = [" ".join(words[: len(words) - len(x.split())]) for x in got]
    forms = sentence_forms(want[0], [g for g in given if g])
    return len(forms) > 1 and _key_set(got) == _key_set([*forms, *want[1:]])


def key_counts(
    expected: Mapping[str, Sequence[str]] | None,
    read: Mapping[str, ReadKey],
    *,
    has_key_photo: bool,
) -> KeyCounts:
    out = KeyCounts()
    if not expected:
        return out
    for qkey, accepted in expected.items():
        got = read.get(qkey)
        same = got is not None and _same_key(got.accepted, accepted)
        out.accuracy.count(same)
        if has_key_photo:
            out.mapping.count(same and got is not None and got.from_key_photo)
    return out


# --- the grade graph (M2) --------------------------------------------------------------------


@dataclass
class SavedKey:
    """A key row the grade graph saved: its accepted answers and its status."""

    accepted: list[str]
    status: str


@dataclass
class GradeKeyCounts:
    """The AI key (M2), over the questions with an expected key; the same equivalence as
    :func:`key_counts` (the accepted sets are equal after ``value_norm``).

    - ``fast``: the key ``ai_key_fast`` made (its accepted answers; ``verify_key`` never changes
      them) equals the expected key;
    - ``verified``: the key after ``verify_gate`` / ``verify_key`` equals the expected key **and**
      is usable: a key ``verify_key`` left ``ai_uncertain`` grades ``?`` (B.5 row 3), so it
      counts as not matching;
    - ``uncertain``: how many of those keys ended ``ai_uncertain``.

    A question with no key row (``ai_key_fast`` failed) counts as not matching in both."""

    fast: Ratio = field(default_factory=Ratio)
    verified: Ratio = field(default_factory=Ratio)
    uncertain: int = 0

    def add(self, other: GradeKeyCounts) -> GradeKeyCounts:
        return GradeKeyCounts(
            self.fast.add(other.fast),
            self.verified.add(other.verified),
            self.uncertain + other.uncertain,
        )


def grade_key_counts(
    expected: Mapping[str, Sequence[str]] | None, saved: Mapping[str, SavedKey]
) -> GradeKeyCounts:
    out = GradeKeyCounts()
    for qkey, accepted in (expected or {}).items():
        got = saved.get(qkey)
        same = got is not None and _same_key(got.accepted, accepted)
        unsure = got is not None and got.status == "ai_uncertain"
        out.fast.count(same)
        out.verified.count(same and not unsure)
        out.uncertain += int(unsure)
    return out


@dataclass
class VerdictCounts:
    """The grade graph's verdicts against the truth (M2).

    - ``verdict``: over the answered questions (a non-blank expected answer) that have a truth,
      the graph's verdict equals it; a ``?`` (uncertain) or ungraded verdict is a miss;
    - ``judge``: the same, over the questions the graph sent to ``judge_rewrites``;
    - ``uncertain``: the counted questions the graph left ``?`` or ungraded;
    - ``no_truth``: answered questions with no truth (no expected key, or a free-text answer
      the teacher has not given a verdict for yet); they are not counted;
    - ``score``: per fixture with a complete truth, the graph's total equals the truth's total
      and the graph left nothing ``?``."""

    verdict: Ratio = field(default_factory=Ratio)
    judge: Ratio = field(default_factory=Ratio)
    uncertain: int = 0
    no_truth: int = 0
    score: Ratio = field(default_factory=Ratio)

    def add(self, other: VerdictCounts) -> VerdictCounts:
        return VerdictCounts(
            self.verdict.add(other.verdict),
            self.judge.add(other.judge),
            self.uncertain + other.uncertain,
            self.no_truth + other.no_truth,
            self.score.add(other.score),
        )


_SURE = ("correct", "incorrect")


def verdict_counts(
    truth: Mapping[str, str | None],
    graph: Mapping[str, str],
    *,
    answered: Iterable[str],
    judged: Iterable[str] = (),
) -> VerdictCounts:
    """``truth`` / ``graph``: question key → verdict (truth None = unknown); ``answered``: the
    question keys with a non-blank expected answer; ``judged``: those sent to the judge."""
    out = VerdictCounts()
    to_judge = set(judged)
    for qkey in answered:
        want = truth.get(qkey)
        if want is None:
            out.no_truth += 1
            continue
        got = graph.get(qkey, "ungraded")
        ok = got == want
        out.verdict.count(ok)
        if got not in _SURE:
            out.uncertain += 1
        if qkey in to_judge:
            out.judge.count(ok)
    return out


def score_match(
    truth_total: float | None, graph_total: float | None, *, graph_unsure: bool
) -> Ratio:
    """One fixture's exact score match: nothing counted without a truth total; a match needs
    the same total and no ``?`` left by the graph."""
    if truth_total is None:
        return Ratio()
    ok = graph_total is not None and not graph_unsure and abs(graph_total - truth_total) < 1e-6
    return Ratio(int(ok), 1)


# --- usage per node ------------------------------------------------------------------------


@dataclass
class NodeUsage:
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    ms: int = 0

    def add(self, other: NodeUsage) -> NodeUsage:
        return NodeUsage(
            self.tokens_in + other.tokens_in,
            self.tokens_out + other.tokens_out,
            self.calls + other.calls,
            self.ms + other.ms,
        )
