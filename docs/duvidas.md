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
