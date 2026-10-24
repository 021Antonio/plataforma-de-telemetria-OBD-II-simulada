# Plano B: voltar a usar só o simulador

Use este guia se o hardware não for montado, não funcionar, ou se vocês decidirem não continuar com ele. **Nada se perde.** O simulador nunca dependeu do ESP32: o firmware mora numa pasta separada (`firmware/`) e o resto do projeto não o usa.

Em uma frase: **o projeto continua funcionando exatamente como antes, com `make run`, e o TCC da etapa 1 continua válido.**

## 1. Entendendo o que existe

| O quê | Onde | Depende de hardware? |
| --- | --- | --- |
| Simulador, ECU virtual, coletor, servidor, dashboard, painel | `src/` | Não |
| Testes, ensaios E1 a E7, TCC da etapa 1 | `tests/`, `docs/ensaios/`, `docs/tcc/` | Não |
| Servidor ELM327 do simulador (porta 35000) | `src/obd/simulator/elm327_server.py` | Não |
| Firmware do ESP32 e manual de hardware | `firmware/`, `docs/hardware/` | **Sim, só isto** |
| Script que lê um adaptador ELM327 remoto | `scripts/coletar_adaptador.py` | Só se usado com a placa |

Os pontos de referência no Git (tags):

- `v1.0-simulador`: a etapa 1 congelada, antes de qualquer coisa de hardware.
- `v1.1-firmware-pc`: a etapa 2 em software (tarefas 17, 18 e 19), antes de qualquer teste em placa.

## 2. Opção A (recomendada): não mexer em nada

Basta **não usar** o hardware. Todo o resto continua a funcionar. Não precisa apagar nem desfazer nada.

O que muda é só a narrativa: o trabalho fica como uma plataforma 100% em software, e o firmware vira "trabalho futuro com código de apoio já pronto e testado no PC".

### Rodar e validar o simulador

Dentro da pasta do projeto, com o ambiente virtual ligado (`. .venv/bin/activate`):

```bash
pip install -e ".[dev]"
make lint        # ruff + mypy limpos
make test        # testes unitários e de integração
make cov         # cobertura
make run         # sobe servidor, simulador e coletor
```

Depois de `make run`, abra:

- dashboard: <http://localhost:8000/>
- painel de controle do simulador: <http://localhost:8001/>
- adaptador ELM327 simulado: `localhost:35000`

Ou, sem instalar Python, só com Docker:

```bash
docker compose up
```

### Validar a camada ELM327 sem hardware

Os testes automáticos já validam a camada ELM327 do simulador:

```bash
pytest -q --tb=short tests/integration/test_conformance_simulador.py
pytest -q --tb=short tests/integration/test_firmware_host_server.py
```

O segundo roda a biblioteca do firmware (a mesma que iria para o ESP32) compilada **no PC**, dentro da mesma suíte de conformidade. Isso valida a lógica do firmware sem placa nenhuma.

Se quiserem ver a suíte de conformidade "na mão" contra o simulador:

```bash
make run &                                   # sobe o simulador
python -m tests.conformance --host 127.0.0.1 --port 35000
```

Esperado: **32 de 41 OK e 9 divergências, todas de valor** (ATRV e as respostas de `010C`, `010D`, `0105`, `0111`). Isso é normal: o arquivo dourado tem valores fixos e o simulador gera valores que variam com a condução. A forma e o formato das respostas conferem. Para a conferência exata de valores, o teste automático acima usa o simulador com valores fixos.

### Repetir os ensaios

```bash
python -m tests.benchmarks.e1            # 240 s
python -m tests.benchmarks.e2            # e3, e4, e5, e6 e e7 do mesmo modo
```

Os resultados vão para `runs/<data>/`. Instruções completas em `docs/ensaios.md`.

### Testar com clientes de terceiros (também sem hardware)

Com `make run` ligado, um aplicativo ou biblioteca que fale ELM327 por TCP pode conectar em `localhost:35000` (o OBD Auto Doctor e a biblioteca python-OBD já foram validados assim).

## 3. Opção B: voltar a árvore de trabalho ao estado da etapa 1

Use se alguém quiser ver ou entregar **exatamente** o que existia antes do hardware, sem as tarefas 17, 18 e 19.

Isto **não altera** a `main`; só cria uma pasta separada com o código daquela versão.

```bash
git fetch --tags
git worktree add ../obd-etapa1 v1.0-simulador
cd ../obd-etapa1
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
make test
make run
```

Para remover essa pasta depois:

```bash
cd ..
git worktree remove obd-etapa1
```

## 4. Opção C: tirar o firmware do repositório (só se for mesmo necessário)

Em geral **não vale a pena**: o firmware não atrapalha nada. Se mesmo assim quiserem retirar, faça num branch, nunca direto na `main`:

```bash
git checkout main && git pull
git checkout -b chore/remove-firmware
git rm -r firmware docs/hardware scripts/coletar_adaptador.py
make lint && make test
```

Atenção: o teste `tests/integration/test_firmware_host_server.py` depende de `firmware/`. Remova esse teste junto, ou o `make test` vai falhar. Depois abra o pull request e revise antes de mesclar. As tarefas 17 e 18 (conformidade ELM327 e coletor tolerante a erros) **não devem ser removidas**: elas melhoram o simulador também.

## 5. Como escrever isso no TCC

Se o hardware não for feito, o texto continua correto. Só ajuste duas coisas:

1. No Capítulo 6, "Trabalhos futuros", mantenha a segunda etapa como **planejada e não executada**, que é exatamente o que já está escrito.
2. Se foram feitos testes de bancada (fase 1 do manual) mas não o carro, escreva só isso: "firmware validado em bancada com ECU simulada; sem ensaio em veículo". Não escreva nada sobre comportamento em carro real.

E mantenha o termo **software-in-the-loop**. Não escreva "hardware-in-the-loop" em nenhuma hipótese.

Resultado negativo também é resultado. Se tentaram montar e não deu, descreva o que foi tentado e o que impediu. Isso é honesto e é aceito.

## 6. Resumo em uma tela

| Situação | O que fazer |
| --- | --- |
| Não vou montar o hardware | Opção A. Use `make run`. Nada a desfazer |
| Montei e não funcionou | Opção A. Guarde as anotações de problema (seção 9 do manual) para o TCC |
| Preciso mostrar exatamente a etapa 1 | Opção B, com a tag `v1.0-simulador` |
| Quero limpar o repositório | Opção C, num branch, com revisão |
