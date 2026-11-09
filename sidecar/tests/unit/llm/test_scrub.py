"""``etach scrub`` and ``etach scrub --check`` (R4.8, S5)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from etach.cli import main
from etach.llm.scrub import (
    CLASS_PLACEHOLDER,
    STUDENT_PLACEHOLDER,
    Targets,
    check_dir,
    field_values,
    find_spans,
    fold,
    scrub_cassette,
    scrub_dir,
)

CASSETTES = Path(__file__).resolve().parents[2] / "cassettes"
NAME = "Nguyễn Văn Bình"
CLASS = "8A3"


def byte_tokens(text: str, size: int = 2) -> list[dict[str, Any]]:
    """Logprob entries that split the UTF-8 bytes every ``size`` bytes (mid-character too)."""
    raw = text.encode("utf-8")
    out = []
    for n, i in enumerate(range(0, len(raw), size)):
        piece = raw[i : i + size]
        out.append(
            {
                "token": piece.decode("utf-8", "replace"),
                "logprob": -0.1 - (n % 7) / 10,
                "bytes": list(piece),
                "top_logprobs": [{"token": "x", "logprob": -3.0, "bytes": [120]}],
            }
        )
    return out


def cassette(task: str, response: Any, thinking: str = "") -> dict[str, Any]:
    text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    return {
        "task": task,
        "match_key": f"{task}:abc",
        "response_text": text,
        "thinking_text": thinking,
        "logprobs": byte_tokens(thinking) + byte_tokens(text),
        "status": "complete",
        "meta": {
            "model": "m",
            "prompt_hash": "h",
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "schema": "X",
        },
    }


def read_answers() -> dict[str, Any]:
    return cassette(
        "read_answers_page",
        {
            "student_name": NAME,
            "class_name": CLASS,
            "answers": [{"question_id": "q-1", "value": "B"}],
            "nested": {"student_name": NAME, "class_name": None},
        },
        thinking=f"The header says {NAME}, class {CLASS}. So student_name is {NAME}.",
    )


def transcribe() -> dict[str, Any]:
    return cassette(
        "transcribe_page",
        {
            "header_text": f"Họ và tên: {NAME}   Lớp: {CLASS}\nĐỀ CUỐI KÌ I LỚP 8 (K)",
            "sections": [],
        },
    )


def write(folder: Path, data: dict[str, Any], name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def assert_consistent(data: dict[str, Any]) -> None:
    """The logprob bytes join exactly to thinking + response."""
    stream = b"".join(bytes(e["bytes"]) for e in data["logprobs"])
    assert stream == (data["thinking_text"] + data["response_text"]).encode("utf-8")


def all_text(data: dict[str, Any]) -> str:
    tokens = b"".join(bytes(e["bytes"]) for e in data["logprobs"] or []).decode("utf-8", "replace")
    return data["response_text"] + data["thinking_text"] + tokens


def test_r4_8_scrub_replaces_values_and_check_passes_after(tmp_path: Path) -> None:
    path = write(tmp_path / "scenario", read_answers(), "001-read_answers_page.json")
    assert {v.value for v in check_dir(tmp_path)} == {NAME, CLASS}
    assert main(["scrub", "--check", str(tmp_path)]) == 1

    assert main(["scrub", str(tmp_path)]) == 0
    data = load(path)
    parsed = json.loads(data["response_text"])
    assert parsed["student_name"] == STUDENT_PLACEHOLDER
    assert parsed["class_name"] == CLASS_PLACEHOLDER
    assert parsed["nested"] == {"student_name": STUDENT_PLACEHOLDER, "class_name": None}
    assert parsed["answers"] == [{"question_id": "q-1", "value": "B"}]
    assert NAME not in all_text(data) and CLASS not in all_text(data)
    assert data["thinking_text"].count(STUDENT_PLACEHOLDER) == 2
    assert_consistent(data)
    assert check_dir(tmp_path) == []
    assert main(["scrub", "--check", str(tmp_path)]) == 0


def test_name_in_a_header_of_another_cassette_is_scrubbed(tmp_path: Path) -> None:
    scenario = tmp_path / "s1"
    header = write(scenario / "pages", transcribe(), "001-transcribe_page.json")
    answers = write(scenario, read_answers(), "002-read_answers_page.json")
    assert check_dir(tmp_path) != []  # only the read_answers fields are visible to the check
    assert sorted(scrub_dir(tmp_path)) == sorted([header, answers])
    for path in (header, answers):
        data = load(path)
        assert NAME not in all_text(data) and CLASS not in all_text(data)
        assert_consistent(data)
    header_text = json.loads(load(header)["response_text"])["header_text"]
    assert header_text.startswith(f"Họ và tên: {STUDENT_PLACEHOLDER}   Lớp: {CLASS_PLACEHOLDER}\n")
    assert "ĐỀ CUỐI KÌ I LỚP 8 (K)" in header_text  # printed test text stays


def test_accent_stripped_and_case_variants_are_scrubbed(tmp_path: Path) -> None:
    write(tmp_path, read_answers(), "001-read_answers_page.json")
    variant = cassette(
        "transcribe_page",
        {"header_text": "Name: NGUYEN VAN BINH, class 8a3", "sections": []},
        thinking="The student wrote nguyen van binh.",
    )
    path = write(tmp_path, variant, "002-transcribe_page.json")
    scrub_dir(tmp_path)
    data = load(path)
    header_text = json.loads(data["response_text"])["header_text"]
    assert header_text == f"Name: {STUDENT_PLACEHOLDER}, class {CLASS_PLACEHOLDER}"
    assert data["thinking_text"] == f"The student wrote {STUDENT_PLACEHOLDER}."
    assert "binh" not in fold(all_text(data))
    assert_consistent(data)


def test_names_given_on_the_command_line_are_scrubbed(tmp_path: Path) -> None:
    data = cassette(
        "transcribe_page",
        {"header_text": "Họ và tên: Trần Thị Mai  Lớp: 9C2", "sections": []},
    )
    path = write(tmp_path, data, "001-transcribe_page.json")
    assert check_dir(tmp_path) == []  # no field names her: the check cannot see it
    assert main(["scrub", "--name", "Trần Thị Mai", "--class", "9C2", str(tmp_path)]) == 0
    scrubbed = load(path)
    header_text = json.loads(scrubbed["response_text"])["header_text"]
    assert header_text == f"Họ và tên: {STUDENT_PLACEHOLDER}  Lớp: {CLASS_PLACEHOLDER}"
    assert_consistent(scrubbed)


def test_logprobs_collapse_to_one_placeholder_entry() -> None:
    original = read_answers()
    targets = Targets(frozenset({NAME}), frozenset({CLASS}))
    data, changed = scrub_cassette(original, targets)
    assert changed
    assert_consistent(data)
    entries = data["logprobs"]
    collapsed = [e for e in entries if STUDENT_PLACEHOLDER in e["token"]]
    assert len(collapsed) == 4  # 2 in the thinking, 2 in the response
    for entry in collapsed + [e for e in entries if CLASS_PLACEHOLDER in e["token"]]:
        assert entry["top_logprobs"] == []
    # logprob = the min of the entries it replaced
    old = original["logprobs"]
    old_stream = b"".join(bytes(e["bytes"]) for e in old)
    start = old_stream.find(f'"student_name": "{NAME}'.encode()) + len(b'"student_name": "')
    end = start + len(NAME.encode())
    pos, covered = 0, []
    for e in old:
        n = len(e["bytes"])
        if pos < end and pos + n > start:
            covered.append(e["logprob"])
        pos += n
    assert min(covered) in [e["logprob"] for e in collapsed]
    assert len(entries) < len(old)


def test_word_boundaries_and_placeholders_are_respected() -> None:
    targets = Targets(frozenset({"Sinh"}), frozenset({CLASS}))
    text = f"{STUDENT_PLACEHOLDER} in 18A35 and 8A3; Sinh."
    spans = find_spans(text, targets)
    replaced = [text[s:e] for s, e, _ in spans]
    assert replaced == ["8A3", "Sinh"]


def test_scrub_is_idempotent_and_skips_clean_files(tmp_path: Path) -> None:
    write(tmp_path, read_answers(), "001-read_answers_page.json")
    write(tmp_path, transcribe(), "002-transcribe_page.json")
    assert len(scrub_dir(tmp_path)) == 2
    assert scrub_dir(tmp_path) == []
    assert scrub_dir(tmp_path, names=["Sinh"]) == []  # a placeholder is never matched again


def test_scrub_works_on_invalid_json_and_without_logprobs(tmp_path: Path) -> None:
    data = read_answers()
    data["response_text"] = data["response_text"][:60]  # cut off mid-stream
    data["logprobs"] = None
    assert NAME in data["response_text"]
    path = write(tmp_path, data, "001-read_answers_page.json")
    scrub_dir(tmp_path)
    new = load(path)
    assert NAME not in new["response_text"]
    assert f'"student_name": "{STUDENT_PLACEHOLDER}"' in new["response_text"]
    assert new["logprobs"] is None


def test_field_values_finds_nested_and_null() -> None:
    text = '{"a": {"student_name": null}, "b": [{"class_name": "7B"}]}'
    assert field_values(text) == [("student_name", None), ("class_name", "7B")]


def test_check_passes_on_empty_or_absent_folder(tmp_path: Path) -> None:
    assert main(["scrub", "--check", str(tmp_path / "absent")]) == 0
    (tmp_path / "empty").mkdir()
    assert main(["scrub", "--check", str(tmp_path / "empty")]) == 0


def test_check_help_says_the_teacher_still_reads_cassettes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["scrub", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert "read recorded cassettes" in help_text
    assert "--name TEXT" in help_text and "--class TEXT" in help_text


def test_committed_cassettes_are_scrubbed() -> None:
    """S5 on the repository's own cassettes."""
    assert check_dir(CASSETTES) == []


@pytest.mark.parametrize("value", [None, STUDENT_PLACEHOLDER])
def test_check_accepts_null_and_placeholders(tmp_path: Path, value: str | None) -> None:
    data = cassette("read_answers_page", {"student_name": value, "class_name": CLASS_PLACEHOLDER})
    write(tmp_path, data, "001-read_answers_page.json")
    assert check_dir(tmp_path) == []


# --- name variants and alternatives (verifier case) --------------------------------------------

TAM = "Lê Văn Tâm"


def everything(data: dict[str, Any]) -> str:
    """All text of a cassette, folded: response, thinking, chosen tokens and alternatives."""
    parts = [data["response_text"], data["thinking_text"]]
    for entry in data["logprobs"] or []:
        parts.append(bytes(entry["bytes"]).decode("utf-8", "replace"))
        parts += [str(alt["token"]) for alt in entry.get("top_logprobs") or []]
    return fold("\n".join(parts))


def with_alternatives(data: dict[str, Any], tokens: list[str]) -> dict[str, Any]:
    """Offer ``tokens`` as alternatives on the first entries (unrelated to any name)."""
    for entry, token in zip(data["logprobs"], tokens, strict=False):
        entry["top_logprobs"] = [
            *entry["top_logprobs"],
            {"token": token, "logprob": -4.0, "bytes": list(token.encode("utf-8"))},
        ]
    return data


def test_verifier_case_given_name_class_and_alternatives(tmp_path: Path) -> None:
    header = cassette(
        "transcribe_page",
        {"header_text": f"Họ và tên: {TAM}\nĐỀ KIỂM TRA", "sections": []},
        thinking="Em Tâm học lớp 7B4. Tam is the student.",
    )
    answers = cassette(
        "read_answers_page",
        {"student_name": TAM, "class_name": "7B4", "answers": []},
        thinking="Em Tâm học lớp 7B4. Tam is the student.",
    )
    for data in (header, answers):
        with_alternatives(data, [" Tâm", "7B4", " Tam", "Văn Tâm"])
    paths = [
        write(tmp_path, header, "001-transcribe_page.json"),
        write(tmp_path, answers, "002-read_answers_page.json"),
    ]
    assert len(scrub_dir(tmp_path)) == 2
    for path in paths:
        data = load(path)
        text = everything(data)
        assert re.search(r"\btam\b", text) is None
        assert "7b4" not in text
        assert_consistent(data)
        assert data["thinking_text"] == (
            f"Em {STUDENT_PLACEHOLDER} học lớp {CLASS_PLACEHOLDER}. {STUDENT_PLACEHOLDER} is the"
            " student."
        )
    assert json.loads(load(paths[0])["response_text"])["header_text"] == (
        f"Họ và tên: {STUDENT_PLACEHOLDER}\nĐỀ KIỂM TRA"
    )


def test_two_word_form_is_one_placeholder_and_family_name_alone_stays() -> None:
    targets = Targets(frozenset({TAM}))
    text = "Văn Tâm wrote this. Lê Lợi street. Lê Văn Tâm."
    data, _ = scrub_cassette(cassette("t", text), targets)
    assert data["response_text"] == (
        f"{STUDENT_PLACEHOLDER} wrote this. Lê Lợi street. {STUDENT_PLACEHOLDER}."
    )
    assert_consistent(data)


def test_stopword_given_name_needs_capital_mid_sentence() -> None:
    targets = Targets(frozenset({"Nguyễn Thị An"}))
    text = "An apple a day; an answer. Em An làm bài. Nguyễn Thị An."
    data, _ = scrub_cassette(cassette("t", text), targets)
    assert data["response_text"] == (
        f"An apple a day; an answer. Em {STUDENT_PLACEHOLDER} làm bài. {STUDENT_PLACEHOLDER}."
    )
    assert_consistent(data)


def test_stopword_given_name_with_accents_matches_as_exact_original() -> None:
    targets = Targets(frozenset({"Trần Thanh Hải"}))
    data, _ = scrub_cassette(cassette("t", "Hải làm bài. Hai apples."), targets)
    assert data["response_text"] == f"{STUDENT_PLACEHOLDER} làm bài. Hai apples."


def test_alternatives_spelling_a_prefix_are_removed() -> None:
    targets = Targets(frozenset({"Nguyễn Văn Bình"}), frozenset({"8A3"}))
    data = with_alternatives(cassette("t", "The answer is B."), ["Nguy", "Bi", " bình", "8a3", "A"])
    new, changed = scrub_cassette(data, targets)
    assert changed
    kept = [alt["token"] for e in new["logprobs"] for alt in e["top_logprobs"]]
    assert "Nguy" not in kept and " bình" not in kept and "8a3" not in kept
    assert "Bi" in kept and "A" in kept  # shorter than 3 characters: kept


# --- string values only; values that are not names or classes (the recorded-s1 failure) -------


def test_numeric_name_and_class_are_ignored_and_numbers_stay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = cassette(
        "read_answers_page", {"student_name": "34", "class_name": "35", "answers": {}}
    )
    page = {
        "header_text": "Question 34 and 35",
        "sections": [{"range_first": 34, "range_last": 35, "questions": [{"printed_number": 34}]}],
    }
    paths = [
        write(tmp_path, answers, "001-read_answers_page.json"),
        write(tmp_path, cassette("transcribe_page", page), "002-transcribe_page.json"),
    ]
    before = [load(p) for p in paths]
    assert main(["scrub", str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert "ignored student_name '34': not a name; pass --name if needed" in err
    assert "ignored class_name '35': not a class; pass --class if needed" in err
    for path, old in zip(paths, before, strict=True):
        data = load(path)
        assert data == old  # nothing replaced
        json.loads(data["response_text"])
        assert_consistent(data)
    assert json.loads(load(paths[1])["response_text"]) == page
    assert check_dir(tmp_path) == []  # not a name / class: nothing for S5 to flag


def test_names_are_replaced_in_string_values_only(tmp_path: Path) -> None:
    """Explicit values are not filtered, but still never touch numbers, keys or literals."""
    page = {"header_text": "Lớp 12 - 12 - Học sinh", "12": 12, "sections": [12, "x 12 y"]}
    path = write(tmp_path, cassette("transcribe_page", page), "001-transcribe_page.json")
    scrub_dir(tmp_path, classes=["12"])
    data = load(path)
    parsed = json.loads(data["response_text"])
    c = CLASS_PLACEHOLDER
    assert parsed == {
        "header_text": f"Lớp {c} - {c} - Học sinh",
        "12": 12,
        "sections": [12, f"x {c} y"],
    }
    assert_consistent(data)


def test_class_equal_to_an_answer_value_leaves_answers_intact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The blank-page case: the model wrote an answer letter as the class."""
    response = {
        "student_name": NAME,
        "class_name": "B",
        "answers": {"q-1": [{"value": "B", "location": "circled_option"}]},
    }
    path = write(tmp_path, cassette("read_answers_page", response), "001-read_answers_page.json")
    scrub_dir(tmp_path)
    assert "ignored class_name 'B': not a class" in capsys.readouterr().err
    data = load(path)
    parsed = json.loads(data["response_text"])
    assert parsed["student_name"] == STUDENT_PLACEHOLDER
    assert parsed["class_name"] == "B"
    assert parsed["answers"] == response["answers"]
    assert_consistent(data)


@pytest.mark.parametrize(
    ("value", "name", "cls"),
    [
        ("34", False, False),
        ("B", False, False),
        ("An", True, False),
        ("Nguyễn Văn Bình", True, False),
        ("8A3", False, True),
        ("8TC11", False, True),
        ("A1", False, True),
        ("Bình 2", False, True),
    ],
)
def test_name_and_class_shapes(value: str, name: bool, cls: bool) -> None:
    from etach.domain.boxes import looks_like_class, looks_like_name

    assert looks_like_name(value) is name
    assert looks_like_class(value) is cls


# --- template type words, a name with its class, refused options --------------------------------


def test_template_type_words_are_never_targets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = cassette(
        "read_answers_page",
        {"student_name": "string", "class_name": "verbatim-string", "answers": {}},
    )
    page = {"header_text": "Write a string of verbatim-string words", "sections": []}
    paths = [
        write(tmp_path, answers, "001-read_answers_page.json"),
        write(tmp_path, cassette("transcribe_page", page), "002-transcribe_page.json"),
    ]
    before = [load(p) for p in paths]
    assert main(["scrub", str(tmp_path)]) == 0
    err = capsys.readouterr().err
    assert "ignored student_name 'string'" in err and "ignored class_name 'verbatim-string'" in err
    assert [load(p) for p in paths] == before
    assert check_dir(tmp_path) == []


def test_name_with_a_trailing_class_yields_both_targets(tmp_path: Path) -> None:
    answers = cassette(
        "read_answers_page",
        {"student_name": f"{NAME} 8TC11", "class_name": None, "answers": {}},
    )
    page = {"header_text": f"Họ và tên: {NAME}  Lớp: 8TC11", "sections": []}
    assert {v.value for v in check_dir_of(tmp_path, answers)} == {f"{NAME} 8TC11"}
    header = write(tmp_path, cassette("transcribe_page", page), "002-transcribe_page.json")
    scrub_dir(tmp_path)
    got = json.loads(load(header)["response_text"])["header_text"]
    assert got == f"Họ và tên: {STUDENT_PLACEHOLDER}  Lớp: {CLASS_PLACEHOLDER}"
    parsed = json.loads(load(tmp_path / "001-read_answers_page.json")["response_text"])
    assert parsed["student_name"] == f"{STUDENT_PLACEHOLDER} {CLASS_PLACEHOLDER}"
    assert check_dir(tmp_path) == []


def check_dir_of(folder: Path, data: dict[str, Any]) -> list[Any]:
    write(folder, data, "001-read_answers_page.json")
    return check_dir(folder)


@pytest.mark.parametrize("value", ["None", "null", "", "  ", "string"])
def test_empty_or_none_options_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    path = write(tmp_path, transcribe(), "001-transcribe_page.json")
    before = load(path)
    for flag in ("--name", "--class"):
        assert main(["scrub", flag, value, str(tmp_path)]) == 2
        assert "not a value to scrub" in capsys.readouterr().err
    assert load(path) == before
