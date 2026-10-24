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
