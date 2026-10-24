# Ensaios de desempenho (E1 a E7)

Resultados de uma máquina (`maquina` em cada JSON de `docs/ensaios/`: Python 3.12, WSL2). **Não há
segunda máquina medida**: veja as instruções no fim e `docs/duvidas.md` (tarefa 10, item 10).
O modelo é *software-in-the-loop*: nada aqui diz respeito a veículo real.

## Como rodar

```bash
pip install -e ".[dev]"
python -m tests.benchmarks.e1            # 240 s; --duration N muda a duração por execução
python -m tests.benchmarks.e2            # e3, e4, e5, e6 e e7 do mesmo modo
pytest -q --tb=short tests/unit tests/benchmarks -k "stats or smoke"
```

Saída em `runs/<data>/` (ignorado pelo git): `eN.csv` (uma linha por leitura, com `true_value`,
`error` e `resolution`), `eN.json` (configuração, sementes, máquina e métricas), `eN_<run>.db`
(SQLite do servidor, com `readings.true_value` preenchido) e os gráficos `eN_*.png`.
Exemplo versionado em `docs/ensaios/` (o CSV do E1 está cortado em 500 linhas).
Sementes do E1: `seed_model=1`, `seed_ecu=1`; os demais usam as mesmas.

## Resultados

Estatísticas: média, desvio padrão amostral, mediana, p95, p99 e máximo (todas no JSON).

### E1: 240 s, 10 PIDs, ECU em 10 ± 3 ms, P0300 aos 100 s

| Medida | Resultado |
| --- | --- |
| Ciclos / leituras | 1907 / 19070 |
| Ciclo (ms) | média 106,1; desvio 5,6; p95 115,6; p99 119,3; máx 124,0 |
| RTT por PID (ms) | média 10,6; desvio 1,8; p95 13,5; p99 13,7; máx 14,1 |
| Latência coletor→banco (ms) | média 2,9; p95 3,5; p99 3,7; máx 42,2 |
| Perdas / duplicações / timeouts | 0 / 0 / 0 |
| Leituras com erro > resolução/2 | 0 de 19070 (erro máx. rpm 0,125 de 0,25; combustível 0,196 de 0,392) |
| Detecção da P0300 | 0,79 s após a injeção |

| Requisito | Limite | Medido | |
| --- | --- | --- | --- |
| RNF01 ciclo de 10 PIDs (p95) | ≤ 150 ms | 115,6 ms | atendido |
| RNF02 latência (p95) | ≤ 50 ms | 3,5 ms | atendido |
| RNF03 perdas em 240 s | 0 | 0 | atendido |
| RNF04 IDs 11 bits (0x7DF/0x7E8), RTT ≤ P2 | ≤ 50 ms | RTT máx 14,1 ms | atendido; 500 kbit/s não é medido |

### E2: atraso da ECU (30 s cada)

| Atraso | Ciclo médio (ms) | Ciclo p95 (ms) | Ciclos/s | Leituras/s |
| --- | --- | --- | --- | --- |
| 0 ms | 0,5 | 0,7 | 9,9 | 99,4 |
| 10 ms | 103,8 | 105,8 | 8,1 | 81,1 |
| 25 ms | 257,8 | 259,5 | 3,5 | 35,4 |
| 50 ms | 506,4 | 508,2 | 1,8 | 18,5 |

O ciclo cresce linearmente (cerca de 10 × atraso). Com 25 ms ou mais o ciclo passa de 150 ms: RNF01 só vale até cerca de 14 ms por PID.
Com 0 ms o ciclo não chega a 1 ms, e a taxa fica em 10 ciclos/s, limitada pelo intervalo de 100 ms.

### E3: número de PIDs (20 s cada, ECU em 10 ± 3 ms)

| PIDs | Ciclo médio (ms) | Ciclo p95 (ms) | Taxa por PID (Hz) | Leituras/s |
| --- | --- | --- | --- | --- |
| 1 | 10,6 | 13,6 | 9,9 | 9,9 |
| 3 | 32,0 | 37,3 | 9,9 | 29,7 |
| 5 | 53,5 | 59,7 | 9,9 | 49,5 |
| 10 | 106,6 | 116,9 | 7,9 | 79,2 |

### E4: perda de quadros (30 s cada, 10 PIDs)

| Perda | Timeouts | Ciclo médio (ms) | Leituras/s | Máx. de ciclos seguidos sem leitura de um PID |
| --- | --- | --- | --- | --- |
| 0% | 0 | 106,3 | 79,4 | 0 |
| 1% | 27 | 117,3 | 71,7 | 1 |
| 5% | 95 | 157,0 | 53,0 | 2 |
| 10% | 131 | 190,5 | 42,6 | 2 |

Sem perdas de amostras no servidor em nenhum caso: o coletor publica sempre, com o PID perdido ausente e contado em `timeouts`.

### E5: remontagem do VIN (100 repetições, ISO-TP, 3 quadros)

| STmin | Média (ms) | Desvio | Mediana | p95 | p99 | Máx |
| --- | --- | --- | --- | --- | --- | --- |
| 0 ms | 1,15 | 0,04 | 1,14 | 1,22 | 1,23 | 1,24 |
| 1 ms | 2,26 | 0,06 | 2,25 | 2,36 | 2,45 | 2,47 |
| 10 ms | 11,58 | 0,45 | 11,35 | 12,26 | 12,29 | 12,31 |

### E6: cliente ELM327 de soquete cru (19 comandos)

19 de 19 respostas no formato esperado (`ATZ`, `ATE0`, `ATL0`, `ATS1`, `ATH0`, `ATSP0`, `ATDP`, `ATRV`, `0100`, `0120`, `010C`, `010D`, `0105`, `0111`, `0101`, `03`, `0902`, `01FF`, `XYZ`).
Validação com app de terceiros: **pendente** (interativa).

### E7: HTTP contra MQTT (60 s cada)

| Canal | Latência média (ms) | p95 (ms) | Máx (ms) | Perdas | Ciclos/s |
| --- | --- | --- | --- | --- | --- |
| HTTP (uvicorn local) | 3,0 | 3,5 | 44,0 | 0 | 7,9 |
| MQTT (**broker em memória**) | 0,2 | 0,3 | 12,2 | 0 | 9,3 |

Não havia Mosquitto nesta máquina: a linha MQTT usa o broker simulado de `tests/fakes.py`, sem rede nem broker real. Ela mede só o custo de serialização e de despacho; **não é comparável ao HTTP**. Repita com `docker compose --profile mqtt up -d` antes do E7 para o número real.

## Repetir em uma segunda máquina

1. Instale Python 3.12+ e `pip install -e ".[dev]"`; confira `python -m pytest -q --tb=short tests/unit tests/benchmarks -k "stats or smoke"`.
2. Feche o que consome CPU (os tempos são de relógio real) e rode `python -m tests.benchmarks.e1` até `e7` com `--out runs/maquina2`.
3. Para o E7 real, suba o Mosquitto (`docker compose --profile mqtt up -d`) antes.
4. Compare os `eN.json` das duas máquinas (campo `maquina`) e declare as diferenças em ciclo, RTT e latência. Valores reais e erros de decodificação dependem só das sementes e devem coincidir; ciclo, RTT e latência dependem do sistema operacional e da CPU.
