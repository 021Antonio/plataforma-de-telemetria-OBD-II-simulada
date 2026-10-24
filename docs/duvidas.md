# Dúvidas e decisões registradas

Registro de pontos não definidos explicitamente na spec, com a decisão tomada
para seguir em frente. Revise e ajuste quando for necessário.

## Tarefa 00 (fundação)

1. **Portas.** A tarefa lista 8000, 8001 e 35000 sem dizer a qual serviço cada
   uma pertence. Decisão: `servidor: 8000` (FastAPI), `painel: 8001` (rotas do
   painel de controle) e `elm327_tcp: 35000` (servidor compatível com ELM327).
2. **Lista de PIDs padrão.** A tarefa pede "a lista de PIDs" sem enumerá-la.
   Decisão: oito PIDs do modo 01 de uso comum (0x04, 0x05, 0x0B, 0x0C, 0x0D,
   0x0F, 0x11, 0x2F). Ajustar quando `docs/spec/04-protocolo.md` for lido na
   tarefa do protocolo.
3. **Valores do campo `can`.** A tarefa cita a taxa 500000. Decisão: campo
   `can.taxa_bps` e `can.transporte: virtual` como padrão, com os demais tipos
   listados em comentário.
4. **Intervalo de coleta.** Não especificado na fundação. Decisão: `coleta.intervalo_ms: 100`
   como valor provisório.
5. **`make run`.** A tarefa define o alvo mas não o comportamento. Decisão:
   alvo existe e apenas informa que não há o que rodar ainda, saindo com código 0.
6. **Versão de ferramentas de lint.** Versões de `ruff` e `mypy` no pre-commit
   foram escolhidas sem verificação contra o registro atual. Conferir ao rodar
   `pre-commit autoupdate`.
7. **Configuração do mypy e do ruff.** Não definida pela tarefa. Decisão: mypy
   em modo `strict`, ruff com regras `E, F, I, UP, B, SIM` e linha de 100 colunas.

## Tarefa 01 (protocolo base)

1. **Resolução dos PIDs.** A spec arredonda (0,392; 0,781). Decisão: `resolution` usa o passo
   exato (100/255, 100/128), senão o erro de ida e volta pode passar de `resolution / 2`.
2. **`parse_response(raw)`.** A spec dá só `raw`, mas "PID errado é rejeitado" exige a requisição.
   Decisão: parâmetro opcional `request`; sem ele valida só o modo+0x40 e o tamanho do PID.
3. **`PidDef` estendido.** Acrescentei `min_value` e `max_value` (faixa física) para os testes de
   propriedade. `encode` satura fora da faixa.
4. **PID 0x06.** Fórmula (A−128)·100/128 implementada como `A·100/128 − 100` (equivalente).
5. **Máscara de suporte.** `decode_supported` inclui o bit de continuação (0x20, 0x40, 0x60).
6. **Quadros.** `CanFrame` valida ID (0x7DF, 0x7E0–0x7E8) e DLC=8; o byte PCI do ISO-TP fica
   para a tarefa 02. Modo 04 rejeita resposta com mais de 1 byte.
7. **Descrições de DTC.** Textos em português escritos por mim (exceto P0300, da spec).

## Tarefa 02 (ISO-TP e Modos 02/09)

1. **API do ISO-TP.** A tarefa pede funções puras sobre bytes e estados. Decisão: `segment`/`reassemble`
   (sem tempo), `Reassembler.feed(frame, now)` e `Sender.start/on_flow_control/poll(now)` com estado
   interno e tempo por parâmetro; nada de `time.time()`.
2. **N_Cr.** O prazo de 1 s reinicia a cada CF. No emissor, a mesma janela vale para esperar o FC
   (inclusive após FC WAIT e após o fim de um bloco). `IsoTpTimeout` herda de `ProtocolError`.
3. **STmin reservado.** Valores 0x80–0xF0 e 0xFA–0xFF são tratados como 127 ms (recomendação da norma).
4. **Modo 02.** Requisição `02 PID 00` (sempre quadro de congelamento 0); resposta com outro nº de quadro é rejeitada.
5. **Modo 09.** Só o PID 0x02 (VIN); `Response.data` traz os 17 bytes ASCII. FC overflow levanta `ProtocolError`.
6. **Testes.** `pythonpath = ["tests"]` no pytest para importar `tests/fakes.py` (`FakeClock`) sem conflito no mypy.

## Tarefa 03 (transporte e ECU virtual)

1. **Modelo de veículo.** `vehicle_model.py` é da tarefa 04. A ECU depende só de `PidSource`
   (`value(pid) -> float`, em `simulator/ecu.py`); a tarefa 04 deve adaptar o modelo real a isso.
2. **ECU como máquina de estados.** `Ecu.on_frame` recebe quadros e `Ecu.poll` devolve os devidos, com
   relógio injetado (atraso testável com `FakeClock`). `LoopbackTransport` e `EcuCanNode` movem os bytes.
3. **Log `(request_id, true_value)`.** `request_id` é o nº sequencial da requisição aceita pela ECU.
   Só PIDs com valor físico (Modo 01 numérico) entram; máscaras, PID 0x01 e Modos 02/03/04/07/09 não.
4. **Modo 03/07 sem DTCs.** A ECU responde `43 00` / `47 00` (N = 0), não silêncio. O `NO DATA` é da camada ELM327.
5. **Freeze frame.** Capturado ao armazenar o primeiro DTC (não pendente); Modo 04 apaga. Sem ele, o Modo 02 é silêncio.
6. **Respostas negativas.** Modo desconhecido: `7F modo 11`; Modo 09 com PID ≠ 02: `7F 09 12`; tamanho errado: `7F modo 13`.
   PID do Modo 01 não suportado continua em silêncio.
7. **Descoberta.** O bit de continuação (0x20, 0x40) só é anunciado se houver PID acima da faixa; 0x20/0x40 sem
   anúncio ficam em silêncio. O PID 0x01 sempre é anunciado.
8. **Timeout do transporte.** `timeout_ms` vale até o primeiro quadro (P2); depois do FF vale o N_Cr (1 s).
   Estouro de N_Cr devolve `None`; quadro malformado propaga `ProtocolError`. O transporte não filtra o eco
   (isso é do coletor) e descarta quadros residuais antes de cada requisição (CAN virtual).
9. **FC do testador.** `bs` e `stmin` são parâmetros do transporte; o FC vai em 0x7E0. Uma requisição por vez (lock).
10. **Atraso.** `delay_ms=(min, max)` sorteia uniformemente por requisição com `random.Random(seed)`; só o
    primeiro quadro é atrasado. Perda, corrupção, ECU muda e `STmin` do lado da ECU ficam para a tarefa 04.

## Tarefa 04 (modelo de veículo e falhas)

1. **Ruído.** O ruído gaussiano entra no valor reportado (o que a ECU codifica e registra em `log`), não
   no estado físico limpo (`VehicleModel.state`). `VehicleConfig.noise` multiplica os desvios-padrão
   (0 desliga); combustível não tem ruído. Valores são limitados à faixa de cada PID.
2. **Perfil.** Os passos são degraus (valem até o próximo `t`); a velocidade segue o alvo com aceleração
   máxima de 10 km/h/s e desaceleração de 15 km/h/s. Com `loop`, o período é o `t` do último passo.
3. **Carga, MAP, marchas.** Fórmulas ilustrativas: carga = 15 + 85·borboleta·(0,4 + 0,6·rpm/6000);
   MAP = min(101, 28 + 0,73·carga); trocas de marcha em 25/45/65/85 km/h; marcha lenta 800 rpm, corte 6500.
4. **Determinismo.** O modelo avança em passos fixos de 10 ms até `clock()`; o resultado não depende de
   quantas vezes ou com que granularidade se consulta. Semente do modelo e da ECU/falhas são independentes.
5. **DTC com instante.** `FaultInjector.schedule_dtc(code, at)` é aplicado pela ECU de forma preguiçosa, na
   primeira `on_frame`/`poll` com `clock() >= at`; o freeze frame é capturado nesse momento. Para injeção
   imediata use `Ecu.add_dtc`. DTC pendente não gera freeze frame (como na tarefa 03).
6. **Perda e corrupção.** Sorteadas por requisição aceita: perda descarta a resposta (a requisição não é
   processada nem logada); corrupção inverte um bit do eco de modo ou de PID da resposta de aplicação.
   Os dois usam o RNG do `FaultInjector` e só consomem semente quando a probabilidade é > 0.
7. **ECU muda.** Ignora requisições e FCs e descarta resposta em andamento; ao religar volta ao normal.
8. **Atraso de ISO-TP.** `STmin`/`BS` do injetor são impostos ao emissor da ECU sobrepondo o FC do testador:
   STmin = máximo entre os dois, BS = menor valor não nulo. `set_delay` do injetor tem precedência
   sobre o `delay_ms` do construtor da ECU.
9. **Config.** Seção `veiculo` em `config/default.yaml` lida por `VehicleConfig.from_yaml`; os perfis
   ficam em `config/profiles/` (`load_profile` aceita nome ou caminho).

## Tarefa 05 (coletor)

1. **Config do coletor.** Nova seção `coletor` em `config/default.yaml` (transporte, intervalo, timeout, DTC,
   recuo e `plano` com `a_cada`/`prioridade` por PID), lida por `CollectorConfig.from_yaml`. Rápidos (todo
   ciclo): rotação, MAP, borboleta e velocidade; lentos (a cada 5 ciclos): carga, temperaturas, combustível, tensão.
2. **Relógios.** `clock` (monotônico, RTT e ciclo) e `wall_clock` (epoch, `ts` do `Sample`) injetáveis; o
   padrão usa `time.monotonic`/`time.time` só no coletor, nunca no protocolo.
3. **Recuo progressivo.** Aplicado a toda requisição: com `n >= limiar` falhas seguidas, espera
   `min(max, base·2^(n-limiar))` antes de enviar; qualquer resposta válida zera a contagem (inclusive a do PID 0x01).
4. **Falha conta como `invalid`.** Resposta com eco errado, tamanho errado ou negativa (7F). Timeout vai em `timeouts`.
5. **Ciclo vazio.** Um ciclo sem nenhuma leitura válida ainda publica um `Sample` (valores vazios, erros
   contados), para o `seq` não ter lacunas. Falha de publicação é registrada (`publish_failed`) e a amostra é
   descartada; o servidor vê a lacuna pelo `seq`. Sem reenvio nem reconexão com recuo no `HttpPublisher` (fica para a tarefa do servidor).
6. **Descoberta.** Segue o bit de continuação (0x20, 0x40). Se nada for anunciado, tenta de novo no ciclo seguinte.
7. **DTCs.** A primeira leitura do PID 0x01 sempre lê o Modo 03 e publica um `DtcReport`; depois só se (MIL, contagem)
   mudar. O `cycle_ms` não inclui essa verificação; todos os DTCs saem como `stored` (Modo 07 não é lido).
8. **`elm327_tcp`.** `build_transport` levanta `NotImplementedError` até a tarefa 09. `loopback` exige uma `Ecu`.
9. **RNF01.** Medido com `LoopbackTransport` e ECU em 10 ms fixos, relógio real, ciclo 0 (10 PIDs).

## Tarefa 06 (servidor, API e banco)

1. **Execução (`runs`).** A spec não diz quando criar a linha. Decisão: criada de forma preguiçosa na primeira
   gravação, com a `source` da primeira amostra (`desconhecida` se o primeiro evento for DTC). Estatísticas
   valem só para a execução atual; `latest`, `history`, `dtc` e `export.csv` cobrem todas as execuções.
   `seed_*`, `profile` e `notes` existem mas ficam vazios até as tarefas do simulador e dos ensaios.
2. **`GET /api/latest`.** A tabela diz resposta `Sample`, mas a descrição fala em "estado dos DTCs". Decisão:
   devolve só o `Sample` (404 sem amostras); o estado dos DTCs fica em `/api/dtc`.
3. **`GET /api/history`.** `since` filtra pelo `ts` da amostra (instante de publicação). Devolve as `limit`
   primeiras a partir de `since`, em ordem crescente (padrão 1000, máximo 10000).
4. **`GET /api/dtc`.** Histórico de relatórios, do mais antigo ao mais novo; o último traz os DTCs ativos.
   Relatório sem DTCs grava uma linha com `code` NULL, que mantém o relatório reconstruível.
5. **Colunas além da spec.** `samples` ganha `source`, `timeouts` e `invalid`; `dtc_events` ganha `report_id`,
   `ts`, `mil`, `count` e `description`. Sem elas não é possível reconstruir `Sample` e `DtcReport` do banco.
6. **Perdas e duplicatas.** Perda = lacunas entre o menor e o maior `seq` da execução (um servidor que começa
   no meio de uma execução não conta o início como perda). `seq` repetido responde 202 ao coletor, não é
   gravado e vira evento `duplicate` em `comm_events`; `received` não conta duplicatas.
7. **Latência e taxa.** Latência = `ts_recv − ts` da amostra, em ms, com o relógio do servidor. Taxa =
   amostras com `ts_recv` nos últimos 3 s, divididas por 3. Percentis por posto mais próximo.
8. **Mensagens do WebSocket.** A spec não diz como distinguir amostra de DTC. Decisão: envelope
   `{"type": "sample", "data": Sample}` ou `{"type": "dtc", "data": DtcReport}`. Ao conectar: amostras
   com `ts >= agora − 60 s`, depois relatórios de DTC no mesmo intervalo, depois o ao vivo. A inscrição
   acontece antes da leitura do histórico; logo, uma amostra publicada nessa janela pode chegar duas vezes.
   O cliente deduplica por `seq`.
9. **Fila por cliente.** `Broadcaster` usa filas sem limite. Um cliente lento acumula memória; limitar a
   fila exigiria decidir o que fazer com quem fica para trás (desconectar ou perder mensagens).
10. **Dashboard estático.** Montado em `/` só se `src/obd/web/dashboard/` existir, para a tarefa 07 não
    depender desta. Montado depois das rotas, para não engolir `/api`.
11. **Dependência.** O `sqlalchemy` async exige `greenlet`, que o `pyproject.toml` não declarava. Decisão:
    `sqlalchemy[asyncio]>=2`.
12. **Arquivos fora da lista.** `state.py` (estado compartilhado e `Broadcaster`) e `stats.py` (cálculo puro,
    usado pelos dois armazenamentos) foram criados para evitar ciclo entre `routes.py` e `ws.py`.
13. **Ponto de entrada.** `create_app(storage, clock)` recebe o armazenamento pronto (`await SqlStorage.create(url)`).
    O caminho do arquivo SQLite e o processo que sobe o servidor ficam para `make run`, ainda não implementado.
14. **Aviso de depreciação.** O `TestClient` do Starlette avisa que `httpx` está depreciado (sugere `httpx2`).
    Não foi suprimido; a versão do FastAPI instalada é a que impõe esse aviso.

## Tarefa 12 (MQTT)

1. **Arquivos fora da lista.** `src/obd/mqtt_common.py` guarda tópicos, recuo e o adaptador `AiomqttLink`, para
   publicador e assinante não dependerem um do outro. Ambos usam a interface `MqttLink`, que o `FakeBroker` implementa.
2. **Broker fora do ar.** `MqttPublisher` não desiste: repete a mensagem pendente com recuo 1, 2, 4... 30 s, então
   `seq` nunca pula nem inverte. Custo: o laço do coletor espera enquanto o broker estiver caído (em QoS 0 uma
   mensagem em trânsito na queda ainda pode se perder; o servidor a vê como lacuna de `seq`).
3. **Veículo e fonte.** O nome do veículo vem de `mqtt.veiculo` (padrão `simulado`); o assinante usa `+` e aceita
   qualquer veículo, gravando tudo na mesma execução (a spec não define multiveículo). Relatório de DTC grava na
   execução com fonte `desconhecida`, igual ao HTTP.
4. **Mensagem inválida.** JSON fora do schema é descartado e contado em `MqttSubscriber.rejected` (sem 4xx para devolver).
5. **Ativação no servidor.** `create_app(..., mqtt_link=fábrica)` liga o assinante no `lifespan`. Ler `publisher`
   do YAML e subir o processo fica para o `make run`, ainda não implementado. `build_publisher(config)` faz a escolha no coletor.
6. **Teste `broker`.** `addopts` ganhou `-m "not broker"`; rode `pytest -m broker` com `docker compose --profile mqtt up -d mosquitto`.
   O teste real não foi executado aqui (sem Docker/broker); foi pulado por design.
7. **`docker-compose.yml`.** Só tem o Mosquitto; os serviços do app não entraram (ainda não há `make run`).

## Tarefa 07 (dashboard)

1. **Sem captura de tela.** Não há navegador/Playwright no ambiente; o checklist manual (valores mudam, MIL com P0300, "reconectando") e a validação visual de layout ficam pendentes. Coberto por teste: HTML servido, `node --check`, ids usados pelo JS existem no HTML, lógica pura (`gauges.js`) via Node e entrega da amostra no `WS /ws/stream`.
2. **Latência no cabeçalho** = relógio do navegador − `ts` da amostra (mesma máquina; com relógios diferentes seria enviesada). A spec não define a fonte.
3. **Escalas assumidas:** rotação 0–8000 (faixa vermelha em 6000), coletor −1 a +1,5 bar relativo a 101,325 kPa, tensão 9–16 V; faixas de cor de temperatura/combustível/velocidade são palpites.
4. **Gráfico** usa o relógio do navegador na chegada, não o `ts` da amostra, e só guarda os 60 s recebidos (o replay do WS chega de uma vez e fica comprimido na borda direita).
5. **"Sem sinal":** após 3 s sem amostra, a tela fica cinza com aviso; os números antigos permanecem apenas esmaecidos sob o aviso.

## Tarefa 08 (painel de controle)

1. **Caminho dos arquivos.** A tarefa cita `simulator/control_api.py` e `web/simulator_panel/`. Decisão: `src/obd/simulator/control_api.py` e `src/obd/web/simulator_panel/`, seguindo o layout do CLAUDE.md.
2. **Faixa dos overrides.** A spec não define faixas. Decisão: a faixa aceita é a que o PID consegue codificar (rpm 0–16383,75; velocidade 0–255; arrefecimento −40–215; borboleta e combustível 0–100; tensão 0–65,535). Fora disso, `422`. Os sliders do painel usam faixas realistas (rpm 0–7000, tensão 9–16 V), que são escolha de interface.
3. **Variável desconhecida** em `/sim/override/{nome}` retorna `404`; corpo inválido retorna `422` (validação do Pydantic).
4. **Estado físico x valor servido.** `GET /sim/state` traz `variaveis` (o que a ECU responde, já com override) e `fisico` (estado limpo do modelo). Assim o override de 3000 rpm aparece no estado e na leitura do PID 0x0C.
5. **Monitor de quadros.** A ECU não expõe o tráfego, então `Simulator` registra os quadros de entrada (`on_frame`) e de saída (`poll`) sem mudar `ecu.py`. `WS /sim/stream` envia, a cada 100 ms, o estado e os quadros novos desde a mensagem anterior.
6. **Reiniciar com semente** reconstrói modelo, ECU e falhas, mantendo o perfil de condução e o monitor. Overrides, DTCs, atraso e rede voltam aos valores iniciais.
7. **Limites de entrada.** Atraso de 0 a 1000 ms (acima disso o coletor de 100 ms já estoura o timeout); perda e corrupção de 0 a 1; sementes de 0 a 2³²−1. Limites escolhidos, não definidos na spec.
8. **Nomes das variáveis** seguem a spec: `rpm`, `speed`, `coolant`, `throttle`, `fuel`, `voltage`. O estado usa chaves em português (`variaveis`, `fisico`, `perfil`, `latencia`, `rede`, `sem_resposta`).
9. **Painel servido em `/`** da aplicação do simulador, montado depois das rotas da API. Não há comando para subir a porta 8001 ainda: o `make run` continua sem alvo real.

## Tarefa 09 (ELM327)

1. **Caminho dos arquivos.** `src/obd/simulator/elm327_server.py` e `src/obd/transport/elm327_tcp.py`, conforme o layout do CLAUDE.md.
2. **Servidor sobre um `Transport`.** `Elm327Server(backend)` fala com a ECU por um transporte (nos testes, `LoopbackTransport`). Assim ISO-TP, atraso e falhas injetadas valem também no ELM327. Tempo de espera pela ECU: 200 ms (o `ATST` padrão do chip real), escolha nossa.
3. **Padrões após `ATZ`:** eco ligado, espaços ligados, linefeed e cabeçalhos desligados, como no chip. O servidor ecoa o próprio `ATE0` (o eco ainda estava ligado ao recebê-lo) e não ecoa `ATZ`; não confirmado contra um chip real.
4. **Sem DTCs no Modo 03.** A ECU responde `43 00`; o servidor converte em `NO DATA`, como diz a spec. Um adaptador real costuma imprimir `43 00`.
5. **VIN (Modo 09).** Devolvido em uma linha só, já remontado (`49 02 01 ...`), como pede a tarefa. Adaptadores reais imprimem multilinha (`0:`/`1:`); o cliente aceita as duas formas, mas apps de terceiros podem esperar a multilinha.
6. **Comandos fora do escopo** (`ATST`, `ATAT`, `ATSH`, outros `ATSPn`…) devolvem `?`. Apps de terceiros podem enviá-los; ampliar se a validação manual falhar.
7. **Cliente.** Timeout do primeiro pedido é de ao menos 5 s (busca de protocolo); `NO DATA`, `?` e erros do chip viram `None` (o coletor trata como timeout). `build_transport("elm327_tcp")` ganhou `host` e `port`.
9. **Atualização (tarefa 16).** O formato de resposta foi validado contra o python-OBD 0.7.3 (cliente de terceiros), não contra um chip real. Itens 3 e 6 mudaram: `ATH1` imprime `7E8 <PCI> <dados>` por quadro (sem preenchimento 0x55); `ATDPN`, `ATSPn`/`ATTPn`, `ATAT`, `ATST`, `ATSH`, `ATCAF`, `ATS`, `ATAL`, `ATCRA` são aceitos; serviço/PID sem suporte e a negativa `7F` da ECU viram `NO DATA`; `0900` devolve `49 00 40 00 00 00`. Com `ATH0` o multiquadro continua em uma linha. Dúvida: um chip real imprime `NO DATA` também para `7F` de serviço não suportado? Assumido que sim. Apps de celular seguem sem teste.
8. **Validação manual com app de terceiros** (`docs/ensaios.md`) não foi feita: exige cliente real e é interativa. Pendente.

## Tarefa 10 (ensaios)

1. **Um processo, tarefas `asyncio`.** A tarefa pede "processos", mas o valor real só existe em `ecu.log`, dentro do processo da ECU. Decisão: simulador, coletor e servidor (uvicorn real, HTTP em `127.0.0.1`, SQLite em arquivo) rodam como tarefas de um processo. O coletor usa `LoopbackTransport`, então os ensaios não passam por `python-can` nem medem o custo do barramento virtual; o campo `source` das amostras diz `can_virtual`.
2. **Junção do valor real.** `ecu.log` guarda `(request_id, valor)`, mas o `Sample` não tem `request_id`. `TruthTransport` anota o valor logo após cada requisição `01 PID` e `TruthPublisher` o associa ao `seq` na hora de publicar. Depois o executor grava `readings.true_value` no SQLite (`<ensaio>_<run>.db`).
3. **Ciclo de 10 PIDs.** Os 10 PIDs implementados (`0x06` inclusive) entram em todo ciclo; o plano padrão do coletor lê 5 deles a cada 5 ciclos e subestimaria o ciclo de RNF01.
4. **Critérios dos RNF.** RNF01 e RNF02 pelo p95 (mais rígido que a média). RNF03 = publicadas − recebidas + lacunas de `seq`. RNF04: IDs de 11 bits e RTT máximo ≤ P2 (50 ms); os 500 kbit/s são nominais (barramento virtual não tem taxa) e não são medidos.
5. **Falha do E1.** P0300 agendada em 100/240 da duração (100 s no ensaio completo). Detecção = instante em que o coletor publica o relatório com o código menos o instante agendado; o piso é o período de 2 s do PID 0x01.
6. **Parâmetros que a spec não fixa.** E2: atraso fixo (mín = máx). E4: 30 s por execução; perda aplicada às requisições recebidas pela ECU (o coletor vê timeout de 100 ms); "recuperação" = maior sequência de ciclos seguidos sem leitura do mesmo PID. E5: 100 repetições, STmin enviado pelo testador no FC. E6: cliente de soquete cru com 19 comandos e respostas esperadas por expressão regular; não substitui a validação com app de terceiros.
7. **E7 sem Mosquitto.** Se não há broker em `localhost:1883`, o canal MQTT usa o `FakeBroker` em memória de `tests/fakes.py`; o JSON registra `broker`. Nesse caso a latência MQTT não inclui rede nem broker real e não é comparável ao HTTP sem ressalva.
8. **Pacote `tests/benchmarks`.** Tem `__init__.py` e imports relativos para funcionar em `python -m tests.benchmarks.eN` e no pytest (`benchmarks.*`). `tests/` não pode ganhar `__init__.py`: quebra o `import fakes` dos outros testes no mypy.
9. **Desvio padrão** amostral (n − 1); percentis por posto mais próximo, como em `GET /api/stats`.
10. **Segunda máquina.** Não há segunda máquina aqui: `docs/ensaios.md` traz as instruções, mas só uma máquina foi medida. Pendente.

## Tarefa 13 (orquestração do `make run`)

1. **Capturas de tela.** O Playwright e o Chromium (headless shell) instalaram, mas o
   navegador não abre: faltam bibliotecas do sistema (`libnss3`, `libatk`, `libgbm`, `libasound`
   etc.) e o ambiente não tem root para instalá-las. Sem as PNG em `docs/img/`. Para gerar:
   `playwright install-deps chromium` com privilégio e repetir a captura com `make run` ativo
   (aplicar `PUT /sim/override/rpm` e `POST /sim/dtc` antes, e conferir que não há "reconectando").
2. **Dependência `websockets`.** O uvicorn só atende `WS /ws/stream` com uma biblioteca de
   WebSocket; adicionada ao `pyproject.toml` (não vinha em `uvicorn` puro).
3. **Código-base.** A branch `night/20261024` não continha as tarefas 01–10 e 12 (estavam
   empilhadas em `task/10-ensaios`); `task/13-run-orquestracao` parte de `task/10-ensaios`
   mais `main`.
4. **Transporte do coletor.** `coletor.transporte: loopback` (padrão) compartilha com o servidor
   ELM327 a mesma instância de `LoopbackTransport` sobre o `Simulator` (um só lock, e `POST
   /sim/seed` continua valendo). `elm327_tcp` conecta no próprio servidor ELM327 do processo
   (exige não usar `--sem-elm327`). `can_virtual` não tem ECU ligada ao barramento neste
   processo; fica fora do `run`.
5. **Interface de escuta.** `--host` (padrão 127.0.0.1); a imagem Docker usa 0.0.0.0. O
   `docker compose` não pôde ser validado aqui (Docker ausente no ambiente).
6. **`make run` e Ctrl+C.** O encerramento limpo (código 0, sem traceback) é provado por SIGINT
   e SIGTERM nos testes de subprocesso; o `make` em si propaga o código do processo.

## Tarefa 14 (correções do dashboard e do painel)

1. **Fonte da amostra.** O `python -m obd run` usa `coletor.transporte` (padrão `loopback`);
   `can.transporte: virtual` não era lido por nada e contradizia o `source` das amostras.
   Decisão: `can.transporte` passou a `loopback` (mesmo valor) e o teste de integração compara
   `source` de `/api/latest` com o transporte configurado. O campo já refletia a verdade
   (`transport.name`); só a configuração estava incoerente.
2. **PIDs lentos ausentes.** O ajuste de mistura (0x06) não estava no plano do coletor, então a
   barra ficava sempre em "–". Decisão: 0x06 entrou no plano (a cada 5 ciclos) e em `pids`,
   junto com 0x42 (tensão).
3. **Defasagem.** Valor sem atualização por mais de 5 s fica esmaecido (`.defasado`); só é
   "ausente" (–) se nunca chegou. Na reconexão o replay de 60 s carimba os valores com a hora
   da chegada (a amostra não traz a hora de leitura de cada PID no dashboard).
4. **Inspeção das capturas (1280 px).** `docs/img/dashboard.png`: sem "–" em velocidade,
   temperatura, combustível e nas quatro barras; rótulos VELOCIDADE/TEMPERATURA/COMBUSTÍVEL
   separados; textos "3000 rpm" e "-0.62 bar" não cobrem mais os números da escala.
   `docs/img/painel.png`: botões "Automático" inteiros e sliders visíveis. Observação: o gráfico
   de 60 s mostra só o degrau de 800 para 3000 rpm no início da sessão (captura feita em ~5 s).

## Tarefa 15 (redesenho visual)

1. **Tokens compartilhados.** Os dois servidores montam pastas estáticas separadas, então o
   bloco `:root` (cores, espaços, raio, fonte) está duplicado em `dashboard/style.css` e
   `simulator_panel/style.css`; um teste confere que os tokens existem nos dois.
2. **Mudou (antes em `docs/img/antes`, depois em `docs/img`).** Tema claro único (o painel
   perdia o tema escuro automático), grade de 12 colunas, conta-giros e velocidade em destaque,
   bloco secundário (temperatura, combustível, tensão, carga, borboleta, mistura), gráfico com
   abas, área, grade e eixos, MIL vermelho, estados de conexão com ponto colorido, painel com
   interruptor, botões primário e secundário, monitor com requisição (azul) e resposta (verde).
3. **Ainda incomoda.** Cartão de velocidade fica vazio quando o carro está parado; o gráfico
   da captura mostra só o degrau inicial (captura em ~5 s); o status do DTC vem em inglês
   ("stored") da API e não foi traduzido (mudaria contrato); o `Automático` aparece esmaecido
   em vez de oculto quando não há sobreposição. Não foi verificado a 1920 px por captura.

## Tarefa 17 (conformidade ELM327)

1. **`--config perfil.json`.** A tarefa não define o formato. Decidido: JSON com `ignorar`
   (comandos) e `esperado` (comando para resposta crua), aplicado a todas as ocorrências do
   comando. Serve, por exemplo, para o `ATRV` do ESP32, que lê a tensão real.
2. **"Estado esperado" do roteiro.** Guardado como dados em `roteiro.py` (eco, avanço de linha,
   espaços, cabeçalhos depois de cada passo), mas a verificação é pela resposta crua do
   dourado, que já carrega o efeito do estado.
3. **Escopo do dourado.** Valores fixos e sem DTCs; por isso `03` esperado é `NO DATA`. O caso
   `43 01 03 00` está na spec, mas não no roteiro (o firmware não tem injeção de DTC garantida).
4. **Dourado gerado do simulador.** Se o simulador estiver errado, o dourado herda o erro;
   continua sem conferência contra um ELM327 real. `python -m tests.conformance.gerar` regenera e
   um teste falha se o arquivo ficar defasado.
5. **Divergências encontradas na spec 04.** A linha `ATSP6`/`ATSP0` diz só "CAN 11 bits"; o
   código também aceita `ATSPA6` e `ATTP`, e `ATDP` muda com o modo (AUTO). Documentado na 09.

## Tarefa 18 (coletor com adaptador real)

1. **Como o coletor sabe o erro do chip.** O contrato `Transport.request` continua devolvendo
   `None`. O `Elm327TcpTransport` expõe `last_error` (`CAN ERROR`, `NO DATA`, `?`,
   `conexão perdida`...), lido com `getattr` pelo coletor; transportes sem o atributo seguem
   gerando `timeout`. Erro do chip vira evento `adapter_error`, conta em `errors.invalid` e
   não grava valor. Estouro de tempo continua `timeout`.
2. **`NO DATA` no modo 03** (sem DTCs, conforme spec 04) é lido como lista vazia, não como falha.
3. **Resposta atrasada.** Após estouro de tempo, o transporte descarta a resposta atrasada
   (até o próximo `>`) antes do comando seguinte; sem isso ela seria tomada como a do PID seguinte.
4. **Reconexão.** Só o transporte reconecta (reenvia `ATZ`, `ATE0`, `ATL0`, `ATS0`, `ATH0`, `ATSP0`);
   a consulta em que a queda foi notada falha, a seguinte reconecta. Recuo: 1ª tentativa
   imediata, depois 200 ms dobrando até 5 s (parâmetros do construtor, fora do YAML).
   `seq` é do coletor e não depende do soquete.
5. **Padrões do YAML.** `coletor.timeout_ms` passou de 100 para 500 (Wi-Fi) e entrou
   `coletor.timeout_busca_s: 5.0` (só a 1ª consulta após conectar).
6. **Injeção no servidor.** `ErrorInjection` (`errors`, `extra_delay_ms`, `drop_connection_after(n)`,
   `record`/`seen`), desligada por padrão. `errors` vale só para comandos OBD; a queda é única
   e ocorre após responder o N-ésimo comando.
