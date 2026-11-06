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
$chatOutput = Join-Path $acceptanceRoot 'conversation.ndjson'
$chatBody = Join-Path $acceptanceRoot 'conversation.json'

New-Item -ItemType Directory -Force -Path $acceptanceRoot | Out-Null

if (Get-Command opencode -ErrorAction SilentlyContinue) {
  throw 'Clean-machine acceptance requires OpenCode to be absent from PATH before managed installation.'
}

Push-Location $backendRoot
$service = $null
try {
  $installJson = & $Python -c "import json; from app.opencode_install import install; print(json.dumps(install()))"
  if ($LASTEXITCODE -ne 0) { throw 'Managed OpenCode installation failed.' }
  $install = $installJson | ConvertFrom-Json
  if ($install.reused -or -not $install.managed) { throw 'Acceptance did not perform a fresh managed installation.' }
  if (-not $install.path.StartsWith($env:GUI_MANAGED_TOOLS_DIR, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Managed OpenCode escaped the isolated tool directory: $($install.path)"
  }

  New-Item -ItemType Directory -Force -Path (Join-Path $backendRoot 'repos\activitydiary') | Out-Null
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

  $startupLog = Get-Content -Raw $serviceLog
  if ($startupLog -notmatch "OpenCode device tools registered: \['gui_act', 'gui_observe', 'gui_verify'\]") {
    throw 'Paired launcher did not register all explicit GUI device tools.'
  }
  if ($startupLog -notmatch 'GUI-Anything skill registered: True') {
    throw 'Paired launcher did not register the GUI-Anything Skill.'
  }

  $settings = Invoke-RestMethod -Uri 'http://127.0.0.1:8002/api/conversation-settings' -TimeoutSec 15
  $provider = $settings.providers | Where-Object { $_.id -eq 'opencode' -and $_.connected } | Select-Object -First 1
  if (-not $provider) { throw 'OpenCode free provider is not connected on the clean runner.' }
  $model = $provider.models | Where-Object { $_.id -match 'free' } | Select-Object -First 1
  if (-not $model) { $model = $provider.models | Select-Object -First 1 }
  if (-not $model) { throw 'OpenCode free provider exposed no model.' }

  $sessionId = [guid]::NewGuid().ToString()
  $payload = @{
    username = 'local'
    session_id = $sessionId
    project_id = 'activitydiary'
    app_id = 'activitydiary'
    provider = 'opencode'
    model = @{ providerID = 'opencode'; modelID = $model.id }
    message = 'Before answering, call the skill tool to load gui-anything. After it loads, reply with exactly CLEAN_MACHINE_OK.'
  } | ConvertTo-Json -Depth 8 -Compress
  Set-Content -LiteralPath $chatBody -Value $payload -Encoding utf8NoBOM
  & curl.exe -sS --fail --max-time 240 -o $chatOutput -H 'Content-Type: application/json' --data-binary "@$chatBody" 'http://127.0.0.1:8002/api/chat'
  if ($LASTEXITCODE -ne 0) { throw 'First managed OpenCode conversation failed.' }

  $events = Invoke-RestMethod -Uri "http://127.0.0.1:8002/api/conversations/$sessionId/events?after=0" -TimeoutSec 15
  $skillCompleted = $events.events | Where-Object { $_.kind -eq 'tool' -and $_.tool -eq 'skill' -and $_.state -eq 'completed' }
  $reply = ($events.events | Where-Object { $_.kind -in @('text_snapshot','text_delta') } | ForEach-Object { $_.text }) -join "`n"
  $finished = $events.events | Where-Object { $_.kind -eq 'turn_finished' }
  if (-not $skillCompleted) { throw 'The first conversation did not complete a gui-anything Skill tool call.' }
  if ($reply -notmatch 'CLEAN_MACHINE_OK') { throw 'The first conversation did not return the fixed acceptance reply.' }
  if (-not $finished) { throw 'The first conversation did not reach turn_finished.' }

  Write-Output "CLEAN_MACHINE_ACCEPTANCE_OK version=$($install.version) model=opencode/$($model.id) session=$sessionId"
} finally {
  if ($service -and -not $service.HasExited) { Stop-Process -Id $service.Id -Force -ErrorAction SilentlyContinue }
  foreach ($port in 4096,8002) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique |
      ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  }
  if (Test-Path $serviceLog) { Get-Content $serviceLog }
  if (Test-Path $serviceErrorLog) { Get-Content $serviceErrorLog }
  Pop-Location
}
