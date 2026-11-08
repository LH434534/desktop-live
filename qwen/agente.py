#!/usr/bin/env python3
"""Qwen 2.5 7B Instruct controlando o Windows, 100% local.

Loop: observar -> pensar (Ollama /api/chat com tools) -> agir -> repetir.
Sem SDK, sem pip, sem nuvem: apenas urllib da stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from seguranca import Politica           # noqa: E402
from ferramentas import FUNCOES         # noqa: E402


def S(nome, descricao, props=None, obrig=None):
    return {"type": "function", "function": {
        "name": nome, "description": descricao,
        "parameters": {"type": "object", "properties": props or {},
                       "required": obrig or []}}}


TOOLS = [
    S("info_sistema", "Devolve hostname, usuário, SO, CPUs e RAM deste Windows."),
    S("executar", "Executa um comando PowerShell e devolve rc, stdout e stderr. Use para quase tudo.",
      {"comando": {"type": "string", "description": "Comando PowerShell completo"},
       "timeout": {"type": "integer", "description": "Segundos, 5 a 300"}}, ["comando"]),
    S("listar", "Lista arquivos e pastas de um caminho.",
      {"caminho": {"type": "string"}}, ["caminho"]),
    S("ler_arquivo", "Lê um arquivo de texto (UTF-8, até 20k chars).",
      {"caminho": {"type": "string"}}, ["caminho"]),
    S("escrever_arquivo", "Cria ou sobrescreve um arquivo de texto (até 1 MB).",
      {"caminho": {"type": "string"}, "conteudo": {"type": "string"}},
      ["caminho", "conteudo"]),
    S("processos", "Lista os processos que mais consomem CPU, com PID e RAM.",
      {"limite": {"type": "integer"}}),
    S("janelas", "Lista janelas visíveis com título e retângulo x1,y1,x2,y2."),
    S("clicar", "Clica com o botão esquerdo na coordenada da tela.",
      {"x": {"type": "integer"}, "y": {"type": "integer"}}, ["x", "y"]),
    S("digitar", "Digita texto na janela que tem foco, via SendInput Unicode (aceita acentos).",
      {"texto": {"type": "string"}}, ["texto"]),
    S("tecla", "Pressiona uma tecla: enter, tab, esc, backspace, delete, up, down, left, right, win, space.",
      {"tecla": {"type": "string"}}, ["tecla"]),
    S("abrir", "Abre um programa, arquivo ou pasta com Start-Process.",
      {"alvo": {"type": "string"}}, ["alvo"]),
    S("ui_arvore", "Devolve a árvore de acessibilidade da tela EM TEXTO (nomes, tipos, IDs, posições). "
      "Use antes de clicar: este modelo é text-only e não enxerga pixels.",
      {"limite": {"type": "integer"}}),
    S("falar", "Encerra com uma mensagem para o operador."),
]

# -- persona ----------------------------------------------------------------
# "jovem" = um garoto no SEU computador, fazendo as coisas de todo dia.
# "tecnico" = o prompt neutro original, se quiser voltar.
REGRAS_DE_OPERACAO = """Regras que você segue mesmo de bom humor (não são burocracia, é pra não estragar o PC):
1. Antes de clicar, chame ui_arvore ou janelas pra saber o que tá na tela. Nunca inventa coordenada.
2. Prefira `executar` (PowerShell) pra coisa de sistema; mouse/teclado só pra janela gráfica.
3. Olha o resultado de cada ferramenta antes da próxima. Deu erro? Corrige, não repete igual.
4. Não inventa caminho, nome de arquivo nem PID. Não sabe? Lista antes.
5. Tudo fica aqui dentro: nada do que você faz sai deste computador.
6. "Aleatório" é o clima, não é licença: mexe no que o operador pediu. Não apaga, não formata,
   não mexe em registro nem em C:\\Windows por conta própria. Comando destrutivo pede confirmação.
7. Quando terminar, chame `falar` com um resumo curto, do seu jeito, em português do Brasil.
8. Responda chamando ferramentas; não escreve plano longo em texto.
9. Para CRIAR ou ESCREVER um arquivo de texto, use `escrever_arquivo` com `caminho` e
   `conteudo`. `executar` so aceita `comando` PowerShell. Nunca misture os dois.
10. Se uma ferramenta devolver erro, corrija os ARGUMENTOS e tente de novo; nao desista
    e nao chame `falar` com a mensagem vazia."""

SYSTEM_JOVEM = """Você é um jovem de 20 anos usando o SEU próprio computador Windows. Não é assistente
de empresa, não é atendente, não é robô de suporte: é o seu PC, a sua mesa, a sua conta.
Você mexe nele como qualquer pessoa da sua idade mexe — abre música enquanto faz outra
coisa, troca o papel de parede, organiza a pasta Downloads que virou uma bagunça, confere
quanto de RAM sobrou, abre um vídeo, procura um arquivo que sumiu, anota uma ideia aleatória
no Bloco de Notas, olha os processos pra ver quem tá comendo a CPU, mexe no tema, abre um
jogo e fecha porque depois vê, baixa uma coisa, desiste, muda de ideia. Curioso, disperso,
irônico, fala baixo, escreve como quem manda mensagem: direto, com gíria leve, sem enrolação
e sem "certamente!". Nunca trata o operador como cliente; é você mesma(o) na frente da tela.

Você tem 13 ferramentas reais e usa elas de verdade, não fica só conversando.

""" + REGRAS_DE_OPERACAO

SYSTEM_TECNICO = """Você é um agente que controla ESTE Windows. O operador autorizou você a agir.
Regras de operação:
1. Antes de clicar, chame ui_arvore ou janelas para saber o que está na tela. Nunca invente coordenadas.
2. Prefira `executar` (PowerShell) para tarefas de sistema; use mouse/teclado só para interfaces gráficas.
3. Observe o resultado de cada ferramenta antes do próximo passo. Se deu erro, corrija, não repita igual.
4. Não invente caminhos, nomes de arquivo nem PIDs. Se não sabe, liste antes.
5. Você é local e privado: nada do que faz sai desta máquina.
6. Mexa apenas no que o operador pediu. Comandos destrutivos pedem confirmação.
7. Quando terminar, chame `falar` com um resumo curto em português do Brasil.
8. Responda sempre chamando ferramentas; não descreva planos em texto longo."""


def system_para(modo: str) -> str:
    return SYSTEM_TECNICO if str(modo).lower() in ("tecnico", "técnico", "tecnica") \
        else SYSTEM_JOVEM


class Ollama:
    def __init__(self, host: str, modelo: str, timeout: int = 600):
        self.host = host.rstrip("/")
        self.modelo = modelo
        self.timeout = timeout

    def chat(self, messages: list, tools=None) -> dict:
        payload = {"model": self.modelo, "messages": messages, "stream": False,
                   "options": {"temperature": 0.2, "num_predict": 256,
                               "top_p": 0.9, "repeat_penalty": 1.1}}
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            self.host + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def versao(self) -> str:
        with urllib.request.urlopen(self.host + "/api/version", timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("version", "?")


def _normalizar_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {"valor": v}
        except Exception:
            return {"valor": raw}
    return {}


def _extrair_chamadas(msg: dict) -> list:
    """tool_calls nativo do Ollama + fallback para JSON que o 7B às vezes escreve no texto."""
    chamadas = []
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        nome = fn.get("name") or ""
        if nome:
            chamadas.append((nome, _normalizar_args(fn.get("arguments"))))
    if chamadas:
        return chamadas
    texto = (msg.get("content") or "").strip()
    bloco = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.S) or \
            re.search(r"(\{[^{}]*\"name\"[^{}]*\})", texto, re.S)
    if bloco:
        try:
            obj = json.loads(bloco.group(1))
            nome = obj.get("name") or obj.get("tool")
            if nome in FUNCOES:
                chamadas.append((nome, _normalizar_args(obj.get("arguments") or obj.get("args"))))
        except Exception:
            pass
    return chamadas


class Agente:
    def __init__(self, cfg: dict, console=print):
        self.cfg = cfg
        self.console = console
        self.ollama = Ollama(cfg.get("host", "http://127.0.0.1:11434"),
                             cfg.get("modelo", "qwen2.5:7b-instruct"),
                             int(cfg.get("timeout", 600)))
        self.politica = Politica(cfg, BASE, console)
        self.dry_run = bool(cfg.get("dry_run", False))
        self.max_passos = int(cfg.get("max_passos", 12))
        self.personalidade = str(cfg.get("personalidade", "jovem"))
        self.system = system_para(self.personalidade)
        self.historico: list = []

    def _despachar(self, nome: str, args: dict) -> str:
        if nome not in FUNCOES:
            return f"erro: ferramenta inexistente '{nome}'. Disponíveis: {', '.join(FUNCOES)}"
        permitido, motivo = self.politica.avaliar(nome, args)
        if not permitido:
            self.politica.registrar(nome, args, motivo, False, motivo)
            return "BLOQUEADO: " + motivo
        if self.dry_run:
            resultado = "[dry-run] não executado: " + json.dumps(args, ensure_ascii=False)[:200]
        else:
            try:
                resultado = FUNCOES[nome](args)
            except Exception as e:
                resultado = f"erro na ferramenta {nome}: {type(e).__name__}: {e}"
        resultado = self.politica.recortar(str(resultado))
        self.politica.registrar(nome, args, resultado, True)
        return resultado

    def rodar(self, instrucao: str) -> str:
        self.historico = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": instrucao},
        ]
        final = "(sem resposta final)"
        for passo in range(1, self.max_passos + 1):
            try:
                resp = self.ollama.chat(self.historico, TOOLS)
            except urllib.error.URLError as e:
                return f"Ollama inacessível em {self.ollama.host}: {e}. Rode INICIAR.bat primeiro."
            msg = resp.get("message") or {}
            chamadas = _extrair_chamadas(msg)
            self.console(f"\n-- passo {passo} --")
            if not chamadas:
                final = (msg.get("content") or "").strip() or final
                self.console("Qwen: " + final[:600])
                return final
            self.historico.append({"role": "assistant",
                                   "content": msg.get("content") or "",
                                   "tool_calls": [
                                       {"function": {"name": n, "arguments": a}}
                                       for n, a in chamadas]})
            for nome, args in chamadas:
                self.console(f"  -> {nome}({json.dumps(args, ensure_ascii=False)[:180]})")
                resultado = self._despachar(nome, args)
                self.console("     " + resultado[:300].replace("\n", " | "))
                self.historico.append({"role": "tool", "name": nome,
                                       "content": resultado})
                if nome == "falar":
                    return str(args.get("mensagem", final))
        return f"limite de {self.max_passos} passos atingido. Último: {final[:300]}"


def carregar_cfg() -> dict:
    p = BASE / "config.json"
    # utf-8-sig: o Set-Content -Encoding UTF8 do PowerShell 5.1 grava BOM,
    # e json.loads com utf-8 puro recusa. Aqui aceita os dois.
    cfg = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    cfg.setdefault("host", "http://127.0.0.1:11434")
    cfg.setdefault("modelo", "qwen2.5:7b-instruct")
    return cfg


def main():
    # O console do runner Windows usa cp1252: acentos ok, mas box-drawing/emoji
    # estouram com UnicodeEncodeError. Reconfigura antes de imprimir qualquer coisa.
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Qwen 2.5 7B controlando o Windows")
    ap.add_argument("instrucao", nargs="*", help="O que fazer; vazio = modo interativo")
    ap.add_argument("--host", help="URL do Ollama")
    ap.add_argument("--modelo", help="Tag do modelo")
    ap.add_argument("--dry-run", action="store_true", help="Mostra as ações sem executar")
    ap.add_argument("--livre", action="store_true", help="Desliga confirmação de comandos sensíveis")
    ap.add_argument("--personalidade", choices=["jovem", "tecnico"],
                    help="jovem (padrão) = garoto no próprio PC; tecnico = prompt neutro")
    ap.add_argument("--verificar", action="store_true", help="Só checa Ollama e tool calling")
    ns = ap.parse_args()

    cfg = carregar_cfg()
    if ns.host:
        cfg["host"] = ns.host
    if ns.modelo:
        cfg["modelo"] = ns.modelo
    if ns.dry_run:
        cfg["dry_run"] = True
    if ns.livre:
        cfg["confirmar"] = False
    if ns.personalidade:
        cfg["personalidade"] = ns.personalidade

    ag = Agente(cfg)

    if ns.verificar:
        try:
            print("ollama versão:", ag.ollama.versao())
        except Exception as e:
            print("FALHA: Ollama não responde:", e)
            sys.exit(1)
        r = ag.ollama.chat([{"role": "user", "content": "Liste a pasta atual."}], TOOLS)
        calls = _extrair_chamadas(r.get("message") or {})
        print("tool_calls:", [n for n, _ in calls] or "NENHUM — modelo não reconheceu o protocolo")
        sys.exit(0 if calls else 2)

    if ns.instrucao:
        ag.rodar(" ".join(ns.instrucao))
        return
    print("Qwen no comando do Windows. Ctrl+C para sair.")
    while True:
        try:
            linha = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\naté logo.")
            return
        if linha.lower() in ("sair", "exit", "quit"):
            return
        if linha:
            ag.rodar(linha)


if __name__ == "__main__":
    main()
