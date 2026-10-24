# 1. Visão geral, escopo e requisitos

O sistema reproduz em software a cadeia completa de telemetria veicular: um simulador responde como uma ECU (ISO 15765-4), um coletor requisita e decodifica PIDs e DTCs, um servidor armazena e distribui, e um dashboard mostra tudo em tempo real.

**Objetivo:** projetar, implementar e validar por testes automatizados uma plataforma aberta de telemetria OBD-II, independente de hardware, com transporte plugável.

## Dentro do escopo

- Simulador de ECU com modelo de veículo, ciclos de condução e injeção de falhas.
- Protocolo OBD-II sobre CAN: Modos 01, 02, 03, 04, 07 e 09, ISO-TP completo, descoberta de PIDs (0x00, 0x20, 0x40).
- Camada de compatibilidade ELM327 por socket TCP (comandos AT e OBD).
- Coletor (equivalente lógico do firmware do ESP32), servidor HTTP/WebSocket, banco de dados e dashboard.
- Painel de controle do simulador (sliders, botões de falha, perfis).
- Testes automatizados e coleta de métricas de exatidão, latência e taxa de atualização.

## Fora do escopo (limitação ou trabalho futuro)

- Hardware embarcado (ESP32, SN65HVD230, ESP8266) e ensaio em veículo real.
- Camada física CAN (níveis elétricos, terminação, ACK entre nós).
- K-Line, J1850 e CAN de 29 bits.
- Comandos de atuação no veículo: o sistema é somente leitura.
- Bluetooth, TLS e aplicativo móvel.

## Premissas

- Execução em um PC com Python 3.12 ou superior e Docker opcional.
- Todos os valores simulados têm valor físico real conhecido, o que permite medir o erro de decodificação.
- O simulador não pretende reproduzir um veículo específico, apenas gerar sinais coerentes.

## Requisitos funcionais

| ID | Requisito | Critério de aceitação |
| --- | --- | --- |
| RF01 | Simulador responde ao Modo 01 para os PIDs configurados | Resposta em 0x7E8 com modo + 0x40 e PID repetido |
| RF02 | Descoberta de PIDs suportados (0x00, 0x20, 0x40) | Máscara de 32 bits correta; coletor pede só PIDs suportados |
| RF03 | Leitura de DTCs (Modo 03), pendentes (Modo 07) e limpeza (Modo 04) | P0300 injetado aparece em até 2 ciclos de consulta; Modo 04 zera a lista |
| RF04 | Dados congelados (Modo 02) ao surgir uma falha | Freeze frame com os PIDs do instante da falha |
| RF05 | ISO-TP completo (primeiro quadro, consecutivos, controle de fluxo) | VIN de 17 caracteres lido via Modo 09 PID 0x02 |
| RF06 | Coletor requisita, valida e decodifica PIDs pelas fórmulas SAE J1979 | Erro máximo ≤ metade da resolução em 100% das leituras |
| RF07 | Servidor recebe a telemetria e a persiste | Nenhuma perda ou duplicação pelo número de sequência |
| RF08 | API HTTP de consulta e WebSocket de tempo real | Dashboard atualiza sem recarregar |
| RF09 | Painel de controle altera o simulador em tempo de execução | Mudança refletida na leitura em até 2 ciclos |
| RF10 | Camada ELM327 por TCP | Um cliente ELM327 comum completa ATZ, ATE0, 0100 e 010C |
| RF11 | Injeção de falhas de comunicação (atraso, perda, resposta inválida, sem resposta) | Coletor se recupera sem travar e registra o evento |
| RF12 | Transporte plugável por configuração | Trocar simulador por ELM327/TCP ou serial sem alterar o código do coletor |

## Requisitos não funcionais

| ID | Requisito | Meta |
| --- | --- | --- |
| RNF01 | Tempo de ciclo de 10 PIDs | ≤ 150 ms com ECU em 10 ms |
| RNF02 | Latência coletor ao banco | p95 ≤ 50 ms |
| RNF03 | Perda de mensagens | 0 em ensaio de 240 s |
| RNF04 | Conformidade com ISO 15765-4 | 11 bits, 500 kbit/s, P2 = 50 ms |
| RNF05 | Reprodutibilidade | Sementes fixas e ensaios repetíveis em 2 máquinas |
| RNF06 | Cobertura de testes | ≥ 80% nos módulos de protocolo |
| RNF07 | Instalação | Um comando (`docker compose up` ou `make run`) |
| RNF08 | Segurança | Somente leitura; API local, sem exposição externa por padrão |
