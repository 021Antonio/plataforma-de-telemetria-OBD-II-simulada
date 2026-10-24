---
id: "17"
title: Especificação do dialeto ELM327 e suíte de conformidade contra qualquer endereço TCP
model: sonnet
session: 18
order: 18
depends_on: ["16"]
parallel_with: []
weight: M
escalate_if: "a suíte não consegue distinguir respostas corretas de incorretas entre duas implementações após 2 iterações"
spec: docs/spec/04-protocolo.md
---

## Escopo

Hoje o dialeto ELM327 existe só como código (`src/obd/simulator/elm327_server.py`) e testes. O firmware do ESP32 (tarefa 19) precisa responder igual. Esta tarefa transforma o dialeto em especificação escrita e em uma suíte que roda contra qualquer servidor TCP ELM327.

## Arquivos

- `docs/spec/09-elm327-dialeto.md`: tabela de cada comando aceito (AT e OBD), resposta com `ATH0` e `ATH1`, `ATS0` e `ATS1`, `ATE0` e `ATE1`, `ATL0` e `ATL1`, `SEARCHING...` só na primeira consulta, `NO DATA`, `?`, multiquadro, prompt `\r\r>`. Incluir as respostas de erro do chip real (`UNABLE TO CONNECT`, `BUS INIT: ERROR`, `CAN ERROR`, `STOPPED`, `BUFFER FULL`) marcando as que o simulador ainda não gera. Atualizar a tabela de `docs/spec.md` com a seção 9.
- `tests/conformance/roteiro.py`: o roteiro dos 19 comandos do E6 mais os casos da tarefa 16 (`ATH1`, `ATDPN`, `0900`, `0600`, `03`, `0902`), como dados (comando, estado esperado, resposta esperada).
- `tests/conformance/__main__.py`: `python -m tests.conformance --host H --port P [--config perfil.json]`, que executa o roteiro, imprime uma linha por comando (OK ou diferença) e sai com código diferente de zero se houver divergência.
- `tests/conformance/dourado.json`: respostas esperadas, geradas do simulador com semente fixa e valores fixos (não dependem de relógio).
- `tests/integration/test_conformance_simulador.py`: sobe o `Elm327Server` com valores fixos e roda a suíte contra ele; deve passar sem divergências.

## Testes (escrever primeiro)

- A suíte detecta uma divergência de propósito: um servidor de teste (dublê em `tests/fakes.py`) que responde `?` a `ATDPN` ou ignora `ATH1` faz a suíte falhar e apontar o comando.
- Contra o simulador real, 0 divergências.
- A suíte não depende de `time.time()` nem de portas fixas.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration -m "not broker and not realclient"
make lint
```

## Fora desta tarefa

Mudar o comportamento do simulador (só especificar e testar o que existe). Firmware.

## Prompt de lançamento

```text
Leia apenas tasks/17-elm327-conformidade.md e docs/spec/04-protocolo.md. Testes primeiro, depois a suíte e a spec do dialeto; rode os comandos do critério de pronto e mostre só as falhas.
```
