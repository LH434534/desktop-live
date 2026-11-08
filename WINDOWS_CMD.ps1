$ErrorActionPreference = 'Continue'
# v6: traz os scripts corrigidos DIRETO da API (o checkout do run pode ser antigo),
# grava os bytes UTF-8 sem BOM e re-dispara o controle. Nao reinicia nada.
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
"DNS_FIXO_LOCAL : $dns"

# --- 1. versao corrigida sem depender do checkout ---
$hj = @{
  Authorization = "Bearer $env:GH_TOKEN"
  Accept = 'application/vnd.github+json'
  'User-Agent' = 'qwen-v5'
  'X-GitHub-Api-Version' = '2022-11-28'
}
$qdir = Join-Path $PSScriptRoot 'qwen'
New-Item -ItemType Directory -Force -Path $qdir | Out-Null
$baixados = 0
foreach ($nome in @('agente.py','executar_controle.ps1','ferramentas.py','seguranca.py','config.json')) {
  try {
    $uri = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/contents/qwen/$nome"
    $r = Invoke-RestMethod -Uri $uri -Headers $hj -Method Get -TimeoutSec 25
    $bytes = [Convert]::FromBase64String(($r.content -replace '\s',''))
    [IO.File]::WriteAllBytes((Join-Path $qdir $nome), $bytes)
    $baixados++
  } catch { "QWEN_DOWNLOAD_FALHOU $nome : $($_.Exception.Message)" }
}
"QWEN_SCRIPTS_VIA_API : $baixados/5 (bytes UTF-8, sem BOM)"

# --- 2. re-dispara uma unica vez ---
$kitHash = (Get-FileHash (Join-Path $qdir 'agente.py') -Algorithm SHA256).Hash
$flagDir = Join-Path $env:TEMP 'qwen_kit_flags'
New-Item -ItemType Directory -Force -Path $flagDir | Out-Null
$qflag = Join-Path $flagDir "$kitHash.flag"
"QWEN_KIT_HASH : $kitHash  flag=$qflag"

if (-not (Test-Path $qflag)) {
  $job = Join-Path $qdir 'executar_controle.ps1'
  if (Test-Path $job) {
    Set-Content $qflag $stamp -Encoding UTF8
    $so = Join-Path $qdir 'QWEN_STDOUT.log'
    $se = Join-Path $qdir 'QWEN_STDERR.log'
    $p = Start-Process powershell -WindowStyle Hidden -PassThru `
      -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$job`"") `
      -RedirectStandardOutput $so -RedirectStandardError $se
    "QWEN_DISPARADO_KIT : pid=$($p.Id)"
    try {
      $u = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/contents/QWEN_DISPARO.txt"
      $sha = $null
      try { $sha = (Invoke-RestMethod -Uri $u -Headers $hj -Method Get -TimeoutSec 15).sha } catch {}
      $txt = @("disparado_utc : $stamp","pid : $($p.Id)","run : $env:GITHUB_RUN_NUMBER",
               "tentativa : 6 (kit por hash, fallback de ferramenta)","scripts_baixados : $baixados") -join "`n"
      $b = @{ message='qwen: kit final disparado'; content=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($txt)); branch='main' }
      if ($sha) { $b.sha = $sha }
      Invoke-RestMethod -Uri $u -Headers $hj -Method Put -TimeoutSec 20 -ContentType 'application/json' -Body ($b | ConvertTo-Json) | Out-Null
      "QWEN_SINAL_PUBLICADO_KIT"
    } catch { "QWEN_SINAL_FALHOU : $($_.Exception.Message)" }
  } else { "QWEN_AGUARDANDO : $job nao existe" }
} else { "QWEN_JA_DISPARADO_KIT : flag em $qflag" }
exit 0
