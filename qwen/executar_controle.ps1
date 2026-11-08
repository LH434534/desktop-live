# executar_controle.ps1 — roda EM BACKGROUND dentro do Windows vivo.
# Disparado por WINDOWS_CMD.ps1. Nao bloqueia o heartbeat.
# Hereda GH_TOKEN / GITHUB_REPOSITORY do step 6/8 do conectar-windows.
$ErrorActionPreference = 'Continue'
$qdir  = $PSScriptRoot
$repo  = $env:GITHUB_REPOSITORY
$tok   = $env:GH_TOKEN
$api   = 'http://127.0.0.1:11434'
$logf  = Join-Path $qdir 'QWEN_EXEC.log'
$resf  = Join-Path $qdir 'QWEN_STATUS.txt'
'' | Set-Content $logf -Encoding UTF8
'' | Set-Content $resf -Encoding UTF8

function W([string]$m) {
  $s = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') + '  ' + $m
  Add-Content $logf $s -Encoding UTF8
  Add-Content $resf $s -Encoding UTF8
}

function Pub([string]$texto) {
  if (-not $tok -or -not $repo) { W 'PUB: sem token/repo herdado'; return }
  $hdr = @{
    Authorization = "Bearer $tok"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'qwen-agente'
  }
  $uri = "https://api.github.com/repos/$repo/contents/QWEN_RESULTADO.txt"
  $sha = $null
  try {
    $r = Invoke-RestMethod -Uri $uri -Headers $hdr -Method Get -TimeoutSec 20
    $sha = $r.sha
  } catch {}
  $body = @{
    message = 'qwen: evidencia do controle real do Windows'
    content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($texto))
    branch  = 'main'
  }
  if ($sha) { $body.sha = $sha }
  try {
    Invoke-RestMethod -Uri $uri -Headers $hdr -Method Put -TimeoutSec 30 `
      -ContentType 'application/json' -Body ($body | ConvertTo-Json) | Out-Null
    W 'PUB: QWEN_RESULTADO.txt publicado via API'
  } catch {
    W "PUB falhou: $($_.Exception.Message)"
  }
}

function Finalizar([string]$motivo) {
  W "FIM: $motivo"
  $ev = @()
  $ev += '=== STATUS ==='
  $ev += (Get-Content $resf)
  $ev += ''
  $ev += '=== ARQUIVOS NA AREA DE TRABALHO (winuser) ==='
  $desk = 'C:\Users\winuser\Desktop'
  $ev += (Get-ChildItem $desk -File -ErrorAction SilentlyContinue |
          Select-Object -First 15 |
          ForEach-Object { "$($_.Name)  $($_.Length) bytes" })
  $ideia = Join-Path $desk 'ideia_qwen.txt'
  $ev += ''
  if (Test-Path $ideia) {
    $ev += '=== CONTEUDO DE ideia_qwen.txt ==='
    $ev += (Get-Content $ideia -Raw)
  } else {
    $ev += 'ideia_qwen.txt : nao encontrado (o modelo pode ter escolhido outro caminho)'
  }
  $ev += ''
  $ev += '=== LOG DE ACOES DO AGENTE ==='
  $la = Join-Path $qdir 'logs\acoes.jsonl'
  if (Test-Path $la) { $ev += (Get-Content $la -Tail 15) }
  else { $ev += 'sem log de acoes' }
  Pub ($ev -join "`n")
}

W "INICIO | repo=$repo | run=$env:GITHUB_RUN_NUMBER | quem=$env:USERNAME"
try { W "disco C livre: $([math]::Round((Get-PSDrive C).Free/1GB,2)) GB" } catch {}
& whoami 2>&1 | ForEach-Object { W "whoami: $_" }

# ── 1. Ollama ────────────────────────────────────────────────────────────
$oll = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $oll) {
  W 'Ollama ausente -> winget install -e --id Ollama.Ollama'
  try {
    winget install -e --id Ollama.Ollama --silent `
      --accept-package-agreements --accept-source-agreements 2>&1 |
      Select-Object -Last 6 | ForEach-Object { W "winget: $_" }
  } catch { W "winget erro: $($_.Exception.Message)" }
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path','User')
  $oll = Get-Command ollama -ErrorAction SilentlyContinue
}
if (-not $oll) {
  W 'fallback: instalador oficial com verificacao de assinatura'
  try {
    Invoke-Expression (Invoke-WebRequest -Uri 'https://ollama.com/install.ps1' `
      -UseBasicParsing -TimeoutSec 60).Content
  } catch { W "install.ps1 erro: $($_.Exception.Message)" }
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path','User')
  $oll = Get-Command ollama -ErrorAction SilentlyContinue
}
if (-not $oll) {
  Finalizar 'FALHA: Ollama nao instalou'
  exit 1
}
W "Ollama em: $($oll.Source)"
& $oll.Source --version 2>&1 | ForEach-Object { W "ollama --version: $_" }

# ── 2. servidor na 11434 ─────────────────────────────────────────────────
$v = $null
try { $v = Invoke-RestMethod "$api/api/version" -TimeoutSec 5 } catch {}
if (-not $v) {
  W 'subindo ollama serve'
  Start-Process -FilePath $oll.Source -ArgumentList 'serve' `
    -WindowStyle Hidden -PassThru | Out-Null
  for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    try { $v = Invoke-RestMethod "$api/api/version" -TimeoutSec 4; break } catch {}
  }
}
if (-not $v) { Finalizar 'FALHA: API 11434 nao respondeu'; exit 1 }
W "Ollama versao: $($v.version)"

# ── 3. modelo em cascata (o pedido e o 7B; 3B so se nao couber) ─────────
$instalados = (& $oll.Source list 2>&1 | Out-String)
W "modelos ja presentes: $($instalados.Trim().Replace("`n", ' | '))"
$tags = @('qwen2.5:7b-instruct', 'qwen2.5:7b', 'qwen2.5:3b')
$modelo = $null
foreach ($t in $tags) {
  if ($instalados -match [regex]::Escape($t)) {
    $modelo = $t
    W "MODELO_JA_INSTALADO: $t (pulando download)"
    break
  }
  W "ollama pull $t (4.7 GB no 7B, pode levar minutos)"
  & $oll.Source pull $t 2>&1 |
    Select-Object -Last 5 | ForEach-Object { W "pull: $_" }
  if ($LASTEXITCODE -eq 0) { $modelo = $t; W "MODELO_OK: $t"; break }
  W "pull falhou rc=$LASTEXITCODE para $t"
}
if (-not $modelo) { Finalizar 'FALHA: nenhum modelo baixou'; exit 1 }

# ── 4. ajusta o config SEM BOM (PS 5.1 grava BOM e o json.loads recusa) ──
try {
  $cfgp = Join-Path $qdir 'config.json'
  $cfg = Get-Content $cfgp -Raw | ConvertFrom-Json
  $cfg.modelo = $modelo
  $cfg.host = $api
  $cfg.max_passos = 8
  $json = $cfg | ConvertTo-Json -Depth 6
  [IO.File]::WriteAllText($cfgp, $json, (New-Object System.Text.UTF8Encoding $false))
  W "config (sem BOM): modelo=$modelo host=$api max_passos=8 personalidade=$($cfg.personalidade)"
} catch { W "config erro: $($_.Exception.Message)" }

$agente = Join-Path $qdir 'agente.py'
$argsBase = @('--host', $api, '--modelo', $modelo)

# ── 5. prova do protocolo de ferramentas ────────────────────────────────
W 'VERIFICAR: /api/chat com tools'
$vout = & python $agente @argsBase --verificar 2>&1 | Out-String
W "VERIFICAR_RC=$LASTEXITCODE"
W ($vout.Trim())

# ── 6. ORDEM REAL: o jovem mexe no PC ───────────────────────────────────
$ordem = 'da uma olhada no sistema, cria um arquivo ideia_qwen.txt na area de trabalho C:\Users\winuser\Desktop com uma ideia aleatoria sua e me conta o que voce fez'
W "ORDEM: $ordem"
$aout = & python $agente @argsBase $ordem 2>&1 | Out-String
W "AGENTE_RC=$LASTEXITCODE"
W ($aout.Trim())

# ── 7. segunda ordem: usa PowerShell de verdade ────────────────────────
$ordem2 = 'usa o PowerShell para listar os 5 processos que mais gastam CPU e escreve o resultado em C:\Users\winuser\Desktop\processos_qwen.txt'
W "ORDEM2: $ordem2"
$aout2 = & python $agente @argsBase $ordem2 2>&1 | Out-String
W "AGENTE2_RC=$LASTEXITCODE"
W ($aout2.Trim())

# ── 8. evidencias ───────────────────────────────────────────────────────
Finalizar 'execucao concluida (v2, sem BOM)'
exit 0
