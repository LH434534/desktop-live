"""Política local de execução + auditoria.

Todo comando que o modelo pede passa por aqui antes de tocar o Windows.
Nada é enviado para fora da máquina: o log fica em logs/acoes.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# Padrões que exigem confirmação humana (não são proibição: são freio).
PADROES_SENSIVEIS = [
    r"(?i)\bremove-item\b.*(-recurse|-force)",
    r"(?i)\bdel\b.*(/f|/s|/q)",
    r"(?i)\brm\s+-rf\b",
    r"(?i)\bformat-volume\b|\bdiskpart\b|\bcipher\s+/w\b",
    r"(?i)\breg\s+delete\b|\bremove-itemproperty\b",
    r"(?i)\bstop-computer\b|\brestart-computer\b|\bshutdown\b",
    r"(?i)\bbcdedit\b|\bvssadmin\b.*delete",
    r"(?i)\bset-executionpolicy\b.*unrestricted",
    r"(?i)\binvoke-webrequest\b.*(-outfile|>\s)",
    r"(?i)\bset-content\b.*-force\b.*\\windows\\",
    r"(?i)\bstop-process\b.*(-force|\*)",
]

LIMITE_SAIDA = 12_000       # caracteres devolvidos ao modelo por ferramenta
LIMITE_ESCRITA = 1_000_000  # bytes por escrita de arquivo


class Politica:
    def __init__(self, cfg: dict, base: Path, console=print):
        self.cfg = cfg
        self.base = base
        self.console = console
        self.confirmar = bool(cfg.get("confirmar", True))
        self.raiz = cfg.get("raiz")  # None = sem restrição de caminho
        self.log_path = base / "logs" / "acoes.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.total_acoes = 0

    def _sensivel(self, texto: str) -> str | None:
        for p in PADROES_SENSIVEIS:
            if re.search(p, texto or ""):
                return p
        return None

    def _caminho_ok(self, caminho: str) -> tuple[bool, str]:
        if not self.raiz:
            return True, ""
        try:
            alvo = Path(caminho).resolve()
            raiz = Path(self.raiz).resolve()
            if raiz in alvo.parents or alvo == raiz:
                return True, ""
            return False, f"fora da raiz permitida: {raiz}"
        except Exception as e:
            return False, f"caminho inválido: {e}"

    def avaliar(self, nome: str, args: dict) -> tuple[bool, str]:
        """Devolve (permitido, motivo)."""
        self.total_acoes += 1
        if self.total_acoes > int(self.cfg.get("max_acoes", 40)):
            return False, "limite de ações por sessão atingido"

        if nome in ("ler_arquivo", "escrever_arquivo", "listar"):
            ok, motivo = self._caminho_ok(str(args.get("caminho", "")))
            if not ok:
                return False, motivo

        if nome == "executar":
            cmd = str(args.get("comando", ""))
            padrao = self._sensivel(cmd)
            if padrao and self.confirmar:
                self.console(f"\n[SEGURANÇA] comando sensível detectado ({padrao})")
                self.console(f"  {cmd[:300]}")
                try:
                    resp = input("  Confirmar? [s/N] ").strip().lower()
                except EOFError:
                    resp = "n"
                if resp not in ("s", "sim", "y", "yes"):
                    return False, "negado pelo operador"
        return True, ""

    def recortar(self, texto: str) -> str:
        if len(texto) > LIMITE_SAIDA:
            return texto[:LIMITE_SAIDA] + f"\n... [recortado, {len(texto)} chars]"
        return texto

    def registrar(self, nome: str, args: dict, resultado: str, ok: bool,
                  motivo: str = "") -> None:
        linha = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "nome": nome,
            "args": {k: (str(v)[:400]) for k, v in args.items()},
            "ok": ok,
            "motivo": motivo,
            "resultado_len": len(resultado),
            "resultado_head": resultado[:200],
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
