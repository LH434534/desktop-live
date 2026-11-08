#!/usr/bin/env python3
"""Testes reais do loop agêntico, com um servidor Ollama falso em localhost.

Roda em qualquer SO (as ferramentas entram em modo SIMULADO fora do Windows).
Valida: protocolo de tools, despacho, bloqueio, escrita, log e resposta final.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from agente import Agente, TOOLS, _extrair_chamadas, _normalizar_args  # noqa: E402
from seguranca import Politica                                          # noqa: E402


def tc(nome, args=None):
    return {"function": {"name": nome, "arguments": args or {}}}


RESPOSTAS = [
    {"message": {"role": "assistant", "content": "",
                 "tool_calls": [tc("info_sistema"), tc("janelas")]}},
    {"message": {"role": "assistant", "content": "",
                 "tool_calls": [tc("executar", {"comando": "Remove-Item -Recurse -Force C:\\temp"})]}},
    {"message": {"role": "assistant", "content": "",
                 "tool_calls": [tc("escrever_arquivo", {"__PATH__": True})]}},
    {"message": {"role": "assistant", "content": "",
                 "tool_calls": [tc("falar", {"mensagem": "tarefa concluida"})]}},
]

REQUISICOES: list[dict] = []
ARQ_TEMP = ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"version": "0.0-mock"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n).decode("utf-8"))
        REQUISICOES.append(payload)
        idx = min(len(REQUISICOES) - 1, len(RESPOSTAS) - 1)
        resp = json.loads(json.dumps(RESPOSTAS[idx]))
        for call in resp["message"].get("tool_calls", []):
            a = call["function"].get("arguments") or {}
            if a.get("__PATH__"):
                call["function"]["arguments"] = {
                    "caminho": ARQ_TEMP, "conteudo": "escrito pelo Qwen\nlinha 2"}
        self._send(resp)


class TestaAgente(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global ARQ_TEMP
        cls.tmp = tempfile.TemporaryDirectory()
        ARQ_TEMP = str(Path(cls.tmp.name) / "saida.txt")
        cls.srv = HTTPServer(("127.0.0.1", 0), Handler)
        cls.porta = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        REQUISICOES.clear()
        self.cfg = {
            "host": f"http://127.0.0.1:{self.porta}", "modelo": "mock",
            "max_passos": 8, "max_acoes": 40, "timeout": 10,
            "confirmar": True, "raiz": None, "dry_run": False,
        }
        self.log = BASE / "logs" / "acoes.jsonl"
        if self.log.exists():
            self.log.unlink()

    def _rodar(self):
        buf = io.StringIO()
        with redirect_stdout(buf), patch("builtins.input", return_value="n"):
            ag = Agente(self.cfg, console=lambda *a: print(*a))
            retorno = ag.rodar("verifique o sistema e escreva um arquivo")
        return ag, retorno, buf.getvalue()

    def test_01_schema_das_ferramentas(self):
        self.assertEqual(len(TOOLS), 13)
        for t in TOOLS:
            self.assertEqual(t["type"], "function")
            f = t["function"]
            self.assertTrue(f["name"])
            self.assertTrue(f["description"])
            self.assertEqual(f["parameters"]["type"], "object")
            self.assertIsInstance(f["parameters"]["properties"], dict)

    def test_02_normalizacao_e_fallback(self):
        self.assertEqual(_normalizar_args('{"x": 1}'), {"x": 1})
        self.assertEqual(_normalizar_args({"x": 2}), {"x": 2})
        self.assertEqual(_normalizar_args("texto cru"), {"valor": "texto cru"})
        # 7B às vezes devolve JSON no conteúdo em vez de tool_calls
        msg = {"content": 'vou chamar ```json\n{"name":"janelas","arguments":{}}\n```'}
        self.assertEqual(_extrair_chamadas(msg), [("janelas", {})])
        self.assertEqual(_extrair_chamadas({"tool_calls": [tc("janelas")]}),
                         [("janelas", {})])

    def test_03_loop_completo(self):
        ag, retorno, saida = self._rodar()
        self.assertEqual(retorno, "tarefa concluida")
        self.assertEqual(len(REQUISICOES), 4, "deveria haver 4 rodadas de chat")
        for r in REQUISICOES:
            self.assertEqual(r["model"], "mock")
            self.assertEqual(len(r["tools"]), 13)
            self.assertFalse(r["stream"])
        # 2ª rodada recebeu os resultados das 2 primeiras ferramentas
        tools_vistos = [m for m in REQUISICOES[1]["messages"] if m["role"] == "tool"]
        self.assertEqual([m["name"] for m in tools_vistos],
                         ["info_sistema", "janelas"])
        self.assertIn("SIMULADO", tools_vistos[0]["content"])
        # 3ª rodada viu o BLOQUEADO
        bloqueio = [m for m in REQUISICOES[2]["messages"]
                    if m["role"] == "tool" and m["name"] == "executar"]
        self.assertTrue(bloqueio)
        self.assertIn("BLOQUEADO", bloqueio[0]["content"])
        self.assertIn("[SEGURANÇA]", saida)

    def test_04_escrita_real_e_log(self):
        self._rodar()
        self.assertTrue(Path(ARQ_TEMP).exists(), "arquivo não foi escrito")
        self.assertIn("escrito pelo Qwen", Path(ARQ_TEMP).read_text())
        linhas = [json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertGreaterEqual(len(linhas), 5)
        nomes = [x["nome"] for x in linhas]
        self.assertIn("info_sistema", nomes)
        self.assertIn("escrever_arquivo", nomes)
        self.assertFalse(next(x for x in linhas if x["nome"] == "executar")["ok"])

    def test_05_ferramenta_inexistente_e_recorte(self):
        ag = Agente(self.cfg, console=lambda *a: None)
        self.assertIn("inexistente", ag._despachar("nao_existe", {}))
        p = Politica(self.cfg, BASE, console=lambda *a: None)
        self.assertTrue(p.recortar("x" * 20000).endswith("chars]"))
        self.assertEqual(p.recortar("curto"), "curto")

    def test_06_dry_run_nao_executa(self):
        self.cfg["dry_run"] = True
        ag = Agente(self.cfg, console=lambda *a: None)
        self.assertIn("dry-run", ag._despachar("janelas", {}))

    def test_07_persona_jovem_e_padrao(self):
        ag, _, _ = self._rodar()
        system = REQUISICOES[0]["messages"][0]
        self.assertEqual(system["role"], "system")
        self.assertEqual(ag.personalidade, "jovem")
        self.assertIn("próprio computador", system["content"])
        self.assertIn("20 anos", system["content"])
        self.assertIn("papel de parede", system["content"])
        self.assertIn("Downloads", system["content"])

    def test_08_persona_nao_remove_as_travas(self):
        """Mudar a voz não pode afrouxar a operação: segue valendo o freio."""
        _, _, saida = self._rodar()
        self.assertIn("[SEGURANÇA]", saida)
        self.assertIn("BLOQUEADO", saida)
        for frase in ("Antes de clicar", "Não inventa", "confirmação",
                      "nada do que você faz sai"):
            self.assertIn(frase, REQUISICOES[0]["messages"][0]["content"])

    def test_09_modo_tecnico(self):
        self.cfg["personalidade"] = "tecnico"
        ag, retorno, _ = self._rodar()
        system = REQUISICOES[0]["messages"][0]["content"]
        self.assertEqual(ag.personalidade, "tecnico")
        self.assertIn("agente que controla ESTE Windows", system)
        self.assertNotIn("20 anos", system)
        self.assertEqual(retorno, "tarefa concluida")


if __name__ == "__main__":
    unittest.main(verbosity=2)
