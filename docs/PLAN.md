# Plano de sessões

Gerado a partir de `tasks/*.md`. Uma tarefa por sessão. O modelo é o mais barato que dá conta; sobe um nível só se a condição de escalada ocorrer. Para regenerar: skill `plan-sessions`.

## Ordem de execução

| Ordem | Sessão | Tarefa | Modelo | Depende de | Paralelizável com | Peso | Escalar se |
|---|---|---|---|---|---|---|---|
| 1 | S1 | [00 Fundação do repositório](../tasks/00-fundacao.md) | haiku | nenhuma | nenhuma | P | make test ou make lint ainda falham após 2 iterações |
| 2 | S2 | [01 Núcleo de protocolo (PIDs, DTCs, quadros, serviços e schemas)](../tasks/01-protocolo-base.md) | sonnet | 00 | nenhuma | M | testes de propriedade ou de fórmulas seguem falhando após 2 iterações |
| 3 | S3 | [02 ISO-TP completo e Modos 02 e 09](../tasks/02-isotp.md) | sonnet | 01 | nenhuma | M | remontagem multiquadro falha em algum comprimento após 2 iterações |
| 4 | S4 | [03 Transporte plugável e ECU virtual](../tasks/03-transporte-ecu.md) | sonnet | 01, 02 | 06 | M | a ECU não responde corretamente ao ISO-TP ou há condição de corrida após 2 iterações |
| 5 | S5 | [04 Modelo de veículo, perfis de condução e falhas](../tasks/04-modelo-veiculo-falhas.md) | sonnet | 03 | 06 | M | o modelo não é determinístico com as mesmas sementes após 2 iterações |
| 6 | S6 | [05 Coletor (descoberta, plano de leitura, recuperação e publicação)](../tasks/05-coletor.md) | sonnet | 03 | 06 | M | recuo progressivo ou ordem de eventos falham de forma intermitente após 2 iterações |
| 7 | S7 | [06 Servidor, API e banco de dados](../tasks/06-servidor-banco.md) | haiku | 01 | 02, 03, 04, 05 | M | o WebSocket ou a detecção de perda por seq falha após 2 iterações; passar para sonnet |
| 8 | S8 | [12 MQTT (publicador, assinante e Mosquitto no Compose)](../tasks/12-mqtt.md) | sonnet | 05, 06 | 07, 08, 09 | M | o assinante perde mensagens ou duplica registros após 2 iterações |
| 9 | S9 | [07 Dashboard web](../tasks/07-dashboard.md) | sonnet | 06 | 05, 08, 09, 12 | M | layout ou animação continuam errados após 2 iterações com captura de tela |
| 10 | S10 | [08 API de controle e painel do simulador](../tasks/08-painel-controle.md) | haiku | 04 | 05, 06, 07, 09, 12 | P | overrides não refletem na leitura após 2 iterações; passar para sonnet |
| 11 | S11 | [09 Camada ELM327 (servidor TCP e cliente)](../tasks/09-elm327.md) | sonnet | 03 | 05, 06, 07, 08, 12 | M | cliente de terceiros não conclui o handshake após 2 iterações |
| 12 | S12 | [10 Ensaios E1 a E7, métricas e gráficos](../tasks/10-ensaios.md) | sonnet | 04, 05, 06, 09, 12 | nenhuma | M | métricas inconsistentes entre execuções com as mesmas sementes após 2 iterações |
| 13 | S13 | [13 Orquestração (make run), serviços no Compose e verificação de ponta a ponta](../tasks/13-run-orquestracao.md) | sonnet | 05, 06, 07, 08, 09, 12 | nenhuma | M | o processo não sobe ou não encerra limpo após 2 iterações, ou a amostra não chega ao dashboard |
| 14 | S14 | [14 Correções do dashboard e do painel e script de capturas de tela](../tasks/14-dashboard-correcoes.md) | sonnet | 13 | nenhuma | P | valores lentos continuam piscando ou sumindo após 2 iterações |
| 15 | S15 | [15 Redesenho visual do dashboard e do painel do simulador](../tasks/15-dashboard-design.md) | sonnet | 14 | nenhuma | M | o resultado visual continua desorganizado ou parecido com o anterior após 2 iterações: usar opus uma vez para direção de design |
| 16 | S16 | [16 Compatibilidade do ELM327 simulado com clientes reais (python-OBD)](../tasks/16-elm327-clientes-reais.md) | sonnet | 09, 13 | nenhuma | M | o python-OBD ainda não lê rotação, velocidade e DTCs após 2 iterações |
| 17 | S17 | [11 Reescrita dos capítulos do TCC com os resultados reais](../tasks/11-texto-tcc.md) | sonnet | 10, 13, 15, 16 | nenhuma | M | revisão final de coerência entre objetivos, método e conclusões: usar opus uma vez |
| 18 | S18 | [17 Especificação do dialeto ELM327 e suíte de conformidade contra qualquer endereço TCP](../tasks/17-elm327-conformidade.md) | sonnet | 16 | nenhuma | M | a suíte não consegue distinguir respostas corretas de incorretas entre duas implementações após 2 iterações |
| 19 | S19 | [18 Coletor tolerante a respostas de erro, atrasos e quedas de um adaptador real](../tasks/18-coletor-adaptador-real.md) | sonnet | 16, 17 | nenhuma | M | a reconexão deixa o coletor em estado inconsistente ou há condição de corrida após 2 iterações |
| 20 | S20 | [19 Firmware do ESP32 DevKit como adaptador ELM327 por Wi-Fi](../tasks/19-firmware-esp32.md) | sonnet | 17, 18 | nenhuma | G | o ISO-TP multiquadro (VIN, DTCs) falha em algum comprimento após 2 iterações: usar opus uma vez |

**MVP:** fim da tarefa 07 (dashboard); o MQTT (12) entra antes dele na ordem (coleta, servidor, banco e dashboard funcionando de ponta a ponta).

## Caminho crítico

00, 01, 02, 03, 05, 12, 10, 11. As tarefas 17, 18 e 19 (ESP32) ficam depois do texto do TCC e não bloqueiam a entrega. As tarefas 06, 07, 08, 09 e 12 saem do caminho crítico e podem rodar em paralelo, em sessões separadas.

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
