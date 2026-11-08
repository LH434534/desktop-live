"""Ferramentas que o Qwen pode chamar para controlar o Windows.

No Windows real: Win32 via ctypes + PowerShell (zero dependências pip).
Fora do Windows: modo SIMULADO, usado apenas pelos testes automatizados.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

WIN = (os.name == "nt")

# ─────────────────────────────────────────────── Win32 (ctypes puro, sem pip)
if WIN:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", PUL)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", PUL)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
    KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def _ps(comando: str, timeout: int = 60) -> str:
    """Executa PowerShell e devolve stdout+stderr."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
    return f"rc={r.returncode}\n{out.strip()}"


# ───────────────────────────────────────────────────────────────────────────
def info_sistema(args: dict) -> str:
    if not WIN:
        return json.dumps({"SIMULADO": True, "so": platform.platform(),
                           "cpus": os.cpu_count(), "usuario": "runner"}, ensure_ascii=False)
    cmd = ("$c=Get-CimInstance Win32_ComputerSystem; "
           "$o=Get-CimInstance Win32_OperatingSystem; "
           "[pscustomobject]@{Hostname=$env:COMPUTERNAME; Usuario=$env:USERNAME; "
           "SO=$o.Caption; Build=$o.BuildNumber; "
           "CPUs=$c.NumberOfLogicalProcessors; "
           "RAM_GB=[math]::Round($c.TotalPhysicalMemory/1GB,2); "
           "RAM_Livre_GB=[math]::Round($o.FreePhysicalMemory/1MB,2)} | ConvertTo-Json -Compress")
    return _ps(cmd)


def executar(args: dict) -> str:
    comando = str(args.get("comando", "")).strip()
    if not comando:
        return "erro: comando vazio"
    timeout = max(5, min(int(args.get("timeout", 60) or 60), 300))
    if not WIN:
        return json.dumps({"SIMULADO": True, "comando": comando[:120], "rc": 0,
                           "saida": "saida simulada do PowerShell"}, ensure_ascii=False)
    try:
        return _ps(comando, timeout)
    except subprocess.TimeoutExpired:
        return f"erro: timeout de {timeout}s"


def listar(args: dict) -> str:
    caminho = str(args.get("caminho", "."))
    if not WIN and not Path(caminho).exists():
        return json.dumps({"SIMULADO": True, "caminho": caminho,
                           "itens": ["config.json", "agente.py", "README.md"]}, ensure_ascii=False)
    try:
        p = Path(caminho)
        itens = []
        for f in sorted(p.iterdir())[:120]:
            itens.append(("dir " if f.is_dir() else "file") + " " + f.name)
        return "\n".join(itens) or "(vazio)"
    except Exception as e:
        return f"erro: {e}"


def ler_arquivo(args: dict) -> str:
    caminho = str(args.get("caminho", ""))
    try:
        t = Path(caminho).read_text(encoding="utf-8", errors="replace")
        return t[:20000]
    except Exception as e:
        return f"erro: {e}"


def escrever_arquivo(args: dict) -> str:
    caminho = str(args.get("caminho", ""))
    conteudo = str(args.get("conteudo", ""))
    if len(conteudo.encode("utf-8")) > 1_000_000:
        return "erro: conteudo acima de 1 MB"
    try:
        p = Path(caminho)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
        return f"ok: {p} ({len(conteudo)} chars)"
    except Exception as e:
        return f"erro: {e}"


def processos(args: dict) -> str:
    n = max(1, min(int(args.get("limite", 15) or 15), 60))
    if not WIN:
        return json.dumps({"SIMULADO": True, "processos": ["ollama", "explorer", "python"]},
                          ensure_ascii=False)
    return _ps(f"Get-Process | Sort-Object CPU -Descending | Select-Object -First {n} "
               "Name,Id,CPU,@{n='RAM_MB';e={[math]::Round($_.WorkingSet64/1MB,1)}} "
               "| Format-Table -AutoSize | Out-String -Width 200")


def janelas(args: dict) -> str:
    if not WIN:
        return json.dumps({"SIMULADO": True,
                           "janelas": [{"titulo": "Windows Terminal", "rect": [0, 0, 1280, 720]}]},
                          ensure_ascii=False)
    achados: list[dict] = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if not buf.value.strip():
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        achados.append({"titulo": buf.value[:160],
                        "rect": [r.left, r.top, r.right, r.bottom]})
        return len(achados) < 60

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return json.dumps(achados, ensure_ascii=False)


def clicar(args: dict) -> str:
    x, y = int(args.get("x", 0)), int(args.get("y", 0))
    if not WIN:
        return json.dumps({"SIMULADO": True, "clique": [x, y]}, ensure_ascii=False)
    user32.SetCursorPos(x, y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return f"ok: clique em ({x},{y})"


def digitar(args: dict) -> str:
    texto = str(args.get("texto", ""))[:500]
    if not WIN:
        return json.dumps({"SIMULADO": True, "digitado": texto}, ensure_ascii=False)
    for ch in texto:
        code = ord(ch)
        down = INPUT(type=INPUT_KEYBOARD,
                     u=_U(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, None)))
        up = INPUT(type=INPUT_KEYBOARD,
                   u=_U(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
        arr = (INPUT * 2)(down, up)
        user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT))
    return f"ok: {len(texto)} caracteres digitados"


TECLAS = {"enter": 0x0D, "tab": 0x09, "esc": 0x1B, "backspace": 0x08,
          "delete": 0x2E, "up": 0x26, "down": 0x28, "left": 0x25,
          "right": 0x27, "win": 0x5B, "space": 0x20}


def tecla(args: dict) -> str:
    nome = str(args.get("tecla", "enter")).lower()
    vk = TECLAS.get(nome)
    if vk is None:
        return f"erro: tecla desconhecida '{nome}'. Use: {', '.join(TECLAS)}"
    if not WIN:
        return json.dumps({"SIMULADO": True, "tecla": nome}, ensure_ascii=False)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 0x0002, 0)
    return f"ok: tecla {nome}"


def abrir(args: dict) -> str:
    alvo = str(args.get("alvo", ""))
    if not alvo:
        return "erro: alvo vazio"
    if not WIN:
        return json.dumps({"SIMULADO": True, "aberto": alvo}, ensure_ascii=False)
    return _ps(f"Start-Process -FilePath '{alvo.replace(chr(39), chr(39)*2)}' "
               "-PassThru | Select-Object Id,ProcessName | ConvertTo-Json -Compress")


def ui_arvore(args: dict) -> str:
    """Árvore de acessibilidade em TEXTO — o Qwen2.5 7B é text-only, não lê pixels."""
    if not WIN:
        return json.dumps({"SIMULADO": True, "elementos": [
            {"nome": "Barra de tarefas", "tipo": "ToolBar"},
            {"nome": "Iniciar", "tipo": "Button"}]}, ensure_ascii=False)
    limite = max(10, min(int(args.get("limite", 120) or 120), 300))
    script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$q = New-Object System.Collections.Generic.Queue[object]
$q.Enqueue(@($root, 0))
$out = New-Object System.Collections.Generic.List[string]
while ($q.Count -gt 0 -and $out.Count -lt {limite}) {{
  $item = $q.Dequeue(); $el = $item[0]; $d = $item[1]
  try {{
    $c = $el.Current
    $r = $c.BoundingRectangle
    $out.Add(('  ' * $d) + $c.ControlType.ProgrammaticName + ' | ' + $c.Name +
             ' | id=' + $c.AutomationId + ' | xy=' + [int]$r.X + ',' + [int]$r.Y)
    if ($d -lt 4) {{
      $child = $walker.GetFirstChild($el)
      while ($null -ne $child) {{ $q.Enqueue(@($child, $d + 1)); $child = $walker.GetNextSibling($child) }}
    }}
  }} catch {{}}
}}
$out -join "`n"
"""
    return _ps(script, timeout=90)


def falar(args: dict) -> str:
    return "mensagem registrada: " + str(args.get("mensagem", ""))[:300]


FUNCOES = {
    "info_sistema": info_sistema,
    "executar": executar,
    "listar": listar,
    "ler_arquivo": ler_arquivo,
    "escrever_arquivo": escrever_arquivo,
    "processos": processos,
    "janelas": janelas,
    "clicar": clicar,
    "digitar": digitar,
    "tecla": tecla,
    "abrir": abrir,
    "ui_arvore": ui_arvore,
    "falar": falar,
}
