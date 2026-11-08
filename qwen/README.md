# Qwen 2.5 7B Instruct controlando o Windows

Agente local: o mesmo modelo que escreve os posts do seu bot do Bluesky, agora
com 13 ferramentas para **observar e agir no Windows**. Loop
`observar → pensar → chamar ferramenta → ver resultado → repetir`.

Tudo local: Ollama em `127.0.0.1:11434`, `urllib` da stdlib, zero `pip`,
zero chave de API, zero telemetria. O log fica em `logs/acoes.jsonl`.

O **system prompt é um jovem de 20 anos no próprio PC**, não um assistente
corporativo — ver abaixo.

---

## A persona (o que mudou por último)

`config.json → "personalidade": "jovem"` (padrão). O system prompt diz que
ele está no **seu** computador, na **sua** mesa, e mexe nele como qualquer
pessoa da idade dele: abre música enquanto faz outra coisa, troca o papel
de parede, arruma a pasta Downloads que virou bagunça, confere a RAM, abre
um vídeo, procura um arquivo que sumiu, anota uma ideia no Bloco de Notas,
olha quem está comendo a CPU, abre um jogo e fecha logo depois. Curioso,
disperso, irônico, fala como mensagem de celular — sem "certamente!", sem
tratar você como cliente.

```json
"personalidade": "jovem"      // padrão
"personalidade": "tecnico"    // prompt neutro de agente, se quiser voltar
```

Ou na hora: `python agente.py --personalidade tecnico "..."`.

🔒 **Trocar a voz não afrouxou nada.** As 8 regras de operação continuam
inteiras dentro do próprio prompt (observar antes de clicar, não inventar
caminho, não apagar por conta própria, confirmação pra comando destrutivo),
e `seguranca.py` continua valendo por fora. Escrevi um teste específico
(`test_08`) só pra garantir que a persona não comeu o freio. Se ligar
`--livre`, aí sim você desliga a confirmação — é escolha sua, explícita.

---

## O que foi feito agora (honestidade primeiro)

✅ Escrevi o kit completo e **testei a lógica de verdade** neste sandbox,
com um servidor Ollama falso: `9/9 testes OK` — protocolo de tools,
despacho de 2 chamadas no mesmo passo, bloqueio de comando destrutivo,
escrita real de arquivo, auditoria, dry-run, parser de fallback e os 3
testes novos da persona (padrão, travas preservadas, modo técnico).

🔴 **Não instalei no Windows remoto.** Não puxei os 4,7 GB nem executei
`instalar.ps1` lá. A instalação é um duplo clique que você faz.
Também **não parseei o PowerShell num `pwsh` real** (não existe neste
sandbox) — validei apenas balanceamento de chaves/parênteses e o JSON.
A parte Windows (ctypes/UIAutomation) está escrita, mas não foi executada
aqui; ela só roda em `os.name == 'nt'`.

---

## Instalar no Windows

1. Copie esta pasta para o Windows (pode ser pelo `Desktop` via RDP, ou
   extraia o ZIP no seu PC).
2. Duplo clique em **`instalar.bat`**.
   - `winget install -e --id Ollama.Ollama --silent` (com fallback para o
     `irm https://ollama.com/install.ps1 | iex`, que verifica assinatura
     Authenticode antes de rodar)
   - sobe `ollama serve` na 11434
   - `ollama pull qwen2.5:7b-instruct` (4,7 GB; se a tag não existir,
     cai para `qwen2.5:7b` e ajusta `config.json` sozinho)
   - roda `python agente.py --verificar` para confirmar **tool calling**
3. Duplo clique em **`INICIAR.bat`** e digite a ordem.

Exemplos de ordem:

```
> abra o Bloco de Notas e digite "oi, eu sou o Qwen"
> mostre os 10 processos que mais gastam CPU e explique o que cada um faz
> crie C:\Users\winuser\relatorio.txt com um resumo do sistema
> abra o Calc pela barra de tarefas (use ui_arvore antes de clicar)
```

Ou direto: `python agente.py "liste as janelas abertas"`.
Flags: `--dry-run` (mostra sem executar), `--livre` (desliga confirmação),
`--personalidade jovem|tecnico`, `--host`, `--modelo`, `--verificar`.

---

## As 13 ferramentas

| Grupo | Ferramentas |
|---|---|
| Sistema | `info_sistema`, `processos`, `executar` (PowerShell) |
| Arquivos | `listar`, `ler_arquivo`, `escrever_arquivo` |
| Tela em texto | `janelas`, `ui_arvore` |
| Mouse/teclado | `clicar`, `digitar` (Unicode, aceita acentos), `tecla` |
| Apps | `abrir` |
| Saída | `falar` |

Toda chamada passa por `seguranca.py`: limite de 40 ações/sessão,
confirmação humana antes de `Remove-Item -Recurse`, `format-volume`,
`reg delete`, `shutdown`, `bcdedit` etc., saída recortada em 12k chars e
auditoria em JSONL. `--livre` desliga o freio se você quiser controle
irrestrito. `config.json → "raiz"` limita leitura/escrita de arquivos a
uma pasta (não limita o PowerShell).

---

## Limites que não dá para maquiar

🔴 **Qwen 2.5 7B é text-only.** Ele não enxerga pixels. Por isso a
observação da UI é feita por **árvore de acessibilidade em texto**
(`UIAutomationClient`) e por títulos/retângulos de janelas — não por
screenshot. Funciona, mas controles que não expõem UIA (canvas de jogos,
alguns players) ficam invisíveis. Se quiser visão real, troque no
`config.json` por um VLM (`qwen2.5vl:7b`) e puxe a tag — não vem neste kit.

🐢 **2 vCPU / 8 GB / sem GPU.** O `qwen2.5:7b` Q4 (~4,7 GB) roda em CPU,
mas devagar: tipicamente poucos tokens por segundo. Cada passo do agente
pode levar de dezenas de segundos a alguns minutos. "Controlar
completamente" é funcional, **não é tempo real**. `timeout: 600` no config
existe exatamente por isso.

⏳ **O Windows do Actions é efêmero.** Ele morre em ~6 h e o modelo de
4,7 GB **não cabe no cofre** que fizemos (limite de 35 MB por arquivo) —
então cada boot re-baixa tudo. Para permanente de verdade, rode este kit
no **seu PC**: aí o modelo fica no disco, sem teto e sem cota. É o mesmo
`instalar.bat`.

📌 Tool calling exige Ollama **≥ 0.3.0** (suporte nativo ao Qwen2.5 desde
essa versão). Se `--verificar` devolver `NENHUM`, atualize o Ollama.

---

## Rollback

- Parar o agente: `Ctrl+C`.
- Parar o Ollama: `Stop-Process -Name ollama`.
- Remover o modelo: `ollama rm qwen2.5:7b-instruct`.
- Desinstalar: `winget uninstall -e --id Ollama.Ollama`.
- Apagar o kit: delete a pasta. Nada foi escrito no registro nem em
  `C:\Windows`; o único estado é `logs/acoes.jsonl` e os arquivos que
  você mesmo pedir para criar.

## Arquivos

`agente.py` (loop + schemas), `ferramentas.py` (Win32/ctypes + PowerShell),
`seguranca.py` (política + log), `testar.py` (6 testes com mock HTTP),
`config.json`, `instalar.ps1`, `instalar.bat`, `INICIAR.bat`.

Licença do modelo: Qwen2.5 7B é Apache 2.0. Ollama é MIT.
