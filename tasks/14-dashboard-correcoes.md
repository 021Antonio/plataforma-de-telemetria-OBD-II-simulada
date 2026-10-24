---
id: "14"
title: Correções do dashboard e do painel e script de capturas de tela
model: sonnet
session: 14
order: 14
depends_on: ["13"]
parallel_with: []
weight: P
escalate_if: "valores lentos continuam piscando ou sumindo após 2 iterações"
spec: docs/spec/07-dados-web.md
---

## Escopo

Corrigir os defeitos vistos com o sistema rodando (`python -m obd run`) e criar a ferramenta de captura de tela que a tarefa 15 usa.

## Defeitos

1. **Valores lentos somem.** Cada amostra traz só os PIDs lidos naquele ciclo; os lentos (temperatura do líquido, combustível, ajuste de mistura, tensão) chegam a cada N ciclos. Hoje o dashboard mostra "–" quando o PID não veio na amostra. Correção: guardar o último valor de cada PID e atualizar só os que chegaram. Marcar o valor como defasado (esmaecido) quando passar de 5 s sem atualização, e como ausente só se nunca chegou.
2. **Títulos colados.** "VELOCIDADE", "TEMPERATURA" e "COMBUSTÍVEL" aparecem juntos e invadem o cartão vizinho. Cada medida deve ter o seu próprio rótulo e o cartão não pode estourar a largura.
3. **Botões "Automático" cortados** na borda direita do cartão "Variáveis" do painel. Nenhum controle pode ser cortado em telas de 1280 px ou mais.
4. **Fonte da amostra.** `config/default.yaml` diz `can.transporte: virtual`, mas as amostras trazem `source: loopback`. Descobrir qual transporte o `python -m obd run` usa de fato, fazer config e comportamento coincidirem (ou documentar a decisão em `docs/duvidas.md`) e garantir que o campo `source` diga a verdade.

## Ferramenta de captura

- `scripts/capturar_telas.py`: sobe `python -m obd run` em portas livres com banco temporário, aplica um cenário (perfil urbano, override de rotação em 3000, falha P0300), abre o dashboard e o painel com Playwright (Chromium) e salva PNGs em `docs/img/` (`dashboard.png`, `painel.png`). Encerra o sistema ao final. Aceita `--saida DIR`.
- Adicionar `playwright` aos extras de desenvolvimento do `pyproject.toml`. A imagem Docker do executor já traz o Chromium em `PLAYWRIGHT_BROWSERS_PATH`.
- Depois de corrigir, **abra os PNGs e confira por inspeção**: sem "–" nos PIDs lentos, sem texto sobreposto, sem botão cortado. Registre o que viu em `docs/duvidas.md`.

## Testes (escrever primeiro)

- A lógica de mesclar amostras (último valor por PID, marca de defasagem) fica em função pura e é testada via Node, como as outras lógicas puras do dashboard.
- Teste de integração: duas amostras seguidas, a segunda sem o PID lento, mantêm o valor lento na tela.
- O teste de `source` verifica que o valor reportado corresponde ao transporte configurado.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration tests/e2e
make lint
python scripts/capturar_telas.py     # gera docs/img/*.png
```

## Fora desta tarefa

Mudança de visual e de identidade (tarefa 15).

## Prompt de lançamento

```text
Leia apenas tasks/14-dashboard-correcoes.md e docs/spec/07-dados-web.md. Testes primeiro, depois corrija, gere as capturas, abra os PNGs para conferir e mostre só as falhas.
```
