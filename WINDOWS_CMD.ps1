$ErrorActionPreference = 'Continue'
$ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
$ip  = (& $ts ip -4 | Select-Object -First 1)
$dns = try { (& $ts status --json | ConvertFrom-Json).Self.DNSName } catch { '' }
if (-not $dns) { $dns = $ip }
$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ'
@(
  "# ENDERECO FIXO — lido de DENTRO do seu Windows",
  "data_utc  : $stamp",
  "run       : $env:GITHUB_RUN_NUMBER",
  "Host FIXO : $dns",
  "IP atual  : $ip",
  "Porta     : 3389",
  "Usuario   : winuser",
  "Nota      : o IP muda a cada boot; ESTE NOME nao muda.",
  "App       : Windows App / RD Client -> campo NOME DO COMPUTADOR",
  "Requisito : Tailscale ativo no celular, mesma conta"
) | Set-Content DNS_FIXO.txt -Encoding UTF8
$f = 'CONECTAR_WINDOWS.txt'
if (Test-Path $f) {
  $c = Get-Content $f
  if (-not ($c -match '^Host FIXO')) {
    $c = $c -replace '^(Address       : .+)$', "`$1`r`nHost FIXO     : $dns"
    $c | Set-Content $f -Encoding UTF8
  }
}
git config user.name dns-fixo
git config user.email dns-fixo@localhost
git add DNS_FIXO.txt CONECTAR_WINDOWS.txt 2>&1 | Out-Null
git commit -m "dns fixo $dns" 2>&1 | Out-Null
for ($i=0; $i -lt 4; $i++) {
  git pull --rebase -X theirs origin main 2>&1 | Out-Null
  git push origin HEAD:main 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { break }
  Start-Sleep -Seconds 3
}
"DNS_FIXO_PUBLICADO : $dns"

# --- QWEN 2.5 7B: dispara o controle real UMA unica vez, em BACKGROUND ---
# O trabalho pesado (instalar + baixar 4.7 GB + rodar o agente) roda em
# processo separado para NAO bloquear o heartbeat de 10 min.
# v2: flag novo, porque a v1 ja disparou e o BOM quebrou o agente
Remove-Item (Join-Path $env:TEMP 'qwen_controle_disparado.flag') -ErrorAction SilentlyContinue
$qflag = Join-Path $env:TEMP 'qwen_controle_v2.flag'
if (-not (Test-Path $qflag)) {
  $job = Join-Path $PSScriptRoot 'qwen\executar_controle.ps1'
  if (Test-Path $job) {
    Set-Content $qflag (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') -Encoding UTF8
    $so = Join-Path $PSScriptRoot 'qwen\QWEN_STDOUT.log'
    $se = Join-Path $PSScriptRoot 'qwen\QWEN_STDERR.log'
    $p = Start-Process powershell -WindowStyle Hidden -PassThru `
      -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$job`"") `
      -RedirectStandardOutput $so -RedirectStandardError $se
    "QWEN_DISPARADO : pid=$($p.Id) job=$job"
    try {
      $hdr = @{
        Authorization = "Bearer $env:GH_TOKEN"
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'qwen-gancho'
      }
      $uri = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/contents/QWEN_DISPARO.txt"
      $sha = $null
      try {
        $sha = (Invoke-RestMethod -Uri $uri -Headers $hdr -Method Get -TimeoutSec 15).sha
      } catch {}
      $txt = @(
        "disparado_utc : $stamp",
        "pid           : $($p.Id)",
        "run           : $env:GITHUB_RUN_NUMBER",
        "job           : $job",
        "token_herdado : $([bool]$env:GH_TOKEN)",
        "tentativa     : 2 (correcao do BOM UTF-8)"
      ) -join "`n"
      $b = @{
        message = 'qwen: gancho v2 executado (correcao BOM)'
        content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($txt))
        branch  = 'main'
      }
      if ($sha) { $b.sha = $sha }
      Invoke-RestMethod -Uri $uri -Headers $hdr -Method Put -TimeoutSec 20 `
        -ContentType 'application/json' -Body ($b | ConvertTo-Json) | Out-Null
      "QWEN_SINAL_PUBLICADO : pid=$($p.Id)"
    } catch {
      "QWEN_SINAL_FALHOU : $($_.Exception.Message)"
    }
  } else {
    "QWEN_AGUARDANDO : $job ainda nao chegou no checkout"
  }
} else {
  "QWEN_JA_DISPARADO : flag em $qflag"
}
exit 0
