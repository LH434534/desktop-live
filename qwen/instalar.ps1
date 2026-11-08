# instalar.ps1 — Ollama + Qwen 2.5 7B Instruct no Windows, 100% local.
# Rode:  powershell -NoProfile -ExecutionPolicy Bypass -File instalar.ps1
$ErrorActionPreference = 'Stop'
$MODELO = 'qwen2.5:7b-instruct'
$FALLBACK = 'qwen2.5:7b'
$HOST_API = 'http://127.0.0.1:11434'

function Say($m) { Write-Host "[qwen] $m" }

# ── 0. Python (stdlib apenas, nenhum pip é necessário) ───────────────────
Say 'verificando Python...'
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw 'Python 3.9+ não encontrado. Instale em python.org e rode de novo.' }
& python --version

# ── 1. Ollama ───────────────────────────────────────────────────────────
Say 'verificando Ollama...'
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
  Say 'instalando via winget (ID exato Ollama.Ollama)...'
  try {
    winget install -e --id Ollama.Ollama --silent `
      --accept-package-agreements --accept-source-agreements
  } catch {
    Say "winget falhou ($($_.Exception.Message)); usando instalador oficial assinado..."
    irm https://ollama.com/install.ps1 | iex
  }
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path','User')
  $ollama = Get-Command ollama -ErrorAction SilentlyContinue
}
if (-not $ollama) { throw 'Ollama não ficou disponível no PATH.' }
& ollama --version

# ── 2. servidor na 11434 ────────────────────────────────────────────────
Say 'subindo ollama serve...'
$api = $null
try { $api = Invoke-RestMethod "$HOST_API/api/version" -TimeoutSec 4 } catch {}
if (-not $api) {
  Start-Process -FilePath $ollama.Source -ArgumentList 'serve' `
    -WindowStyle Hidden -PassThru | Out-Null
  for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    try { $api = Invoke-RestMethod "$HOST_API/api/version" -TimeoutSec 4; break } catch {}
  }
}
if (-not $api) { throw "Ollama não respondeu em $HOST_API/api/version" }
Say "ollama versão: $($api.version)"

# ── 3. modelo (4.7 GB, quantizado Q4, roda em CPU) ──────────────────────
Say "baixando $MODELO (4.7 GB, pode levar alguns minutos)..."
$ok = $false
& ollama pull $MODELO
if ($LASTEXITCODE -eq 0) { $ok = $true }
if (-not $ok) {
  Say "tag $MODELO indisponível; tentando $FALLBACK..."
  & ollama pull $FALLBACK
  if ($LASTEXITCODE -eq 0) {
    $ok = $true
    python -c "import json,pathlib; p=pathlib.Path('config.json'); d=json.loads(p.read_text(encoding='utf-8')); d['modelo']='$FALLBACK'; p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')"
  }
}
if (-not $ok) { throw 'Nenhum modelo baixou. Verifique disco e conexão.' }
& ollama list

# ── 4. smoke test de tool calling ───────────────────────────────────────
Say 'testando se o modelo reconhece o protocolo de ferramentas...'
& python agente.py --verificar
if ($LASTEXITCODE -ne 0) {
  Say 'AVISO: o modelo não devolveu tool_calls. Atualize o Ollama (>= 0.3.0) e rode de novo.'
} else {
  Say 'tool calling OK.'
}

Say 'PRONTO. Rode INICIAR.bat (ou: python agente.py "sua ordem").'
