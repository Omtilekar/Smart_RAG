param(
    [string]$Repo = (Get-Location).Path,
    [int]$QuotaRetrySeconds = 600,
    [int]$NormalResumeDelaySeconds = 5
)

$ErrorActionPreference = "Continue"
Set-Location $Repo

$ControllerPrompt = Join-Path $Repo "prompts\phase_3\task_3.99_phase3_autonomous_execution_loop.md"
$StateDir = Join-Path $Repo "artifacts\phase3_controller"
$StateFile = Join-Path $StateDir "state.json"
$LogFile = Join-Path $StateDir "supervisor.log"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if (-not (Test-Path $ControllerPrompt)) {
    Write-Error "Controller prompt not found: $ControllerPrompt"
    exit 2
}

function Write-SupervisorLog([string]$Message) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $line = "[$stamp] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Initialize-ControllerState {
    if (Test-Path $StateFile) {
        return
    }

    $initial = [ordered]@{
        controller          = "task_3.99_phase3_autonomous_execution_loop"
        status              = "RUNNING"
        current_task        = "unknown_until_repository_audit"
        last_completed_task = "unknown_until_repository_audit"
        current_stage       = "startup_audit"
        last_safe_commit    = $null
        resume_instruction  = "Audit Progress.md, PROJECT_EXECUTION.md, Git, results, and checkpoints; continue the first incomplete Phase 3 action."
        updated_at_utc      = (Get-Date).ToUniversalTime().ToString("o")
    }

    $initial | ConvertTo-Json -Depth 4 | Set-Content -Path $StateFile -Encoding UTF8
    Write-SupervisorLog "Initialized controller state at $StateFile"
}

function Get-ControllerStatus {
    if (-not (Test-Path $StateFile)) {
        return "MISSING"
    }
    try {
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
        if ($null -eq $state.status -or [string]::IsNullOrWhiteSpace([string]$state.status)) {
            return "UNKNOWN"
        }
        return [string]$state.status
    }
    catch {
        Write-Warning "Could not parse $StateFile : $($_.Exception.Message)"
        return "UNKNOWN"
    }
}

Initialize-ControllerState

# Claude Code's native /goal feature continues across normal model turns,
# so there is no human "type continue" step between Phase 3 tasks.
# The controller state gives the external supervisor a deterministic reason
# to stop when real human input is required.
$goalPrompt = @"
/goal Continue the Phase 3 controlled execution defined in
prompts/phase_3/task_3.99_phase3_autonomous_execution_loop.md.

First audit durable repository state: artifacts/phase3_controller/state.json,
Progress.md, project_plan/PROJECT_EXECUTION.md, git status/log, current
results/configs/checkpoints. Repository truth wins over conversation memory.

Keep working across normal task boundaries without asking me to type
"continue". After a numbered Phase 3 task completes, if its tests,
provenance, selection rule, Git state, protected-TEST gate, and next-task
contract are all valid and unambiguous, immediately start the next Phase 3
task.

Stop only when either:
1) the Phase 3 exit audit passes and the controller state is
   PHASE3_COMPLETE; or
2) a genuine hard stop requires me, and the controller state is
   WAITING_USER or BLOCKED with the exact reason recorded.

Do not start Phase 4. Do not consume protected TEST unless the repository
explicitly authorizes it and the controller's rules permit it.
"@

# Matches Claude subscription/session allowance messages as well as ordinary
# transient API rate-limit wording. In particular, current Claude Code prints
# messages such as "You've hit your session limit ... resets 2:30am".
$quotaPattern = '(?i)(usage\s+limit|session\s+limit|rate.?limit|quota|limit\s+reached|too\s+many\s+requests|capacity\s+limit|\b429\b|resets?\s+(?:at\s+|in\s+)?\d{1,2}:\d{2}\s*(?:am|pm)?)'

while ($true) {
    $status = Get-ControllerStatus

    if ($status -in @("WAITING_USER", "BLOCKED", "PHASE3_COMPLETE")) {
        Write-SupervisorLog "Stopping supervisor because controller status is $status."
        break
    }

    Write-SupervisorLog "Launching/resuming Claude Code with native /goal. Controller status=$status"

    # Current Claude Code supports:
    #   claude -c -p "..."
    # to continue the most recent conversation non-interactively.
    # Auto mode is designed for unattended tool execution with safety checks,
    # avoiding a brittle broad Bash allowlist.
    $rawOutput = & claude -c --permission-mode auto -p $goalPrompt 2>&1
    $exitCode = $LASTEXITCODE

    $rawOutput | Tee-Object -FilePath $LogFile -Append
    $outputText = ($rawOutput | Out-String)

    $status = Get-ControllerStatus
    Write-SupervisorLog "Claude invocation ended. exit=$exitCode controller_status=$status"

    if ($status -in @("WAITING_USER", "BLOCKED", "PHASE3_COMPLETE")) {
        Write-SupervisorLog "Stopping supervisor because controller status is $status."
        break
    }

    if ($outputText -match $quotaPattern) {
        Write-SupervisorLog "Session/usage/rate limit detected. Sleeping $QuotaRetrySeconds seconds before automatic retry."
        Start-Sleep -Seconds $QuotaRetrySeconds
        continue
    }

    if ($exitCode -ne 0) {
        Write-SupervisorLog "Non-quota Claude CLI failure detected. Stopping for inspection."
        exit $exitCode
    }

    # If /goal returned but durable state still says RUNNING, invoke the same
    # conversation again. This covers benign process/turn endings without
    # asking the user for "continue".
    Write-SupervisorLog "Controller still RUNNING; automatically resuming in $NormalResumeDelaySeconds seconds."
    Start-Sleep -Seconds $NormalResumeDelaySeconds
}
