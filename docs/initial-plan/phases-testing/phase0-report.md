# Phase 0 Report — Exam Revision Helper

| | |
|---|---|
| Plan step | 5, Phase 0 live checks 👤 (R5.1–R5.4) |
| Answers | llm-design §9 Q1 (logprobs with `format` and images) and Q2 (NuExtract3 template vs `format`); PRD R4 |
| Status | **Filled from the live run on 2026-09-29; decisions approved by the teacher on 2026-09-29 and applied in PRD v4.6 / llm-design v4.7.** Every "Measured:" value comes from `docs/initial-plan/phases-testing/phase0-live-output.txt` (line numbers given as `out:L…`) or the scrubbed cassettes |
| Tests | `sidecar/tests/live/test_phase0_live.py` (items 1–6), helpers in `sidecar/tests/live/phase0.py` |

The tests start **their own** `ollama serve` on a free 127.0.0.1 port, as the app will (PRD §11).
They use the models in your usual models folder (`%USERPROFILE%\.ollama\models`), so nothing is
downloaded again. They never send work to your own Ollama on port 11434. They only ask it
whether a model is loaded, because a loaded model there would take VRAM.

The input is a **synthetic page** that the test draws: a printed MCQ with a pen circle around B,
and a gap-fill with a handwritten "plays". The made-up student is "Lê Văn Bình", class 7C3.
No student photo is used, so the cassettes hold no student data. They are still scrubbed.

---

## How to run (the teacher's runbook)

Run these in **PowerShell**, in order. The whole live run takes roughly 10–30 minutes; most of
that is model loading.

**1. Pull the two role models.** Your usual Ollama does the download. Wait until both finish.
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull numind/nuextract3:Q6_K
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen3.5:4b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

**2. Free the GPU.** Close other GPU programs. Your own Ollama should have no model loaded, so this
should list nothing:
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" ps
```

**3. Run `LIVE` with recording.** The first line removes cassettes from an earlier attempt. The
tests refuse to record into a folder that already has cassettes.
```powershell
cd D:\Projects\Exam_Revision_Helper\sidecar
if (Test-Path tests\cassettes\phase0) { Remove-Item -Recurse -Force tests\cassettes\phase0 }
$env:ERH_PHASE0_RECORD = "1"
uv run pytest -m live -q -s -rs
Remove-Item Env:ERH_PHASE0_RECORD
```
The results go to `sidecar/tests/live/_out/`, which git ignores. The folder holds
`phase0-results.json`, `pytest-summary.json` and the private server logs.

**4. Write the output file** (R5.2):
```powershell
uv run python tests/live/render_output.py --out ..\docs\initial-plan\phases-testing\phase0-live-output.txt
```
Check near the top of the file that the pytest summary says **0 failed**.

**5. Scrub the cassettes**, then check them:
```powershell
uv run erh scrub tests/cassettes/phase0 --name "Le Van Binh" --class 7C3
uv run erh scrub --check tests/cassettes/phase0
uv run python tests/live/render_output.py --check-cassettes tests/cassettes/phase0
```
The last command counts the cassettes against R5.4: at least 3 with logprobs, at least one of
them with an image input. The task name ends in `_image` for an image input.

**6. Look through the cassettes by hand for names.** Open each file in `tests\cassettes\phase0\`.
The name and class fields should read `Học Sinh A` / `8X1`. No other name should appear, and
no `Bình`/`Binh` or `7C3` should remain. This search should print nothing:
```powershell
Select-String -Path tests\cassettes\phase0\*.json -Encoding UTF8 -Pattern "Binh|Bình|7C3"
```

**7. Fill this report.** In each section, fill "Measured:" from `phase0-live-output.txt`, then write
the `Decision:` and `Fallback:` lines. Or ask Claude to draft them for you to check. If a
decision contradicts llm-design, llm-design needs a changelog row and plan.md's "Based on" line
changes in the same commit (R5.3).

**8. Commit the two sign-offs** (on the branch `step/5-phase0-live`). Type these yourself; agents
never make `👤 sign-off:` commits:
```powershell
cd D:\Projects\Exam_Revision_Helper
git add docs/initial-plan/phases-testing/phase0-live-output.txt
git commit -m "👤 sign-off: phase0 live output"
git add sidecar/tests/cassettes/phase0
git commit -m "👤 sign-off: cassettes phase0"
git log -2 --format=%s
```
The last command must show both subjects **starting with 👤**, because the verifier searches for
`^👤 sign-off:`. If PowerShell shows `??` in place of the emoji, run the two commits in Git
Bash instead. The report itself (with its decisions) can go into the second commit or its own
commit.

---

Run facts (out:L1–L32): Ollama 0.34.4, GTX 1660 Ti 6144 MiB (0 MiB used before the run), no model
loaded on the user's own Ollama, cassette recording on. Roles: vision `numind/nuextract3:Q6_K`,
reasoning `qwen3.5:4b`, both `num_ctx 16384, temperature 0, seed 42`. **pytest: 14 passed,
0 failed, 0 skipped, 0 errors** (out:L18).

## 1. Logprobs with `format`, with an image, and with both

Test `test_item1_logprobs`, 7 cases (out:L34–L43, records out:L101–L724). "Missing" is the same in
every case: one entry fewer than `eval_count`. That last token is the end-of-generation token,
which has no text; no content token lacks a logprob. Every entry has 5 `top_logprobs`.

- Measured: vision template + text: logprobs **33** / with top **33** / missing: 33 entries for eval_count 34 (the end token only); valid, 4/4 answers correct
- Measured: vision template + image: **33 / 33**, same; valid, 4/4 correct
- Measured: vision template + format + text: **33 / 33**, same; valid, 4/4 correct
- Measured: vision template + format + image: **33 / 33**, same; valid, 4/4 correct
- Measured: reasoning format + text: **44 / 44** (eval_count 45); valid, 4/4 correct
- Measured: reasoning format + image: **44 / 44** (eval_count 45); valid, 4/4 correct. `qwen3.5:4b` has vision, so this case ran
- Measured: reasoning format + think: **887 / 887** (eval_count 888), `covers = other`. **Yes, the logprobs cover the thinking tokens.** The joined tokens are the thinking text (2,787 chars live), then a literal `\n</think>`, then the JSON response (2,884 chars in all, out:L665–L666; checked in cassette `007-…think.json`: thinking, `</think>`, then `{…}`)
- Measured (side note): with `format`, `top_logprobs` still list tokens the schema grammar would forbid, e.g. ` ``` ` and `[` as alternatives to the opening `{` (out:L502–L506). For the vision role, template alone and template + `format` give **identical** logprobs to all printed digits (−0.0003722406690940261 on text, out:L144 and L322). So the logprobs are the model's distribution **before** the grammar mask

Decision: **Logprob confidence (llm-design §6) is the primary method for both roles, with
`format`, with images, and with both.** llm-design §9 Q1 is answered "yes" and PRD R4 is closed
for logprobs. Two details for step 6. (a) The span mapper finds the response inside the token
stream: with `think=true` it skips everything up to and including the `</think>` token. It does not
assume the logprobs match `response_text` from the first token. (b) It ignores the final token that
has no logprob entry. Because `top_logprobs` are taken before the grammar, restricting them to the
valid choices and renormalizing (as §6 already says) is needed, not optional.

Fallback: **`none`** (see "Summary for step 6" below). Logprobs were present in 13/13 answer
calls (items 1, 2, 3 and the item 5 answer checks), so the fallback is only a safety net, for a later model swap to a model without logprobs.

## 2. NuExtract3 template alone vs template + `format`

Test `test_item2_nuextract_template_vs_format`, page image (out:L45–L49, records out:L725–L902).

- Measured: template alone: valid **yes**, answers correct **4/4** (`B`, `plays`, name, class), logprobs **33**, time 53.8 s including a 17.0 s cold load (out:L804–L810)
- Measured: template + format: valid **yes**, answers correct **4/4**, logprobs **33**, time 2.2 s warm (out:L894–L899)
- Measured: output text identical, and the logprobs identical too (e.g. first token −0.0008233001572079957 in both, out:L767 and L856). Warm decode speed about the same (18.99 vs 16.95 tok/s; the first call includes image encoding at load)

Decision: **`adapter_options.also_format = true`** for the vision role in `models.toml` and in the
code defaults (currently `false` in `sidecar/src/erh/llm/defaults.py` and `config.py`). The
template stays as the native prompt; `format` is added as a grammar guard. On this page the two are
the same, so the grammar costs nothing measurable, and it rules out invalid JSON. Invalid JSON would
cost a retry of a 20–50 s vision call (llm-design §3.2 step 4). §9 Q2 is answered: they don't
conflict. Re-check on the real fixtures in Phase 1 (`erh eval`), because this page's output was
only 34 tokens, not a long transcription.

Fallback: if the fixture eval shows `format` hurting long transcriptions (slower, or truncated or
looping output), switch back to `also_format = false`. It is a config value, so no code changes.

## 3. The MCQ letter is a single token

Test `test_item3_mcq_letter_token` (out:L51–L55, records out:L903–L1120).

- Measured: vision (template, image): tokens **`["B"]`**, single token **yes**, A–D probabilities **{A 0.0, B 0.9999, C 0.0, D 0.0}**, other alternative `b` 0.0
- Measured: reasoning (`format`, image): tokens **`["B"]`**, single token **yes**, A–D probabilities **{A 0.0001, B 0.9992, C 0.0001, D 0.0001}**, other alternative `b` 0.0003
- Measured: the letter token is the bare letter. The quote before it is a separate token (` "`, then `B`, then `",`; cassette `002`). All four of A–D were in the top 5 for both models

Decision: **The §6 enum margin reads the first token of the value, as designed.** The letter is
one token for both roles. Restrict to the exact valid choices (case-sensitive: `b` and `(` are
dropped, as in R6.2), renormalize, margin = p(top) − p(second). A valid choice that is missing
from the top 5 counts as probability 0. This page's answer is very clear (margin ≈ 1.0), so the
threshold must come from the fixtures (§6), not from this run.

Fallback: none needed. If a later model splits a letter into several tokens, the first-token rule
still applies (§6).

## 4. VRAM and speed per role model at `num_ctx` 16384

Test `test_item4_vram_and_speed`, baseline server (flash attention 0, KV f16), cold load plus one
transcription call on the image (out:L57–L61, records out:L1121–L1248).

- Measured: vision: load **13.6 s**, prompt **27.0 tok/s**, eval **17.4 tok/s** (115 tokens), size **9436 MiB**, VRAM **7954 MiB**, GPU share 0.843, fully on GPU **no**; `nvidia-smi` 5953/6144 MiB; wall 52.3 s; valid
- Measured: reasoning: load **10.5 s**, prompt **105.9 tok/s**, eval **50.4 tok/s** (145 tokens), size **7995 MiB**, VRAM **7995 MiB**, GPU share 1.0, fully on GPU **yes** (reported); `nvidia-smi` 5953/6144 MiB; wall 21.2 s; valid
- Measured: `/api/ps` context_length = 16384 for both, so the setting is applied
- Note: both baseline `size_vram` values (7954, 7995 MiB) are **larger than the 6144 MiB card**, while `nvidia-smi` shows 5953 MiB used. `/api/ps` reports what Ollama allocated or estimated, not physical VRAM. On Windows the NVIDIA driver can place the extra in shared system memory. So the baseline "fully on GPU" for reasoning is not trustworthy, and the card was 97 % full

Decision: **Keep `num_ctx = 16384` for both roles, but only together with item 5 (flash attention
+ q8_0 KV).** Without them the baseline fills the card (5953/6144 MiB) and the vision model is
partly on the CPU. With them, reasoning is fully on the GPU at 3189 MiB, and vision is 77 % on the
GPU (3526 of 4567 MiB) with about 1.8 GB free on the card (item 5). A full page transcription
may need a long context, so the value stays. The vision model's partial offload goes to Phase 1:
measure `erh eval` speed with vision at `num_ctx` 8192 against 16384 on real pages before
changing anything. Use `nvidia-smi` numbers, not `/api/ps` `size_vram`, for the VRAM reported per
node (§8).

Fallback: not a confidence question. Both models ran and gave valid output.

## 5. Flash attention and q8_0 KV cache on Turing (GTX 1660 Ti)

Test `test_item5_flash_attention_q8_kv` (out:L63–L91, records out:L1249–L1512). No Ollama error.

- Measured: vision: VRAM **7954 → 3526 MiB** (size 9436 → 4567; `nvidia-smi` 5953 → 4349), eval **17.39 → 22.55 tok/s**, prompt **27.0 → 160.1 tok/s**, load 13.6 → 9.4 s, wall 52.3 → 19.9 s; valid **yes**, answers 4/4, transcript lines identical to the baseline (`same_lines: true`), error **none**. Still not fully on GPU (share 0.772; log shows a 34 MiB CPU KV buffer)
- Measured: reasoning: VRAM **7995 → 3189 MiB** (`nvidia-smi` 5953 → 4077), eval **50.42 → 51.57 tok/s**, prompt 105.9 → 115.1 tok/s, load 10.5 → 5.5 s, wall 21.2 → 15.5 s; valid **yes**, answers 4/4, error **none**. Fully on GPU. `same_lines: false`: the only difference is Question 2, "My brother ______ (play)" → "My brother (play)". Both runs leave out the handwritten word, so it is a small change in wording, not a lost reading
- Measured: server log: **yes, it is really enabled.** `llama_context: flash_attn = enabled`, `warmup: flash attention is enabled`, `K (q8_0): 136.00 MiB, V (q8_0): 136.00 MiB` for 16384 cells, for both models (out:L72–L91)

Decision: **On.** The app's `ollama serve` sets `OLLAMA_FLASH_ATTENTION=1` and
`OLLAMA_KV_CACHE_TYPE=q8_0`. On this Turing card it more than halves the memory, makes the vision
model 2.6× faster per page, keeps the reasoning speed, and gave the same answers. This adds two
environment variables to the server that llm-design §2 and PRD §11 describe, so both documents need
a minor version with this new detail.

Fallback: if a later model or Ollama version errors with flash attention (the test records the
error instead of failing), the app starts without the two variables for that model. The Phase 1
eval (CER, answer accuracy) confirms that q8_0 KV does not hurt quality on real pages.

## 6. Swap time with `OLLAMA_MAX_LOADED_MODELS=1`

Test `test_item6_swap_time`, baseline server (flash attention off, KV f16) (out:L93–L98,
out:L1513–L1558).

- Measured: vision (cold) load **11.7 s** (wall 48.0 s), reasoning (swap) load **14.7 s** (wall 16.8 s), vision (swap back) load **18.1 s** (wall 53.8 s). Valid each time, and after each call only the model just used was loaded
- Measured (for comparison, item 5): with flash attention + q8_0 the cold loads were 9.4 s (vision) and 5.5 s (reasoning)

Decision: **Keep `OLLAMA_MAX_LOADED_MODELS=1` (acceptable).** A swap costs about 12–18 s on the
baseline, less with item 5's settings. The extract graph uses only the vision role, and the grade
graph uses only the reasoning role (llm-design §4, §5), so a swap happens about once per run, not once per call.
Both models at once also do not fit: 3526 + 3189 MiB on the GPU plus overhead is more than
6144 MiB, even with flash attention + q8_0. No change to llm-design §2 / PRD §11.

Fallback: none needed. If a later graph switches roles inside one run, measure its swaps with
`erh eval` (time per node) before thinking about two loaded models.

---

## Other observations

- **Invalid output:** none. All 20 model calls (13 answer calls, 4 transcription calls in items 4–5, 3 swap calls) returned
  `complete` and valid output (out:L37–L43, L48–L49, L60–L61, L66–L67, L96–L98).
- **Temperature 0:** looks fine. Same input gave the same text every time. Logprobs across
  separate loads differ only in the 3rd significant digit (−0.000829 vs −0.000823, out:L233 and
  L767), which is floating-point noise, not sampling. The think call at temperature 0 ended by
  itself (`done_reason: stop`) after 888 of its 1500 tokens, so this run showed no repetition loop
  from greedy decoding with thinking. The Qwen guidance warns that it can happen, so watch
  `verify_key` in Phase 1.
- **Surprising:**
  - `/api/ps` reports more VRAM than the card has (item 4).
  - Without flash attention the vision model reads the page prompt at only 27 tok/s (160 with it).
  - The thinking text ends in a stray `cw` before `</think>` (cassette `007`). It is harmless, but
    it shows why the mapper should split on `</think>` and not on text.
  - `qwen3.5:4b` also reads the image: its answers were 4/4. Its transcription left out the
    handwriting, and NuExtract3's did not.
- **Scrubbed cassettes vs the live stream:** `erh scrub` merges the name tokens into one
  placeholder entry, so a cassette holds fewer logprob entries than the live call (vision 28 vs 33,
  reasoning 39 vs 44, think 850 vs 887; `render_output.py --check-cassettes`). Step 6 tests on the
  cassettes should check span mapping against the cassette's own `response_text`, not the live
  counts.

## Summary for step 6

- Chosen `confidence.fallback`: **`none`**. Logprobs work for both roles, with `format`, with
  images and with both (item 1), so the fallback is used only for a later model without logprobs.
  In that case `none` flags every value `?` for the teacher and costs no extra GPU time.
  `resample` would double every vision call (20–50 s per page on this laptop), and its 1.0/0.0
  agreement signal is weak at temperature 0. `self_report` is not calibrated for small models.
- Cassettes in `sidecar/tests/cassettes/phase0/`: **9** in total, **9** with logprobs, **5** with
  an image input (`002`, `004`, `006`, `008`, `009`). This meets R5.4 (≥ 3, at least one with an
  image). One (`007`) has thinking tokens before `</think>`: a test case for the span mapper.

