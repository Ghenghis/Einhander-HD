<#
claude-einhander-ui granted-job launcher, adapted from s45 tools/s45_grant_launch.ps1 (sha256 c7f9448f...).
Changes vs s45: base/cwd, receipts and logs are the registered ui output (receipts\, logs\); -Affinity has no default
(pass the mask the grant names); receipts carry owner and derived_from. Preflight, spawn, caps and exit codes unchanged.
ONE attempt per grant; never retries.
Preflight runs IMMEDIATELY before spawn, in this order: grant start deadline (GrantUtc + StartWindowSec), tool sha256, CPU load
< 60 %, free RAM > 16 GiB, log file absent. Any failure writes a DECLINE receipt (reason, values) and exits 3 without spawning;
a declined grant is reported and needs a fresh grant (no retry here).
On spawn: cmd /c start "" /b /wait /belownormal /affinity <mask> python -I -B <tool> <args>, threads env = 1, polls the python
child's working set every 200 ms (kill tree above MemCapMB), kills the tree at CapSec. Writes a receipt JSON with cmd/python PID,
python creation time, start/end UTC, wall, numerical outer exit, killed flag, peak working set, matching python processes left.
All output via Write-Host (no function return values). Writes receipts ONLY under <ui output>\receipts\, logs under <ui output>\logs\.
#>
param(
  [Parameter(Mandatory)] [string] $Name,
  [Parameter(Mandatory)] [string] $GrantUtc,
  [Parameter(Mandatory)] [string] $GrantMsg,
  [Parameter(Mandatory)] [string] $Tool,
  [Parameter(Mandatory)] [string] $ToolSha,
  [string] $ToolArgs = '',
  [int] $StartWindowSec = 120,
  [int] $CapSec = 30,
  [int] $MemCapMB = 512,
  [Parameter(Mandatory)] [string] $Affinity
)
$ErrorActionPreference = 'Stop'
$base = 'C:\github\Einhander\.claude\worktrees\xenodochial-snyder-093665\remaster-audit\claude-einhander-ui'
$rdir = "$base\receipts"
New-Item -ItemType Directory -Force $rdir | Out-Null
New-Item -ItemType Directory -Force "$base\logs" | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$receipt = "$rdir\$Name-$stamp.json"
$log = "$base\logs\$Name.log"
$match = [IO.Path]::GetFileName($Tool)
$grant = [datetime]::Parse($GrantUtc).ToUniversalTime()
$r = [ordered]@{ owner = 'claude-einhander-ui'; derived_from = 's45 tools/s45_grant_launch.ps1 c7f9448fb3cd612a656d3aa4cf051728345038930824d8d6d62814647e159a5a'; name = $Name; grant_msg = $GrantMsg; grant_utc = $grant.ToString('o'); start_window_s = $StartWindowSec; tool = $Tool; tool_args = $ToolArgs; cap_s = $CapSec; mem_cap_mib = $MemCapMB; affinity_mask = $Affinity }
# ---- preflight, immediately before spawn ----
$now = (Get-Date).ToUniversalTime()
$age = ($now - $grant).TotalSeconds
$sha = (Get-FileHash "$base\$Tool" -Algorithm SHA256).Hash.ToLower()
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
$freeGiB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 2)
$r.preflight = [ordered]@{ utc = $now.ToString('o'); seconds_since_grant = [math]::Round($age, 2); tool_sha256 = $sha; cpu_pct = $cpu; free_gib = $freeGiB; log_exists = (Test-Path $log) }
$why = @()
if ($age -gt $StartWindowSec) { $why += "start window expired ($([math]::Round($age,1)) s > $StartWindowSec s)" }
if ($sha -ne $ToolSha) { $why += 'tool sha mismatch' }
if ($cpu -ge 60) { $why += "cpu $cpu% >= 60" }
if ($freeGiB -le 16) { $why += "free RAM $freeGiB GiB <= 16" }
if (Test-Path $log) { $why += 'log exists' }
if ($why.Count -gt 0) {
  $r.status = 'DECLINED_UNUSED (no spawn; needs a fresh grant; no retry)'; $r.reasons = $why
  $r | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $receipt
  Write-Host "[$Name] DECLINED: $($why -join '; ') receipt=$receipt"
  exit 3
}
# ---- spawn ----
$env:OMP_NUM_THREADS = '1'; $env:OPENBLAS_NUM_THREADS = '1'; $env:MKL_NUM_THREADS = '1'; $env:NUMEXPR_NUM_THREADS = '1'
$start = (Get-Date).ToUniversalTime()
$p = Start-Process cmd.exe -ArgumentList '/c', ("start `"`" /b /wait /belownormal /affinity $Affinity python -I -B $Tool $ToolArgs") -WorkingDirectory $base -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$py = $null; $peak = 0; $killed = $false; $killReason = $null
$sw = [Diagnostics.Stopwatch]::StartNew()
while (-not $p.HasExited -and $sw.ElapsedMilliseconds -lt ($CapSec * 1000)) {
  if (-not $py) { $py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$match*" } | Select-Object -First 1 }
  if ($py) { try { $pp = Get-Process -Id $py.ProcessId -ErrorAction Stop; if ($pp.WorkingSet64 -gt $peak) { $peak = $pp.WorkingSet64 }; if ($peak -gt ($MemCapMB * 1MB)) { taskkill /T /F /PID $p.Id | Out-Null; $killed = $true; $killReason = 'memory cap'; break } } catch {} }
  Start-Sleep -Milliseconds 200
}
if (-not $p.HasExited) { taskkill /T /F /PID $p.Id | Out-Null; $killed = $true; $killReason = 'time cap' }
$p.WaitForExit(5000) | Out-Null
$end = (Get-Date).ToUniversalTime()
$left = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$match*" })
$r.status = 'RAN'
$r.cmd_pid = $p.Id; $r.python_pid = $py.ProcessId; $r.python_created = "$($py.CreationDate)"
$r.start_utc = $start.ToString('o'); $r.end_utc = $end.ToString('o'); $r.seconds_since_grant_at_spawn = [math]::Round(($start - $grant).TotalSeconds, 2)
$r.wall_s = [math]::Round(($end - $start).TotalSeconds, 2); $r.outer_exit = $p.ExitCode; $r.killed = $killed; $r.kill_reason = $killReason
$r.peak_ws_mib = [math]::Round($peak / 1MB, 1); $r.python_processes_left = $left.Count; $r.log = $log
$r | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $receipt
Write-Host "[$Name] cmd_pid=$($p.Id) python_pid=$($py.ProcessId) created=$($py.CreationDate) spawn_after_grant_s=$($r.seconds_since_grant_at_spawn) wall_s=$($r.wall_s) outer_exit=$($p.ExitCode) killed=$killed peak_MiB=$($r.peak_ws_mib) left=$($left.Count) receipt=$receipt"
Get-Content $log | Select-Object -Last 12 | Out-String | Write-Host
Get-Content "$log.err" -ErrorAction SilentlyContinue | Select-Object -First 12 | Out-String | Write-Host
if ($p.ExitCode -ne 0 -or $killed -or $left.Count -ne 0) { exit 1 }
exit 0
