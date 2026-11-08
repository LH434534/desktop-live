# Permanente — o que dá para fazer, degrau por degrau

**Pedido:** "quero uma permanente".
**Resposta curta:** 1000% permanente exige uma máquina sua. Mas dava para
eliminar a pior parte agora — **o disco que sumia a cada 6 h** — sem me
pedir nenhuma conta nova. Foi isso que fiz.

---

## Degrau 1 — FEITO AGORA: o disco não some mais

O runner continua efêmero, mas `Desktop`, `Documents` e `Downloads` agora
**atravessam a morte dele**.

`cofre.py` empacota essas três pastas, cifra com **AES-256-GCM** (chave
derivada por PBKDF2-HMAC-SHA256, 200.000 iterações) e grava `estado.cofre`
no repo. O arquivo é público, mas sem a passphrase é só ruído. A passphrase
ficou num **Actions secret**, nunca no código.

Ciclo no `conectar-windows.yml` v2:

- **boot** → `python cofre.py restore ...` (falha aqui nunca derruba o desktop)
- **a cada 10 min**, junto com o heartbeat → `save` + commit
- **próximo boot** → restaura sozinho

Validação num runner GitHub de verdade (`cofre-teste #2`, 14:15 UTC):

```
SAVE     : arquivos: 3 | ignorados: 1 | bytes_cifrado: 20530
RESTORE  : arquivos_restaurados: 3
diff     : OK (nota.txt + dados.csv byte a byte)
appdata  : NAO VAZOU
senha_errada : REJEITADA (InvalidTag)
arquivo_40mb : IGNORADO (verificado no SAVE)
RESULTADO: COFRE_VALIDADO_NUM_RUNNER_GITHUB
```

Também testado no sandbox: round-trip idêntico, `AppData` excluído, senha
errada rejeitada, path traversal bloqueado e arquivo acima de 35 MB pulado.

⚠️ **Um bug meu no caminho:** o primeiro teste rotulou "36 MB ignorado",
mas 36.700.160 bytes é exatamente o limite de `35 * 1024 * 1024` — o arquivo
**tinha entrado**. Corrigi o teste para 40 MB e passei a exigir
`ignorados: 1` no próprio SAVE, em vez de escrever o rótulo à mão. O #1
mentiu; o #2 é o válido.

**Limites do cofre:**
- teto de 35 MB por arquivo e ~280 MB por pacote (GitHub não gosta de blob
  grande). Vídeos, `.blend` e APKs grandes ficam de fora — esses continuam
  nos entregáveis que eu te passei.
- a v2 **vale a partir do próximo boot** (~15:20 UTC). Não reiniciei o #1 de
  propósito: ele está com você agora, heartbeat 14:15, `rdp_3389: True`.
- se você trocar a senha ou revogar a `tskey-auth-…`, atualize os secrets
  antes da renovação das 5h15.

---

## Degrau 2 — FEITO AGORA: o caminho para 24/7 está aberto

Confirmei que a conta aceita **self-hosted runners**: a API devolveu um
`registration-token` (não foi gravado em lugar nenhum, expira em 1 h).

Runners self-hosted são gratuitos em repo público e **não têm o teto de 6 h
por job** dos runners hospedados — o limite de 6 h é para GitHub-hosted
[citation:10][citation:12]. É o que transforma "renovação encadeada" em
"máquina ligada sempre".

Deixei `bootstrap-vps.sh` + `permanente.yml` prontos. Você roda **um
comando** no VPS e ele instala XRDP + XFCE + Tailscale, cria o usuário,
abre a 3389 **só na interface da tailnet** e registra o runner.

⚠️ **Não executado:** não tenho VPS seu. `bash -n` passou e o YAML foi
parseado, mas instalação real depende da sua máquina.

Para uma VM gratuita, o **Oracle Cloud Always Free** é o caminho usual —
mas as fontes de 2026 **divergem** sobre a cota: umas dizem 4 OCPU / 24 GB
(3.000 OCPU-h + 18.000 GB-h) [citation:9], outras dizem que o FAQ oficial
agora fala em ~2 OCPU / 12 GB (1.500 OCPU-h + 9.000 GB-h) [citation:6].
Confira o FAQ antes de contar com os números. Requisitos recorrentes:
cartão de crédito real para verificação (pré-autorização temporária),
**Home Region imutável**, e capacidade A1 frequentemente esgotada em regiões
populares [citation:6][citation:8].

---

## Degrau 3 — 1000% seu, e Windows de verdade

Aí sim é propriedade: disco permanente, IP fixo, sem plataforma decidindo
por você.

**Windows real** num VPS custa licença. Planos de entrada ficam entre
**~US$ 9 e US$ 17/mês** (2 vCPU / 4–6 GB), e alguns fornecedores entregam
Windows Server em *evaluation* de 180 dias — para uso longo você precisa da
sua própria chave [citation:11][citation:13]. 4 GB é o mínimo confortável
para RDP com browser; 2 GB é o mínimo técnico da Microsoft [citation:11].

Alternativas sem custo: o seu próprio PC como self-hosted runner, ou Linux
com XRDP no Oracle Free Tier — **mas aí não é Windows**.

---

## O que NÃO mudou (honestidade)

| | Agora | Permanente de verdade |
|---|---|---|
| Arquivos do usuário | ✅ sobrevivem ao boot | ✅ disco local |
| Disponibilidade | encadeamento ~5h15, janela de 1–3 min | 24/7 |
| Hardware | da Microsoft, 2 vCPU / 8 GB | seu |
| IP `100.x` | muda a cada boot | fixo |
| Teto de 6 h | contornado, não eliminado | inexistente |
| Cota do GitHub | repo público = gratuito | irrelevante |

**Conclusão:** hoje você ganhou **memória**, não **propriedade**. O apê
continua alugado, mas agora a mudança não leva seus móveis. Para o 1000%,
falta exatamente uma coisa: `usuario@IP_do_VPS` (ou uma conta Oracle).
Com isso eu rodo o bootstrap e te devolvo o endereço testado.
