# Plano de sessões

Gerado a partir de `tasks/*.md`. Uma tarefa por sessão. O modelo é o mais barato que dá conta; sobe um nível só se a condição de escalada ocorrer. Para regenerar: skill `plan-sessions`.

## Ordem de execução

| Ordem | Sessão | Tarefa | Modelo | Depende de | Paralelizável com | Peso | Escalar se |
|---|---|---|---|---|---|---|---|
| 1 | S1 | [00 Fundação](../tasks/00-fundacao.md) | haiku | nenhuma | nenhuma | P | lint/test falham após 2 iterações |
| 2 | S2 | [01 Protocolo base](../tasks/01-protocolo-base.md) | sonnet | 00 | nenhuma | M | fórmulas/propriedades falham após 2 iterações |
| 3 | S3 | [02 ISO-TP](../tasks/02-isotp.md) | sonnet | 01 | nenhuma | M | remontagem falha após 2 iterações |
| 4 | S4 | [03 Transporte e ECU](../tasks/03-transporte-ecu.md) | sonnet | 01, 02 | 06 | M | corrida/ISO-TP após 2 iterações |
| 5 | S5 | [04 Modelo de veículo e falhas](../tasks/04-modelo-veiculo-falhas.md) | sonnet | 03 | 06 | M | não determinístico após 2 iterações |
| 6 | S6 | [05 Coletor](../tasks/05-coletor.md) | sonnet | 03 | 06 | M | recuo/ordem intermitente |
| 7 | S7 | [06 Servidor e banco](../tasks/06-servidor-banco.md) | haiku | 01 | 02 a 05 | M | WebSocket/seq falha: passar para sonnet |
| 8 | S8 | [07 Dashboard](../tasks/07-dashboard.md) | sonnet | 06 | 05, 08, 09 | M | layout errado após 2 iterações |
| 9 | S9 | [08 Painel de controle](../tasks/08-painel-controle.md) | haiku | 04 | 05 a 07, 09 | P | override falha: passar para sonnet |
| 10 | S10 | [09 ELM327](../tasks/09-elm327.md) | sonnet | 03 | 05 a 08 | M | handshake falha após 2 iterações |
| 11 | S11 | [10 Ensaios](../tasks/10-ensaios.md) | sonnet | 04, 05, 06, 09 | nenhuma | M | métricas inconsistentes |
| 12 | S12 | [11 Texto do TCC](../tasks/11-texto-tcc.md) | sonnet | 10 | nenhuma | M | revisão final de coerência: opus uma vez |

**MVP:** fim da tarefa 07 (coleta, servidor, banco e dashboard funcionando de ponta a ponta).

## Caminho crítico

00, 01, 02, 03, 04 ou 05, 10, 11. As tarefas 06, 07, 08 e 09 saem do caminho crítico e podem rodar em paralelo, em sessões separadas.

## Como lançar uma sessão

1. `/clear`
2. `/model <modelo da tabela>`
3. Colar o prompt de lançamento do final do arquivo da tarefa (uma linha).

Exemplo para a S2:

```text
/model sonnet
Leia apenas tasks/01-protocolo-base.md e as seções de docs/spec citadas nele. Escreva os testes primeiro, implemente, rode os comandos do critério de pronto e mostre só as falhas.
```

## Regras de modelo

- **Haiku:** estrutura, CRUD, scripts e painéis simples.
- **Sonnet:** lógica de protocolo, concorrência, SVG e análise.
- **Opus:** só para revisão de arquitetura, bug que resistiu a 2 tentativas do Sonnet e uma revisão final de coerência do texto.
- Em empate, o mais barato. Nunca subir de modelo "por precaução".

## Pontos de contagem de tokens

- Após cada sessão: commit, `/clear`.
- Saída de teste sempre curta (`pytest -q --tb=short`).
- Tarefas de peso M podem ser divididas em duas sessões se o contexto passar de ~60%.
