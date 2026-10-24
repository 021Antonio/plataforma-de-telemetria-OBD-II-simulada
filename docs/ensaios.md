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
Validação com app de terceiros: **pendente** (interativa); o cliente de biblioteca está em "Cliente real".

### Cliente real

python-OBD 0.7.3 (`pip install obd`, em venv temporário) apontado para `socket://127.0.0.1:<porta>`, `tests/integration/test_elm327_python_obd.py` (`pytest -m realclient`, precisa de rede).

- **Antes da tarefa 16:** conectava ("ISO 15765-4 (CAN 11/500)"), mas não lia nenhum PID. O servidor ignorava `ATH1` (python-OBD descartava o quadro "for being odd"), respondia `?` a `ATDPN` e `ATTP6`, e `0900`/`0600` voltavam `7F ...`.
- **Depois:** lê "Car Connected", protocolo `ISO 15765-4 (CAN 11/500)`, RPM, velocidade, temperatura do líquido, carga, borboleta e combustível (dentro da resolução do PID), RPM sobreposto em 3000 e DTCs (P0300 injetado; lista vazia sem falhas).
- **Não lido:** nada do que o teste cobre ficou de fora. Modo 06 responde `NO DATA`; apps de celular (Car Scanner, Torque, OBD Auto Doctor) seguem sem validação.

### E7: HTTP contra MQTT (60 s cada)

Executado em 24/10/2026 com Mosquitto 2 real (`eclipse-mosquitto:2`, contêiner no mesmo computador), o simulador e o coletor em outro contêiner Linux sobre WSL2 (Python 3.12, 32 núcleos lógicos), mesma semente (modelo 1, ECU 1), perfil urbano, 10 PIDs a cada 100 ms e atraso simulado da ECU entre 7 e 13 ms. Os dois canais rodaram em sequência na mesma máquina. Fonte dos números: `runs/mosquitto/e7.json` (campo `broker: "mosquitto"` na execução MQTT).

| Canal | Latência média (ms) | p95 (ms) | Máx (ms) | Perdas | Ciclos/s |
| --- | --- | --- | --- | --- | --- |
| HTTP (uvicorn local) | 3,0 | 3,6 | 43,5 | 0 | 7,7 |
| MQTT (Mosquitto real) | 0,6 | 0,8 | 13,4 | 0 | 9,3 |

- Perdas, duplicações e timeouts: 0 nos dois canais (463 ciclos no HTTP e 558 no MQTT, todos recebidos). Erro de decodificação acima de meia resolução: 0.
- Tempo de ciclo do coletor e RTT da ECU praticamente iguais nos dois canais (ciclo p95 de 115,8 ms no HTTP e 115,7 ms no MQTT; RTT p95 de 13,5 ms nos dois), porque dependem da ECU simulada e não do canal de publicação.
- A diferença de ciclos por segundo (7,7 contra 9,3) vem do tempo gasto publicando: no HTTP o coletor espera a resposta de cada envio. Não foi investigada além disso.
- Condição de rede: publicador e broker no mesmo computador, pela rede interna do Docker. Os números descrevem o custo do canal nesse arranjo e não representam um enlace real entre máquinas diferentes.

## Firmware ESP32 (pendente do autor)

O firmware (`firmware/`, ver `docs/hardware/esp32.md`) foi verificado só no PC: `make -C firmware test` e a suíte de conformidade contra `firmware/build/host_server` (41/41, 0 divergências). Nada abaixo foi executado em hardware.

**Bancada (sem carro, `BENCH_MODE 1`)**

1. Grave o firmware e conecte o PC ao ponto de acesso `OBD-ESP32` (`192.168.0.10`).
2. `python -m tests.conformance --host 192.168.0.10 --port 35000` e registre as divergências.
3. Aponte o coletor para `192.168.0.10:35000` por alguns minutos e confira perdas e latência.

**Campo (no carro, `BENCH_MODE 0`, ignição ligada)**

1. Confira ligações, terminação removida e o fusível; ligue o adaptador na porta OBD-II.
2. Conecte ao Wi-Fi do adaptador e rode `ATZ`, `ATDP`, `0100`, `010C`, `0902` e `03` à mão.
3. Rode o coletor por 5 minutos parado e depois em movimento, sem afirmar nada além do que foi medido.

| Ensaio | Data | Resultado da suíte (OK/divergências) | Latência média (ms) | Perdas | Observações |
| --- | --- | --- | --- | --- | --- |
| Bancada, Wi-Fi AP | | | | | |
| Bancada, Wi-Fi estação | | | | | |
| Carro, parado | | | | | |
| Carro, em movimento | | | | | |

## Repetir em uma segunda máquina

1. Instale Python 3.12+ e `pip install -e ".[dev]"`; confira `python -m pytest -q --tb=short tests/unit tests/benchmarks -k "stats or smoke"`.
2. Feche o que consome CPU (os tempos são de relógio real) e rode `python -m tests.benchmarks.e1` até `e7` com `--out runs/maquina2`.
3. Para o E7 real, suba o Mosquitto (`docker compose --profile mqtt up -d`) antes.
4. Compare os `eN.json` das duas máquinas (campo `maquina`) e declare as diferenças em ciclo, RTT e latência. Valores reais e erros de decodificação dependem só das sementes e devem coincidir; ciclo, RTT e latência dependem do sistema operacional e da CPU.
