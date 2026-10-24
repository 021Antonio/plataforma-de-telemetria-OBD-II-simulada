# APÊNDICE A: ORIGEM DOS NÚMEROS

Cada número reportado neste trabalho tem uma fonte rastreável no repositório. A Tabela 28 relaciona os números principais, o arquivo de origem e a forma de obtê-los. Números não listados aqui são derivações aritméticas simples dos listados (por exemplo, percentuais e razões), ou vêm de tabelas copiadas diretamente do arquivo citado na legenda.

::: {custom-style="LegendaTabela"}
Tabela 28: Origem dos números do Capítulo 5
:::

| Número | Valor | Fonte | Como obtido |
| --- | --- | --- | --- |
| Testes automatizados | 405 aprovados, 2 excluídos | saída de `pytest` | `pytest -q --tb=short --cov=obd` em 24/10/2026 |
| Cobertura total | 89% (2311 linhas, 254 não cobertas) | saída de `pytest-cov` | mesmo comando |
| Cobertura do protocolo | 97% a 100% | saída de `pytest-cov` | mesmo comando |
| Ciclos e leituras do E1 | 1907 e 19070 | `docs/ensaios/e1.json` | campos `ciclos` e `leituras` |
| Ciclo do E1 (média, p95) | 106,1 ms e 115,6 ms | `docs/ensaios/e1.json` | campo `ciclo_ms` |
| RTT do E1 (média, p95, máx) | 10,6; 13,5; 14,1 ms | `docs/ensaios/e1.json` | campo `rtt_ms` |
| Latência do E1 (média, p95, máx) | 2,9; 3,5; 42,2 ms | `docs/ensaios/e1.json` | campo `latencia_ms` |
| Erro por PID do E1 | Tabela 19 | `docs/ensaios/e1.json` | campo `por_pid`, subcampo `erro` |
| Detecção da P0300 | 0,79 s | `docs/ensaios/e1.json` | campo `deteccao_falha_s` |
| E2 (ciclo por atraso) | Tabela 21 | `docs/ensaios/e2.json` | campos `ciclo_ms` e `ciclos_por_s` de cada execução |
| E3 (ciclo por PIDs) | Tabela 22 | `docs/ensaios/e3.json` | idem |
| E4 (perda de quadros) | Tabela 23 | `docs/ensaios/e4.json` | campos `timeouts`, `ciclos`, `ciclo_ms` e `recuperacao` |
| E5 (remontagem do VIN) | Tabela 24 | `docs/ensaios/e5.json` | campo `remontagem_ms` |
| E6 (19 comandos) | 19 de 19 | `docs/ensaios/e6.json` | execução do cliente de soquete cru |
| E7 (HTTP e MQTT) | Tabela 25 | `docs/ensaios/e7_mosquitto.json` | campos `latencia_ms`, `ciclos` e `ciclos_por_s` |
| Repetição em contêiner (E1 a E3) | Tabela 26 | saída de terminal dos autores (`runs/repeticao/`, não versionado) | comando do Apêndice B, em 24/10/2026 |
| Máquina de medição | Linux sobre WSL2, Python 3.12.15, 32 núcleos lógicos | campo `maquina` de cada JSON | registrado pelo executor de ensaios |
| Linhas de código por módulo | Tabela 7 | `src/obd/` | contagem de linhas dos arquivos de cada pasta, em 24/10/2026 |
| python-OBD 0.7.3 e OBD Auto Doctor | descrição qualitativa | `docs/ensaios.md` (seção "Cliente real"), `docs/duvidas.md` (tarefa 09) e observação dos autores | teste `test_elm327_python_obd.py` e sessão manual |

::: {custom-style="Fonte"}
Fonte: elaborada pelos autores.
:::

Observação sobre o E7: o arquivo `docs/ensaios/e7.json` do repositório é o de uma execução sem *broker* real (intermediário em memória) e não é usado nos números deste trabalho. O arquivo `docs/ensaios/e7_mosquitto.json` é o da execução com Mosquitto real, gerada em 24/10/2026.

# APÊNDICE B: COMO REPRODUZIR

## Instalação e testes

Requisitos: Python 3.12 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test          # 405 testes
make cov           # com cobertura
make lint          # ruff e mypy
```

## Execução da plataforma

```bash
make run           # servidor, simulador, painel, ELM327 e coletor
# ou, com Docker:
docker compose up app
```

Dashboard em `http://localhost:8000/`, painel de controle em `http://localhost:8001/` e servidor ELM327 em `localhost:35000`. Com `OBD_ELM327_LOG=1`, o servidor imprime cada comando recebido e a resposta enviada.

## Execução dos ensaios

```bash
python -m tests.benchmarks.e1            # 240 s; --duration N muda a duração
python -m tests.benchmarks.e2            # e3, e4, e5, e6 e e7 do mesmo modo
```

Cada ensaio grava, em `runs/<data>/`, um CSV com uma linha por leitura (com `true_value`, `error` e `resolution`), um JSON com configuração, sementes, máquina e métricas, o banco SQLite e os gráficos. Sementes do E1: `seed_model=1` e `seed_ecu=1`; os demais usam as mesmas. Para o E7 com *broker* real, suba o Mosquitto antes (`docker compose --profile mqtt up -d mosquitto`).

## Repetição em outra máquina

Para uma comparação entre máquinas, conforme o RNF05: instalar o Python 3.12 ou superior e as dependências, fechar programas que consumam CPU (os tempos são de relógio real), rodar os ensaios E1 a E7 com `--out runs/maquina2`, e comparar os JSON das duas máquinas (campo `maquina`). Para repetir em contêiner isolado, na mesma máquina (foi o que se fez para E1 a E3):

```bash
export MSYS_NO_PATHCONV=1   # só no Git Bash do Windows
docker run --rm -v "$(pwd -W):/work" -w /work plataforma-de-telemetria-obd-ii-simulada-night \
  sh -c 'pip install -e ".[dev]" -q && python -m tests.benchmarks.e1 --out runs/repeticao && python -m tests.benchmarks.e2 --out runs/repeticao && python -m tests.benchmarks.e3 --out runs/repeticao'
```

O nome da imagem é o da imagem de desenvolvimento construída pelo `docker-compose.night.yml`. Valores reais e erros de decodificação dependem só das sementes e devem coincidir; ciclo, RTT e latência dependem do sistema operacional e da CPU, e as diferenças devem ser declaradas. A comparação com uma segunda máquina não foi realizada neste trabalho.

## Validação com cliente real

```bash
pytest -q --tb=short tests/integration -m realclient   # exige rede
```

O teste cria um ambiente virtual temporário, instala o python-OBD nele (nunca no ambiente do projeto) e o aponta para o servidor ELM327.

# APÊNDICE C: SESSÃO ELM327 COM O SIMULADOR

A Tabela 29 mostra uma sessão real, capturada em 24/10/2026 contra o servidor ELM327 do simulador (`python -m obd run`), por um cliente de soquete cru. Cada linha traz o comando enviado e a resposta, com `\r` representando o retorno de carro. A rotação da consulta `010C` é (12 · 256 + 98)/4 = 792,5 rpm, compatível com a marcha lenta do perfil urbano (800 rpm). O VIN devolvido pelo `0902` é um valor fixo do simulador, sem relação com um veículo real.

::: {custom-style="LegendaTabela"}
Tabela 29: Sessão ELM327 capturada contra o simulador
:::

| Comando | Resposta | Comentário |
| --- | --- | --- |
| `ATZ` | `ELM327 v1.5` | Reinicia e identifica o adaptador |
| `ATE0` | `ATE0` e `OK` | Desliga o eco; o próprio comando é ecoado, porque o eco ainda estava ligado |
| `ATL0` | `OK` | Sem avanço de linha |
| `ATH1` | `OK` | Liga cabeçalhos |
| `ATSP0` | `OK` | Protocolo automático |
| `0100` | `SEARCHING...` e `7E8 06 41 00 9C 3A 80 01` | Máscara de PIDs suportados (0x01 a 0x20), com cabeçalho |
| `010C` | `7E8 04 41 0C 0C 62` | Rotação: 792,5 rpm |
| `010D` | `7E8 03 41 0D 00` | Velocidade: 0 km/h |
| `0105` | `7E8 03 41 05 46` | Temperatura do arrefecimento: 70 − 40 = 30 °C |
| `ATH0` | `OK` | Desliga cabeçalhos |
| `0902` | `49 02 01 39 42 ... 31` | VIN em uma linha, já remontado |
| `03` | `NO DATA` | Sem códigos de falha armazenados |
| `0600` | `NO DATA` | Modo 06 não suportado |
| `ATDPN` | `A6` | Protocolo automático, ISO 15765-4 CAN 11/500 |
| `ATI` | `ELM327 v1.5` | Identificação |

::: {custom-style="Fonte"}
Fonte: captura feita pelos autores, em 24/10/2026.
:::

Cada resposta termina com `\r\r>`. Para comparação, a troca observada antes da tarefa 16, com o python-OBD, foi: `ATH1` respondia `OK`, mas as respostas continuavam sem cabeçalho; `ATDPN` e `ATTP6` respondiam `?`; `0600` respondia `7F 06 11`; `0900` respondia `7F 09 12`. A biblioteca descartava os quadros "por serem ímpares" e não lia nenhum PID.

# APÊNDICE D: DECISÕES DE PROJETO REGISTRADAS

A especificação deixou pontos em aberto, e cada decisão foi registrada em `docs/duvidas.md`, tarefa por tarefa. A Tabela 30 seleciona as que mais afetam os resultados ou a interpretação deles.

::: {custom-style="LegendaTabela"}
Tabela 30: Decisões de projeto selecionadas
:::

| Tarefa | Decisão | Motivo |
| --- | --- | --- |
| 01 | A resolução dos PIDs usa o passo exato (100/255 e 100/128) | Com o valor arredondado, o erro de ida e volta poderia passar de r/2 por arredondamento do critério |
| 02 | O ISO-TP usa funções puras e estados com o tempo por parâmetro | Atender à regra de que o protocolo não lê o relógio |
| 02 | STmin reservado (0x80 a 0xF0, 0xFA a 0xFF) vale 127 ms | Recomendação da norma |
| 03 | Modo 03 sem DTC responde `43 00`, não silêncio | O `NO DATA` é da camada ELM327, não da ECU |
| 03 | PID do modo 01 não suportado recebe silêncio | Comportamento da ISO 15765-4 |
| 03 | O freeze frame é capturado ao armazenar o primeiro DTC não pendente | Fidelidade ao modo 02 |
| 04 | O ruído entra no valor reportado, não no estado físico limpo | O estado limpo serve de referência para o erro |
| 04 | O modelo avança em passos fixos de 10 ms | Resultado independente da granularidade de consulta |
| 04 | A perda de quadros descarta a resposta antes do processamento | O coletor vê um timeout, como em um barramento real |
| 05 | Recuo progressivo a partir de 3 falhas seguidas | Evitar insistência contra uma ECU muda |
| 05 | Ciclo sem leitura válida ainda publica uma amostra vazia | O número de sequência não pode ter lacunas |
| 06 | Perdas são as lacunas do número de sequência na execução | Um servidor iniciado no meio da execução não conta o início como perda |
| 06 | Uma duplicata responde 202, não é gravada e vira evento | O coletor não deve tratar duplicata como erro |
| 06 | A fila de cada cliente WebSocket é ilimitada | Limitar exigiria decidir o que fazer com quem fica para trás; registrado como risco |
| 07 | A latência do cabeçalho usa o relógio do navegador | A fonte não estava definida; a mesma máquina evita viés |
| 09 | O servidor ELM327 usa o `Transport` do simulador | ISO-TP, atraso e falhas valem também para o ELM327 |
| 10 | Os ensaios rodam em um processo, com `LoopbackTransport` | O valor real só existe no processo da ECU |
| 10 | RNF01 e RNF02 são verificados pelo p95 | Critério mais rígido que a média |
| 10 | Os 500 kbit/s do RNF04 não são medidos | O barramento virtual não tem taxa |
| 12 | O `MqttPublisher` repete a mensagem pendente com recuo | O número de sequência não pode pular nem inverter |
| 16 | Serviço ou PID sem suporte, e `7F` da ECU, viram `NO DATA` | Comportamento esperado por clientes como o python-OBD; um chip real pode diferir (dúvida registrada) |

::: {custom-style="Fonte"}
Fonte: docs/duvidas.md.
:::
