<#
.SYNOPSIS
  M1 overnight eval batch: runs `etach eval --graph extract` several times on one fixture set and
  writes a REPORT.md with each key metric's run values, mean, min and max.

.DESCRIPTION
  Windows PowerShell 5.1. The teacher starts it (docs/initial-plan/phases-testing/m1-overnight.md):

    powershell -ExecutionPolicy Bypass -File sidecar\scripts\m1-overnight.ps1 -Label baseline

  - Pre-flight: `etach eval --preflight` (the fixtures load; Ollama answers and has the models),
    and a warning when the git tree is not clean (the CSV `commit` column would not describe
    the code that ran).
  - Keeps the PC awake while it runs (SetThreadExecutionState; the power plan is not changed).
  - Each run: `uv run etach eval --graph extract --set <set> --keep <out>\run-<k>`, stdout and
    stderr to <out>\run-<k>.log. With nvidia-smi, the peak VRAM is sampled and recorded.
    A failed run is logged and the next run starts.
  - <out> = fixtures\_runs\<yyyy-MM-ddTHH-mm>-<label>\ (gitignored: it holds student text).
  - Writes <out>\REPORT.md, also when stopped with Ctrl+C. Commits nothing.

  - With -Check (speed bundle 1): first a short live check on one small fixture, into its own
    folder <out>-check\ and its own history file (eval-history.csv gets no row). It prints
    "CHECK OK" or "CHECK FAILED: <reason>" and its time. It fails on a failed fixture, a model
    call that ended `error` (incl. prompt_truncated) or `output_capped`, or a CER of 1.0.
    A failed check stops the script (exit 3); a passed one goes on to the batch.
    -CheckOnly runs the check and stops.
  - The check prints, per paper, CER, stimulus CER, structure_overall, answer_accuracy and
    seconds next to the same paper in a reference run (-CompareTo; default the latest
    fixtures\_runs\*-baseline<N>, highest N) with the difference, and writes that table to
    <out>-check\CHECK.md. The reference is a batch folder (run-1\<set>\<paper>\metrics.json) or
    a check folder (<set>\<paper>\metrics.json).
  - -Mini: the mini test after each change, a check on 3 papers (lop8-hk1-de1,
    L9-T23-book-lop9-50de, L12-TS12-D1-2025-docx). -Mini -CheckOnly runs only that.

  Rules: tuning only while tuning (-Set heldout needs -Final); every change is judged on 1 run
  (temperature 0 and a fixed seed).

.PARAMETER Set       tuning (default) or heldout; heldout is refused unless -Final is given.
.PARAMETER Runs      how many runs (default 1; 0 with -Check = the check only).
.PARAMETER Check     run the live check first (see above); the batch follows if it passes.
.PARAMETER CheckOnly run the live check and stop.
.PARAMETER CheckFixture  the check's fixture name(s), comma-separated or several
                     (default lop8-hk1-de1).
.PARAMETER Mini      the check on the 3 mini-test papers (implies -Check).
.PARAMETER CompareTo the reference folder, a batch or a check folder (default the latest
                     fixtures\_runs\*-baseline<N>, highest N).
.PARAMETER Role      vision=<tag> and/or reasoning=<tag>, passed to `etach eval --role`.
                     Several: -Role "vision=a","reasoning=b" (or one string "vision=a,reasoning=b").
.PARAMETER Graph     extract (default) or grade (M2: `etach eval --graph grade`, the grade graph on
                     the fixtures' typed truth; -Check / -Mini are for extract only).
.PARAMETER Reasoning the reasoning model tag for this batch (adds --role reasoning=<tag>).
.PARAMETER Label     a short name for this batch, e.g. baseline (letters, digits, - and _).
.PARAMETER Final     allows -Set heldout (the final report run).
.PARAMETER Ollama    use the Ollama at this URL instead of a private one (`--spawn-ollama`).

  Hidden, for offline tests of this script (not for the teacher):
  -OutRoot DIR       the parent of the batch folder (default <repo>\fixtures\_runs).
  -History CSV       passed as `--history` (default: the repo's eval-history.csv).
  -ExtraArgs ...     appended to every `etach eval` call, e.g. --fixtures DIR --replay DIR.
                     With --replay in it, no Ollama is used.
#>
[CmdletBinding()]
param(
    [ValidateSet('tuning', 'heldout')][string]$Set = 'tuning',
    [ValidateRange(0, 50)][int]$Runs = 1,
    [switch]$Check,
    [switch]$CheckOnly,
    [string[]]$CheckFixture = @('lop8-hk1-de1'),
    [switch]$Mini,
    [string]$CompareTo = '',
    [string[]]$Role = @(),
    [string]$Label = 'batch',
    [ValidateSet('extract', 'grade')][string]$Graph = 'extract',
    [string]$Reasoning = '',
    [switch]$Final,
    [string]$Ollama = '',
    [string]$OutRoot = '',
    [string]$History = '',
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = 'Stop'
$Inv = [Globalization.CultureInfo]::InvariantCulture
$Utf8 = New-Object System.Text.UTF8Encoding $false
$Sidecar = Split-Path -Parent $PSScriptRoot
$Repo = Split-Path -Parent $Sidecar

function Say([string]$Text) { Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $Text) }
function Warn([string]$Text) { Write-Host ("[{0}] WARNING: {1}" -f (Get-Date -Format 'HH:mm'), $Text) -ForegroundColor Yellow }
function Fail([string]$Text) { Write-Host ("m1-overnight: {0}" -f $Text) -ForegroundColor Red; exit 2 }

# --- parameters -------------------------------------------------------------------------------

if ($Set -eq 'heldout' -and -not $Final) {
    Fail 'held-out is run only at the end, for the report: add -Final to run -Set heldout.'
}
$Label = ($Label -replace '[^A-Za-z0-9_-]', '-').Trim('-')
if ($Label -eq '') { $Label = 'batch' }
$DoCheck = [bool]($Check -or $CheckOnly -or $Mini)
$DoBatch = (-not $CheckOnly) -and $Runs -gt 0
if (-not $DoCheck -and -not $DoBatch) { Fail '-Runs 0 runs nothing; add -Check (or -CheckOnly) for the check.' }
# -Mini: the teacher's mini test after each change (a photo with student writing, a book PDF
# with page-break losses, the long DOCX)
$MiniFixtures = @('lop8-hk1-de1', 'L9-T23-book-lop9-50de', 'L12-TS12-D1-2025-docx')
$names = $CheckFixture
if ($Mini) { $names = $MiniFixtures }
$CheckNames = @()
foreach ($item in $names) {
    foreach ($one in ($item -split ',')) {
        $one = $one.Trim()
        if ($one -ne '' -and $CheckNames -notcontains $one) { $CheckNames += $one }
    }
}
if ($DoCheck -and $CheckNames.Count -eq 0) { Fail '-CheckFixture: no fixture name given.' }
if ($Graph -eq 'grade' -and $DoCheck) { Fail '-Check, -CheckOnly and -Mini are for -Graph extract only.' }
# the reference run the check is compared with: -CompareTo, else the -baseline<N> batch with the highest N
$RefDir = ''
if ($DoCheck) {
    if ($CompareTo -ne '') {
        if (-not (Test-Path -LiteralPath $CompareTo -PathType Container)) { Fail "-CompareTo ${CompareTo}: no such folder." }
        $RefDir = (Resolve-Path -LiteralPath $CompareTo).Path
    } else {
        # the highest -baseline<N> (a plain -baseline counts as 1); the newest folder on a tie
        $cand = Get-ChildItem -LiteralPath (Join-Path $Repo 'fixtures\_runs') -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '-baseline(\d*)$' } |
            Sort-Object @{ Expression = { $m = [regex]::Match($_.Name, '-baseline(\d*)$').Groups[1].Value; if ($m -eq '') { 1 } else { [int]$m } } }, Name |
            Select-Object -Last 1
        if ($null -ne $cand) { $RefDir = $cand.FullName }
    }
}

$RoleArgs = @()
foreach ($item in $Role) {
    foreach ($one in ($item -split ',')) {
        $one = $one.Trim()
        if ($one -eq '') { continue }
        if ($one -notmatch '^(vision|reasoning)=.+$') { Fail "-Role '$one': expected vision=<tag> or reasoning=<tag>" }
        $RoleArgs += @('--role', $one)
    }
}
if ($Reasoning.Trim() -ne '') { $RoleArgs += @('--role', ('reasoning=' + $Reasoning.Trim())) }

$Replay = $ExtraArgs -contains '--replay'
$BackendArgs = @()
if (-not $Replay) {
    if ($Ollama -ne '') { $BackendArgs = @('--ollama', $Ollama) } else { $BackendArgs = @('--spawn-ollama') }
}
$HistoryPath = $History
if ($HistoryPath -eq '') { $HistoryPath = Join-Path $Repo 'eval-history.csv' }
$HistoryPath = [IO.Path]::GetFullPath($HistoryPath)
$HistoryArgs = @()
if ($History -ne '') { $HistoryArgs = @('--history', $HistoryPath) }

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $Uv) { Fail 'uv is not on PATH.' }
$Uv = $Uv.Source
$Smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($null -ne $Smi) { $Smi = $Smi.Source }

if ($OutRoot -eq '') { $OutRoot = Join-Path $Repo 'fixtures\_runs' }
$Stamp = Get-Date -Format 'yyyy-MM-ddTHH-mm'
$Out = Join-Path $OutRoot "$Stamp-$Label"
$n = 2
while ((Test-Path $Out) -or (Test-Path "$Out-check")) { $Out = Join-Path $OutRoot "$Stamp-$Label-$n"; $n++ }
$CheckDir = "$Out-check"  # the check's own folder (its run, logs and history file)

# --- helpers ----------------------------------------------------------------------------------

function Quote([string]$s) { return '"' + ($s -replace '"', '\"') + '"' }

# Run `uv run etach eval <args>` with stdout + stderr into $Log; sample VRAM into $VramFile.
# Returns the exit code.
function Invoke-Etach([string[]]$EtachArgs, [string]$Log, [string]$VramFile) {
    $parts = @((Quote $Uv), 'run', 'etach') + @($EtachArgs | ForEach-Object { Quote $_ })
    $line = ($parts -join ' ') + ' > ' + (Quote $Log) + ' 2>&1'
    $p = Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c "' + $line + '"') `
        -WorkingDirectory $Sidecar -NoNewWindow -PassThru
    $null = $p.Handle  # keeps ExitCode readable after the process ends
    $peak = -1
    $tick = 0
    while (-not $p.HasExited) {
        if ($VramFile -ne '' -and $null -ne $Smi -and ($tick % 5) -eq 0) {
            try {
                $used = & $Smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null
                foreach ($u in @($used)) {
                    $v = 0
                    if ([int]::TryParse(([string]$u).Trim(), [ref]$v) -and $v -gt $peak) {
                        $peak = $v
                        [IO.File]::WriteAllText($VramFile, [string]$peak, $Utf8)
                    }
                }
            } catch { }
        }
        Start-Sleep -Seconds 1
        $tick++
    }
    $p.WaitForExit()
    return $p.ExitCode
}

function Count-Lines([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    return @(Get-Content -LiteralPath $Path -Encoding UTF8 | Where-Object { $_ -ne '' }).Count
}

function Get-CsvRow([string]$Path, [int]$LineNo) {
    $rows = @(Import-Csv -LiteralPath $Path -Encoding UTF8)
    $i = $LineNo - 2
    if ($i -lt 0 -or $i -ge $rows.Count) { return $null }
    return $rows[$i]
}

function Num([string]$s) {
    if ($null -eq $s -or $s.Trim() -eq '') { return $null }
    return [double]::Parse($s, $Inv)
}

function Fmt($v, [string]$f) {
    if ($null -eq $v) { return '-' }
    return ([double]$v).ToString($f, $Inv)
}

function Fmt-Span([TimeSpan]$t) { return ('{0}h {1:00}m' -f [int][Math]::Floor($t.TotalHours), $t.Minutes) }

$GradeMetrics = @(
    @{ Name = 'key_accuracy_fast'; Format = '0.0000' },
    @{ Name = 'key_accuracy'; Format = '0.0000' },
    @{ Name = 'verdict_accuracy'; Format = '0.0000' },
    @{ Name = 'judge_accuracy'; Format = '0.0000' },
    @{ Name = 'score_exact_match'; Format = '0.0000' },
    @{ Name = 's_per_fixture'; Format = '0.0' }
)
$Metrics = @(
    @{ Name = 'cer'; Format = '0.0000' },
    @{ Name = 'stimulus_cer'; Format = '0.0000' },
    @{ Name = 'structure_overall'; Format = '0.0000' },
    @{ Name = 'answer_accuracy'; Format = '0.0000' },
    @{ Name = 'calibration'; Format = '0.0000' },
    @{ Name = 'key_accuracy'; Format = '0.0000' },
    @{ Name = 's_per_fixture'; Format = '0.0' }
)

if ($Graph -eq 'grade') { $Metrics = $GradeMetrics }

function Metric-Value($Row, [string]$Name) {
    if ($null -eq $Row) { return $null }
    if ($Name -eq 's_per_fixture') {
        $w = Num $Row.wall_s
        $nf = Num $Row.n_fixtures
        if ($null -eq $w -or $null -eq $nf -or $nf -eq 0) { return $null }
        return $w / $nf
    }
    return Num ($Row.$Name)
}

function Write-Report {
    $lines = New-Object System.Collections.Generic.List[string]
    $end = Get-Date
    $title = 'M1 batch'
    if ($Graph -eq 'grade') { $title = 'M2 grade batch' }
    $lines.Add("# ${title}: $Label")
    $lines.Add('')
    $failedRuns = @($script:RunInfo | Where-Object { $_.Exit -ne 0 }).Count
    $state = "finished; $failedRuns of $(@($script:RunInfo).Count) run(s) had a non-zero exit"
    if (-not $script:Completed) { $state = 'STOPPED EARLY (Ctrl+C or an error); only the runs listed below finished' }
    $lines.Add("- Status: $state")
    $lines.Add("- Set: ``$Set``, runs planned: $Runs, runs with a CSV row: $(@($script:RunInfo | Where-Object { $null -ne $_.Row }).Count)")
    $first = @($script:RunInfo | Where-Object { $null -ne $_.Row }) | Select-Object -First 1
    # without a row: the pre-flight's models and fixture count, and HEAD
    $vision = $script:Pre.model_vision; $reasoning = $script:Pre.model_reasoning
    $commit = $script:Head; $nfx = $script:Pre.n_fixtures; $mode = $script:Pre.mode
    if ($null -ne $first) {
        $vision = $first.Row.model_vision; $reasoning = $first.Row.model_reasoning
        $commit = $first.Row.commit; $nfx = $first.Row.n_fixtures; $mode = $first.Row.mode
    }
    $lines.Add("- Models: vision ``$vision``, reasoning ``$reasoning``")
    $dirtyNote = ''
    if ($script:Dirty) { $dirtyNote = ' (the tree was NOT clean at the start: uncommitted changes ran too)' }
    $lines.Add("- Commit: ``$commit``$dirtyNote; mode: $mode; fixtures per run: $nfx")
    $lines.Add("- Started $($script:Start.ToString('yyyy-MM-dd HH:mm')), ended $($end.ToString('yyyy-MM-dd HH:mm')); total time $(Fmt-Span ($end - $script:Start))")
    $lines.Add("- History: ``$HistoryPath``; row numbers are line numbers in that file (line 1 is the header)")
    $lines.Add('')
    $lines.Add('## Runs')
    $lines.Add('')
    $lines.Add('| Run | Exit | CSV row | n_failed | Time | Peak VRAM (MB) | Log |')
    $lines.Add('|---|---|---|---|---|---|---|')
    foreach ($r in $script:RunInfo) {
        $rowNo = '-'; $failed = '-'; $vram = '-'
        if ($null -ne $r.Row) { $rowNo = [string]$r.Line; $failed = $r.Row.n_failed; if ($r.Row.vram_peak_mb -ne '') { $vram = $r.Row.vram_peak_mb } }
        $lines.Add("| $($r.K) | $($r.Exit) | $rowNo | $failed | $(Fmt-Span $r.Time) | $vram | ``run-$($r.K).log`` |")
    }
    $lines.Add('')
    $lines.Add('## Key metrics')
    $lines.Add('')
    $ks = @($script:RunInfo | ForEach-Object { $_.K })
    $head = '| Metric | ' + (($ks | ForEach-Object { "Run $_" }) -join ' | ') + ' | Mean | Min | Max |'
    $lines.Add($head)
    $lines.Add('|---|' + (($ks | ForEach-Object { '---' }) -join '|') + '|---|---|---|')
    foreach ($m in $Metrics) {
        $vals = @()
        $cells = @()
        foreach ($r in $script:RunInfo) {
            $v = Metric-Value $r.Row $m.Name
            $cells += (Fmt $v $m.Format)
            if ($null -ne $v) { $vals += $v }
        }
        $mean = $null; $min = $null; $max = $null
        if ($vals.Count -gt 0) {
            $s = $vals | Measure-Object -Average -Minimum -Maximum
            $mean = $s.Average; $min = $s.Minimum; $max = $s.Maximum
        }
        $mlabel = $m.Name
        if ($mlabel -eq 's_per_fixture') { $mlabel = 'time per fixture (s)' }
        $lines.Add("| $mlabel | " + ($cells -join ' | ') + " | $(Fmt $mean $m.Format) | $(Fmt $min $m.Format) | $(Fmt $max $m.Format) |")
    }
    $lines.Add('')
    $lines.Add('Mean, min and max are over the runs that have a value (a run without a CSV row has none).')
    $lines.Add('')
    # per fixture, from each run's kept metrics.json
    $names = @()
    foreach ($r in $script:RunInfo) {
        $dir = Join-Path $Out "run-$($r.K)\$Set"
        if (Test-Path $dir) {
            foreach ($d in (Get-ChildItem -LiteralPath $dir -Directory | Sort-Object Name)) {
                if ($names -notcontains $d.Name) { $names += $d.Name }
            }
        }
    }
    if ($names.Count -gt 0) {
        $cols = 'cer / structure_overall / answer_accuracy'
        if ($Graph -eq 'grade') { $cols = 'key_accuracy_fast / key_accuracy / verdict_accuracy' }
        $lines.Add("## Per fixture ($cols, one cell per run)")
        $lines.Add('')
        $lines.Add('| Fixture | ' + (($ks | ForEach-Object { "Run $_" }) -join ' | ') + ' |')
        $lines.Add('|---|' + (($ks | ForEach-Object { '---' }) -join '|') + '|')
        foreach ($name in $names) {
            $cells = @()
            foreach ($r in $script:RunInfo) {
                $f = Join-Path $Out "run-$($r.K)\$Set\$name\metrics.json"
                if (Test-Path $f) {
                    $j = Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json
                    $mm = $j.metrics
                    if ($Graph -eq 'grade') {
                        $c = '{0} / {1} / {2}' -f (Fmt (Num $mm.key_accuracy_fast) '0.000'), (Fmt (Num $mm.key_accuracy) '0.000'), (Fmt (Num $mm.verdict_accuracy) '0.000')
                    } else {
                        $c = '{0} / {1} / {2}' -f (Fmt (Num $mm.cer) '0.000'), (Fmt (Num $mm.structure_overall) '0.000'), (Fmt (Num $mm.answer_accuracy) '0.000')
                    }
                    if ($j.status -ne 'done') { $c = "$c ($($j.status))" }
                    $cells += $c
                } else { $cells += '-' }
            }
            $lines.Add("| $name | " + ($cells -join ' | ') + ' |')
        }
        $lines.Add('')
        if ($Graph -eq 'grade') {
            $lines.Add("Details: ``run-<k>\$Set\<fixture>\grade.json`` (keys and verdicts per question), ``needs-verdict.json`` (answers that need your verdict), ``explanations.json``.")
        } else {
            $lines.Add("Details (which questions fail): ``run-<k>\$Set\<fixture>\metrics.json`` -> ``mismatches``.")
        }
        $lines.Add('')
    }
    $lines.Add('Nothing was committed. `eval-history.csv` holds the new rows; commit it later.')
    [IO.File]::WriteAllText((Join-Path $Out 'REPORT.md'), (($lines -join "`n") + "`n"), $Utf8)
}

# --- the live check (-Check / -CheckOnly) -----------------------------------------------------

# Why a fixture's check fails: its status, model calls that ended `error` (prompt_truncated or a
# dropped stream) or `output_capped` (an invalid output that used all of num_predict), CER 1.0.
function Get-CheckProblems([string]$Name, [string]$Dir) {
    $problems = @()
    $mf = Join-Path $Dir 'metrics.json'
    if (-not (Test-Path $mf)) { return @("${Name}: no result") }
    $j = Get-Content -LiteralPath $mf -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($j.status -ne 'done') { $problems += "${Name}: the run ended $($j.status)" }
    $cer = Num $j.metrics.cer
    if ($null -ne $cer -and $cer -ge 1.0) { $problems += "${Name}: CER 1.0" }
    $cf = Join-Path $Dir 'llm_calls.json'
    if (Test-Path $cf) {
        $errors = 0; $capped = 0; $truncated = 0
        $calls = Get-Content -LiteralPath $cf -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($c in $calls) {
            $np = $null
            if ($null -ne $c.request -and $null -ne $c.request.options) { $np = $c.request.options.num_predict }
            if ($c.status -eq 'prompt_truncated') { $truncated++ }
            elseif ($c.status -eq 'error') { $errors++ }
            elseif ($c.status -eq 'output_capped' -or ($c.status -eq 'invalid' -and $null -ne $np -and $null -ne $c.tokens_out -and [int]$c.tokens_out -ge [int]$np)) { $capped++ }
        }
        if ($truncated -gt 0) { $problems += "${Name}: $truncated call(s) prompt_truncated" }
        if ($errors -gt 0) { $problems += "${Name}: $errors call(s) ended error (prompt_truncated or a dropped stream)" }
        if ($capped -gt 0) { $problems += "${Name}: $capped call(s) output_capped" }
    }
    return $problems
}

# Runs the check; prints CHECK OK / CHECK FAILED and returns $true when it passed.
function Invoke-Check {
    $hist = Join-Path $CheckDir 'check-history.csv'  # never the repo's eval-history.csv
    $log = Join-Path $CheckDir 'check.log'
    $only = @()
    foreach ($nm in $CheckNames) { $only += @('--only', $nm) }
    $a = @('eval', '--graph', 'extract', '--set', $Set) + $RoleArgs + $BackendArgs + `
        @('--history', $hist, '--keep', $CheckDir) + $only + $ExtraArgs
    Say "Check: $($CheckNames -join ', ') (the laptop is busy); log: $log"
    $t0 = Get-Date
    $exit = Invoke-Etach $a $log ''
    $took = (Get-Date) - $t0
    $problems = @()
    $table = New-Object System.Collections.Generic.List[string]
    $table.Add('| Paper | Metric | Now | Reference | Difference |')
    $table.Add('|---|---|---|---|---|')
    foreach ($nm in $CheckNames) {
        $dir = Join-Path $CheckDir "$Set\$nm"
        $problems += @(Get-CheckProblems $nm $dir)
        $now = Read-FixtureMetrics (Join-Path $dir 'metrics.json')
        $ref = $null
        if ($RefDir -ne '') { $ref = Read-FixtureMetrics (Get-RefMetricsPath $RefDir $nm) }
        foreach ($m in $CheckMetrics) {
            $a = $null; $b = $null
            if ($null -ne $now) { $a = $now[$m.Name] }
            if ($null -ne $ref) { $b = $ref[$m.Name] }
            $d = '-'
            if ($null -ne $a -and $null -ne $b) {
                $diff = $a - $b
                $d = $diff.ToString($m.Format, $Inv)
                if ($diff -gt 0) { $d = '+' + $d }
            }
            $table.Add("| $nm | $($m.Label) | $(Fmt $a $m.Format) | $(Fmt $b $m.Format) | $d |")
        }
    }
    if ($exit -ne 0) { $problems += "etach eval exited $exit" }
    $time = '{0}m {1:00}s' -f [int][Math]::Floor($took.TotalMinutes), $took.Seconds
    $refText = 'none found (no comparison)'
    if ($RefDir -ne '') { $refText = "``$RefDir`` ($(Get-RefLayout $RefDir))" }
    Write-Host ''
    $table | ForEach-Object { Write-Host "  $_" }
    Write-Host "  Reference: $refText"
    Write-Host ''
    $verdict = "CHECK OK (time $time)"
    if ($problems.Count -gt 0) { $verdict = "CHECK FAILED: $($problems -join '; ') (time $time; log $log)" }
    $md = @("# M1 check: $Label", '', "- $verdict", "- Papers: $($CheckNames -join ', ')", "- Reference: $refText", '') + $table + @('')
    try { [IO.File]::WriteAllText((Join-Path $CheckDir 'CHECK.md'), (($md -join "`n") + "`n"), $Utf8) } catch { Warn "could not write CHECK.md: $_" }
    if ($problems.Count -gt 0) {
        Write-Host $verdict -ForegroundColor Red
        return $false
    }
    Write-Host $verdict -ForegroundColor Green
    return $true
}

# The compared metrics of one fixture's metrics.json (name -> number or $null); $null if missing.
$CheckMetrics = @(
    @{ Name = 'cer'; Label = 'CER'; Format = '0.000' },
    @{ Name = 'stimulus_cer'; Label = 'stimulus CER'; Format = '0.000' },
    @{ Name = 'structure_overall'; Label = 'structure_overall'; Format = '0.000' },
    @{ Name = 'answer_accuracy'; Label = 'answer_accuracy'; Format = '0.000' },
    @{ Name = 'seconds'; Label = 'seconds'; Format = '0' }
)
function Read-FixtureMetrics([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $j = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    $out = @{}
    foreach ($m in $CheckMetrics) {
        if ($m.Name -eq 'seconds') { $out['seconds'] = Num ([string]$j.wall_s) }
        else { $out[$m.Name] = Num ([string]$j.metrics.($m.Name)) }
    }
    return $out
}

# A paper's metrics.json in the reference folder. A batch folder keeps it under run-1\, a check
# folder (-Check / -Mini) under <set>\ directly; the batch layout wins when both exist.
function Get-RefMetricsPath([string]$Dir, [string]$Name) {
    $batch = Join-Path $Dir "run-1\$Set\$Name\metrics.json"
    if (Test-Path -LiteralPath $batch) { return $batch }
    return (Join-Path $Dir "$Set\$Name\metrics.json")
}

# How CHECK.md names the reference folder's layout.
function Get-RefLayout([string]$Dir) {
    if (Test-Path -LiteralPath (Join-Path $Dir 'run-1') -PathType Container) { return 'run-1' }
    return 'check'
}

# --- pre-flight -------------------------------------------------------------------------------

$PreDir = $Out
if ($DoCheck) { $PreDir = $CheckDir }
New-Item -ItemType Directory -Force -Path $PreDir | Out-Null
$script:Start = Get-Date
$script:RunInfo = @()
$script:Completed = $false
$script:BatchStarted = $false
$script:CheckFailed = $false
$script:Dirty = $false
$script:Pre = New-Object psobject -Property @{ model_vision = '-'; model_reasoning = '-'; n_fixtures = '-'; mode = '-' }
$script:Head = '-'
$plan = "$Runs run(s)"
if ($CheckOnly) { $plan = 'the check only' } elseif ($DoCheck) { $plan = "a check, then $Runs run(s)" }
Say "M1 batch '$Label': set $Set, $plan; started $($script:Start.ToString('yyyy-MM-dd HH:mm'))"
if ($DoCheck) { Say "Check output: $CheckDir" }
if ($DoBatch) { Say "Output: $Out" }

$git = Get-Command git -ErrorAction SilentlyContinue
if ($null -ne $git) {
    $status = @()
    try { $status = @(& git -C $Repo status --porcelain) } catch { }
    try { $script:Head = [string](& git -C $Repo rev-parse --short HEAD) } catch { }
    if (([string]::Join('', $status)).Trim() -ne '') {
        $script:Dirty = $true
        Warn 'the git tree is not clean: the CSV commit column will not describe all the code that runs.'
    }
}

$common = @('eval', '--graph', $Graph, '--set', $Set) + $RoleArgs + $BackendArgs + $HistoryArgs + $ExtraArgs
$env:PYTHONUTF8 = '1'
Say 'Pre-flight: fixtures, Ollama version and models ...'
$preLog = Join-Path $PreDir 'preflight.log'
$code = Invoke-Etach ($common + @('--preflight')) $preLog ''
Get-Content -LiteralPath $preLog -Encoding UTF8 | ForEach-Object { Write-Host "  $_" }
$preLine = @(Get-Content -LiteralPath $preLog -Encoding UTF8 | Where-Object { $_ -like '{*preflight*' }) | Select-Object -Last 1
if ($null -ne $preLine) { $script:Pre = $preLine | ConvertFrom-Json }
if ($code -ne 0) { Fail "pre-flight failed (exit $code); see $preLog. Nothing was run." }

# --- keep awake -------------------------------------------------------------------------------

Add-Type -Namespace EtachM1 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]2147483648      # 0x80000000
$ES_SYSTEM_REQUIRED = [uint32]1          # 0x00000001
$null = [EtachM1.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
Say 'Keeping the PC awake until the batch ends (the screen may still turn off).'

# --- the runs ---------------------------------------------------------------------------------

try {
    if ($DoCheck -and -not (Invoke-Check)) { $script:CheckFailed = $true }
    if ($DoBatch -and -not $script:CheckFailed) {
        New-Item -ItemType Directory -Force -Path $Out | Out-Null
        if ($DoCheck) { Copy-Item -LiteralPath $preLog -Destination (Join-Path $Out 'preflight.log') }
        $script:BatchStarted = $true
    }
    for ($k = 1; $script:BatchStarted -and $k -le $Runs; $k++) {
        $runDir = Join-Path $Out "run-$k"
        $log = Join-Path $Out "run-$k.log"
        $vramFile = Join-Path $Out "run-$k.vram-mb.txt"
        $before = Count-Lines $HistoryPath
        $args_k = $common + @('--keep', $runDir)
        if ($null -ne $Smi) { $args_k += @('--vram-mb-file', $vramFile) }
        $t0 = Get-Date
        Say "Run $k/$Runs started; log: $log"
        $exit = Invoke-Etach $args_k $log $vramFile
        $t1 = Get-Date
        $after = Count-Lines $HistoryPath
        $row = $null
        $lineNo = 0
        if ($after -eq $before + 1 -or ($before -eq 0 -and $after -eq 2)) {
            $lineNo = $after
            $row = Get-CsvRow $HistoryPath $lineNo
        }
        $script:RunInfo += New-Object psobject -Property @{ K = $k; Exit = $exit; Line = $lineNo; Row = $row; Time = ($t1 - $t0) }
        if ($null -eq $row) {
            Warn "run $k failed (exit $exit) and added no CSV row; see $log. Going on."
        } elseif ($exit -ne 0) {
            Warn "run $k ended with exit $exit ($($row.n_failed) fixture(s) failed); CSV line $lineNo. See $log."
        } else {
            if ($Graph -eq 'grade') {
                Say ("Run $k done in {0}: CSV line {1}; key fast {2}, key {3}, verdicts {4}" -f (Fmt-Span ($t1 - $t0)), $lineNo, $row.key_accuracy_fast, $row.key_accuracy, $row.verdict_accuracy)
            } else {
                Say ("Run $k done in {0}: CSV line {1}; cer {2}, structure {3}, answers {4}" -f (Fmt-Span ($t1 - $t0)), $lineNo, $row.cer, $row.structure_overall, $row.answer_accuracy)
            }
        }
        if ($k -lt $Runs) {
            $avg = [TimeSpan]::FromSeconds((($script:RunInfo | ForEach-Object { $_.Time.TotalSeconds }) | Measure-Object -Average).Average)
            for ($j = $k + 1; $j -le $Runs; $j++) {
                $eta = $t1 + [TimeSpan]::FromTicks($avg.Ticks * ($j - $k))
                Say ("  estimated end of run {0}: {1}" -f $j, $eta.ToString('ddd HH:mm'))
            }
        }
    }
    $script:Completed = $true
} finally {
    $null = [EtachM1.Power]::SetThreadExecutionState($ES_CONTINUOUS)
    Remove-Item Env:\PYTHONUTF8 -ErrorAction SilentlyContinue
    if ($script:BatchStarted) {
        try { Write-Report } catch { Warn "could not write REPORT.md: $_" }
    }
    $total = (Get-Date) - $script:Start
    if (-not $script:Completed) { Warn 'stopped early; finished runs are kept.' }
    Say "Total time $(Fmt-Span $total)."
    if ($script:BatchStarted) { Write-Host "REPORT: $(Join-Path $Out 'REPORT.md')" }
}

if ($script:CheckFailed) {
    if ($DoBatch) { Write-Host 'The batch was NOT started: fix the check failure first.' -ForegroundColor Red }
    exit 3
}
$bad = @($script:RunInfo | Where-Object { $_.Exit -ne 0 }).Count
if ($bad -gt 0) { exit 1 }
exit 0
