$ErrorActionPreference = 'Continue'
# v3: SEM git commit/push aqui. O step 6 ja publica o heartbeat sozinho;
# fazer git dentro do gancho travou o loop na v1 (rebase disputando com a API).
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
"DNS_FIXO_LOCAL : $dns (sem commit: o heartbeat publica)"

# --- QWEN 2.5 7B: dispara o controle real UMA vez, em BACKGROUND ---
Remove-Item (Join-Path $env:TEMP 'qwen_controle_disparado.flag') -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:TEMP 'qwen_controle_v2.flag') -ErrorAction SilentlyContinue
$qflag = Join-Path $env:TEMP 'qwen_controle_v3.flag'
if (-not (Test-Path $qflag)) {
  $job = Join-Path $PSScriptRoot 'qwen\executar_controle.ps1'
  if (Test-Path $job) {
    Set-Content $qflag $stamp -Encoding UTF8
    $so = Join-Path $PSScriptRoot 'qwen\QWEN_STDOUT.log'
    $se = Join-Path $PSScriptRoot 'qwen\QWEN_STDERR.log'
    $p = Start-Process powershell -WindowStyle Hidden -PassThru `
      -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$job`"") `
      -RedirectStandardOutput $so -RedirectStandardError $se
    "QWEN_DISPARADO_V3 : pid=$($p.Id) job=$job"
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
        "tentativa     : 3 (boot limpo, sem git no gancho, handles fechados)",
        "token_herdado : $([bool]$env:GH_TOKEN)"
      ) -join "`n"
      $b = @{
        message = 'qwen: gancho v3 executado'
        content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($txt))
        branch  = 'main'
      }
      if ($sha) { $b.sha = $sha }
      Invoke-RestMethod -Uri $uri -Headers $hdr -Method Put -TimeoutSec 20 `
        -ContentType 'application/json' -Body ($b | ConvertTo-Json) | Out-Null
      "QWEN_SINAL_PUBLICADO_V3 : pid=$($p.Id)"
    } catch {
      "QWEN_SINAL_FALHOU : $($_.Exception.Message)"
    }
  } else {
    "QWEN_AGUARDANDO : $job ainda nao chegou no checkout"
  }
} else {
  "QWEN_JA_DISPARADO_V3 : flag em $qflag"
}
exit 0
