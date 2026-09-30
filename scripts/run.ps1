# Discover an existing Python runtime; never installs software or changes policy.
param(
    [Parameter(Position=0)][string]$Script = 'search_law.py',
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$ScriptArgs
)
$ErrorActionPreference = 'Stop'
$allowed = @('search_law.py','search_cases.py','search_commercial_authorities.py','validate_knowledge_base.py','audit_sources.py','audit_matter.py','new_matter.py','release_guard.py','release_state.py','package_skill.py','benchmark_search.py')
if ($Script -notin $allowed) { throw 'Unsupported helper name.' }
$candidates = [Collections.Generic.List[string]]::new()
if ($env:CHINALAW_PYTHON) { $candidates.Add($env:CHINALAW_PYTHON) }
foreach ($name in @('python','python3','py')) {
    $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $candidates.Add($command.Source) }
}
$runtime = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $runtime) { $candidates.Add($runtime) }
$selected = $null
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    try {
        & $candidate -X utf8 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $selected = $candidate; break }
    } catch { continue }
}
if (-not $selected) { throw 'No usable Python 3.12+. Use read-only text search, or set CHINALAW_PYTHON to an existing runtime. No installation was performed.' }
& $selected -B -X utf8 (Join-Path $PSScriptRoot $Script) @ScriptArgs
exit $LASTEXITCODE
