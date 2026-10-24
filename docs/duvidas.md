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
