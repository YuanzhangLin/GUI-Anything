param(
  [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $repoRoot 'backend'
$acceptanceRoot = Join-Path $env:RUNNER_TEMP 'gui-anything-clean-acceptance'
$env:GUI_MANAGED_TOOLS_DIR = Join-Path $acceptanceRoot 'managed-tools'
$serviceLog = Join-Path $acceptanceRoot 'local-services.log'
$serviceErrorLog = Join-Path $acceptanceRoot 'local-services-error.log'
$modelLog = Join-Path $acceptanceRoot 'acceptance-model.log'
$modelErrorLog = Join-Path $acceptanceRoot 'acceptance-model-error.log'
$chatOutput = Join-Path $acceptanceRoot 'conversation.ndjson'
$chatBody = Join-Path $acceptanceRoot 'conversation.json'

New-Item -ItemType Directory -Force -Path $acceptanceRoot | Out-Null

if (Get-Command opencode -ErrorAction SilentlyContinue) {
  throw 'Clean-machine acceptance requires OpenCode to be absent from PATH before managed installation.'
}

Push-Location $backendRoot
$service = $null
$modelService = $null
try {
  $installJson = & $Python -c "import json; from app.opencode_install import install; print(json.dumps(install()))"
  if ($LASTEXITCODE -ne 0) { throw 'Managed OpenCode installation failed.' }
  $install = $installJson | ConvertFrom-Json
  if ($install.reused -or -not $install.managed) { throw 'Acceptance did not perform a fresh managed installation.' }
  if (-not $install.path.StartsWith($env:GUI_MANAGED_TOOLS_DIR, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Managed OpenCode escaped the isolated tool directory: $($install.path)"
  }

  New-Item -ItemType Directory -Force -Path (Join-Path $backendRoot 'repos\activitydiary') | Out-Null
  $env:GUI_ACCEPTANCE_PROVIDER_URL = 'http://127.0.0.1:18080/v1'
  $modelService = Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','scripts.mock_openai_server:app','--host','127.0.0.1','--port','18080' -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $modelLog -RedirectStandardError $modelErrorLog
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($modelService.HasExited) { throw "Loopback acceptance model exited early with code $($modelService.ExitCode)." }
    try { if ((Invoke-RestMethod -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 2).ok) { break } } catch { Start-Sleep -Seconds 1 }
    if ($attempt -eq 29) { throw 'Loopback acceptance model did not become ready.' }
  }
  $service = Start-Process -FilePath $Python -ArgumentList '-m','app.local_services' -WorkingDirectory $backendRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $serviceLog -RedirectStandardError $serviceErrorLog

  $ready = $false
  for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ($service.HasExited) { throw "Paired local services exited early with code $($service.ExitCode)." }
    try {
      $me = Invoke-RestMethod -Uri 'http://127.0.0.1:8002/api/me' -TimeoutSec 3
      if ($me.username -eq 'local') { $ready = $true; break }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $ready) { throw 'Backend did not become ready within 90 seconds.' }

  $registrationReady = $false
  for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ($service.HasExited) { throw "Paired local services exited during registration with code $($service.ExitCode)." }
    $startupLog = if (Test-Path $serviceLog) { Get-Content -Raw $serviceLog } else { '' }
    $toolsReady = $startupLog -match "OpenCode device tools registered: \['gui_act', 'gui_observe', 'gui_verify'\]"
    $skillReady = $startupLog -match 'GUI-Anything skill registered: True'
    if ($toolsReady -and $skillReady) { $registrationReady = $true; break }
    Start-Sleep -Seconds 1
  }
  if (-not $registrationReady) { throw 'Paired launcher did not finish GUI tool and Skill registration within 90 seconds.' }

  $settings = Invoke-RestMethod -Uri 'http://127.0.0.1:8002/api/conversation-settings' -TimeoutSec 15
  $provider = $settings.providers | Where-Object { $_.id -eq 'acceptance' -and $_.connected } | Select-Object -First 1
  if (-not $provider) { throw 'Loopback acceptance provider is not connected through OpenCode.' }
  $model = $provider.models | Where-Object { $_.id -eq 'acceptance-model' } | Select-Object -First 1
  if (-not $model) { throw 'Loopback acceptance provider exposed no deterministic model.' }

  $sessionId = [guid]::NewGuid().ToString()
  $payload = @{
    username = 'local'
    session_id = $sessionId
    project_id = 'activitydiary'
    app_id = 'activitydiary'
    provider = 'opencode'
    model = @{ providerID = 'acceptance'; modelID = $model.id }
    message = 'Before answering, call the skill tool to load gui-anything. After it loads, reply with exactly CLEAN_MACHINE_OK.'
  } | ConvertTo-Json -Depth 8 -Compress
  Set-Content -LiteralPath $chatBody -Value $payload -Encoding utf8NoBOM
  & curl.exe -sS --fail --max-time 90 -o $chatOutput -H 'Content-Type: application/json' --data-binary "@$chatBody" 'http://127.0.0.1:8002/api/chat'
  if ($LASTEXITCODE -ne 0) { throw 'First managed OpenCode conversation failed.' }

  $events = Invoke-RestMethod -Uri "http://127.0.0.1:8002/api/conversations/$sessionId/events?after=0" -TimeoutSec 15
  $skillCompleted = $events.events | Where-Object { $_.kind -eq 'tool' -and $_.tool -eq 'skill' -and $_.state -eq 'completed' }
  $reply = ($events.events | Where-Object { $_.kind -in @('text_snapshot','text_delta') } | ForEach-Object { $_.text }) -join "`n"
  $finished = $events.events | Where-Object { $_.kind -eq 'turn_finished' }
  if (-not $skillCompleted) { throw 'The first conversation did not complete a gui-anything Skill tool call.' }
  if ($reply -notmatch 'CLEAN_MACHINE_OK') { throw 'The first conversation did not return the fixed acceptance reply.' }
  if (-not $finished) { throw 'The first conversation did not reach turn_finished.' }

  Write-Output "CLEAN_MACHINE_ACCEPTANCE_OK version=$($install.version) model=acceptance/$($model.id) session=$sessionId"
} catch {
  $message = ($_.Exception.Message -replace '[\r\n]+',' ' -replace '%','%25').Trim()
  Write-Host "::error title=Clean machine acceptance::$message"
  throw
} finally {
  if ($service -and -not $service.HasExited) { Stop-Process -Id $service.Id -Force -ErrorAction SilentlyContinue }
  if ($modelService -and -not $modelService.HasExited) { Stop-Process -Id $modelService.Id -Force -ErrorAction SilentlyContinue }
  foreach ($port in 4096,8002,18080) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique |
      ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  }
  if (Test-Path $serviceLog) { Get-Content $serviceLog }
  if (Test-Path $serviceErrorLog) { Get-Content $serviceErrorLog }
  if (Test-Path $modelLog) { Get-Content $modelLog }
  if (Test-Path $modelErrorLog) { Get-Content $modelErrorLog }
  Pop-Location
}
