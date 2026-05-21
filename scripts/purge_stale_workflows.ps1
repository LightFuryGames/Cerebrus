<#
.SYNOPSIS
    Purge stale (orphaned) GitHub Actions workflows from this repo.

.DESCRIPTION
    GitHub keeps workflow entries (and the sidebar listing) alive as long
    as the workflow has any run history, even after the .yml file is
    deleted from the repo. There is no UI button to remove an orphan
    workflow; the only way is to delete every run, after which GitHub
    auto-prunes the workflow.

    This script:
      1. Lists every workflow in the repo.
      2. Filters to the kill list ($StaleWorkflowNames).
      3. Deletes every run for those workflows via the REST API.

    Defaults to dry-run. Pass -Execute to actually delete.

.PARAMETER Repo
    "<owner>/<repo>", e.g. "rahul-gupta-lightfury/Cerebrus".

.PARAMETER StaleWorkflowNames
    Workflow display names (the `name:` field in the YAML, or the label
    shown in the Actions sidebar) to purge. Matching is case-insensitive
    and exact.

.PARAMETER Execute
    Without this switch the script lists what it WOULD delete and exits.
    With it, each run is DELETE'd. Cannot be undone.

.EXAMPLE
    # Dry run (default) -- shows counts, deletes nothing
    pwsh ./scripts/purge_stale_workflows.ps1

    # Actually delete
    pwsh ./scripts/purge_stale_workflows.ps1 -Execute
#>

[CmdletBinding()]
param(
    [string]$Repo = "LightFuryGames/Cerebrus",
    [string[]]$StaleWorkflowNames = @("CI", "Linting", "UnitTests"),
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

# --- Preflight ---------------------------------------------------------------

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI not on PATH. Install GitHub CLI and run 'gh auth login'."
    exit 1
}

$authState = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "gh is not authenticated. Run 'gh auth login' first.`n$authState"
    exit 1
}

Write-Host "Repo:               $Repo"
Write-Host "Workflows to purge: $($StaleWorkflowNames -join ', ')"
Write-Host "Mode:               $([string]::Concat(@('DRY RUN','EXECUTE')[$Execute.IsPresent]))"
Write-Host ""

# --- Resolve workflow IDs ----------------------------------------------------

$workflowsJson = gh api --paginate "repos/$Repo/actions/workflows"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to list workflows for $Repo."
    exit 1
}

# gh api --paginate concatenates JSON objects; parse each independently and
# flatten the .workflows arrays.
$workflows = @()
foreach ($chunk in ($workflowsJson -split '(?<=\})\s*(?=\{)')) {
    if (-not $chunk.Trim()) { continue }
    $obj = $chunk | ConvertFrom-Json
    if ($obj.workflows) { $workflows += $obj.workflows }
}

if (-not $workflows) {
    Write-Error "No workflows returned for $Repo. Check the repo slug."
    exit 1
}

$targets = $workflows | Where-Object {
    $StaleWorkflowNames -contains $_.name
}

if (-not $targets) {
    Write-Host "No matching workflows. Sidebar already clean -- nothing to do."
    Write-Host "All workflows currently registered:"
    $workflows | ForEach-Object { Write-Host "  - $($_.name)  (id=$($_.id), state=$($_.state), path=$($_.path))" }
    exit 0
}

Write-Host "Targets:"
$targets | ForEach-Object {
    Write-Host ("  - {0,-15} id={1}  state={2}  path={3}" -f $_.name, $_.id, $_.state, $_.path)
}
Write-Host ""

# --- Per-workflow purge ------------------------------------------------------

foreach ($wf in $targets) {
    Write-Host "=== $($wf.name) (id=$($wf.id)) ===" -ForegroundColor Cyan

    $runsJson = gh api --paginate "repos/$Repo/actions/workflows/$($wf.id)/runs?per_page=100"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to list runs for workflow $($wf.id); skipping."
        continue
    }

    $runIds = @()
    foreach ($chunk in ($runsJson -split '(?<=\})\s*(?=\{)')) {
        if (-not $chunk.Trim()) { continue }
        $obj = $chunk | ConvertFrom-Json
        if ($obj.workflow_runs) {
            $runIds += $obj.workflow_runs | ForEach-Object { $_.id }
        }
    }

    Write-Host "  Runs found: $($runIds.Count)"
    if ($runIds.Count -eq 0) {
        Write-Host "  Nothing to delete."
        continue
    }

    if (-not $Execute) {
        Write-Host "  [DRY RUN] would DELETE $($runIds.Count) runs."
        continue
    }

    $i = 0
    foreach ($runId in $runIds) {
        $i++
        Write-Progress -Activity "Deleting runs for $($wf.name)" `
                       -Status "$i / $($runIds.Count)" `
                       -PercentComplete (($i / [Math]::Max($runIds.Count,1)) * 100)
        gh api -X DELETE "repos/$Repo/actions/runs/$runId" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "  Run $runId delete failed; continuing."
        }
    }
    Write-Progress -Activity "Deleting runs for $($wf.name)" -Completed
    Write-Host "  Deleted $i runs. Workflow entry will disappear from the sidebar within a minute."
}

Write-Host ""
if (-not $Execute) {
    Write-Host "Dry run complete. Re-run with -Execute to actually delete." -ForegroundColor Yellow
} else {
    Write-Host "Done. Refresh the Actions sidebar in VS Code to verify cleanup." -ForegroundColor Green
}
