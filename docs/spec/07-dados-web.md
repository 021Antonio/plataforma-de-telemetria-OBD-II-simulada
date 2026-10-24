# 7. Banco de dados e interfaces web

## Esquema SQLite

| Tabela | Colunas principais | Observação |
| --- | --- | --- |
| `runs` | `id`, `started_at`, `source`, `seed_model`, `seed_ecu`, `profile`, `notes` | Uma linha por execução ou ensaio |
| `samples` | `id`, `run_id`, `seq`, `ts_pub`, `ts_recv`, `latency_ms`, `cycle_ms` | Uma linha por ciclo; `UNIQUE(run_id, seq)` |
| `readings` | `id`, `sample_id`, `pid`, `name`, `value`, `unit`, `rtt_ms`, `true_value` | Uma linha por PID; `true_value` só existe com simulador |
| `dtc_events` | `id`, `run_id`, `ts_recv`, `code`, `status`, `mil` | Mudanças de estado dos DTCs |
| `comm_events` | `id`, `run_id`, `ts`, `kind`, `detail` | Timeouts, quadros inválidos, reconexões |

Índices em `samples(run_id, seq)` e `readings(sample_id, pid)`. A coluna `true_value` é o que permite calcular o erro de decodificação por consulta SQL, sem reler arquivos. O valor real é preenchido pelo executor de ensaios (ver testes), nunca pelo coletor.

## Dashboard (porta 8000)

| Elemento | Dados | Comportamento |
| --- | --- | --- |
| Conta-giros | `rpm` | Ponteiro animado, faixa vermelha configurável |
| Manômetro do coletor | `map` | Escala em bar relativo, com vácuo negativo |
| Velocidade, temperatura, combustível | PIDs correspondentes | Mostradores numéricos com cor por faixa |
| Borboleta, carga, ajuste de mistura, tensão | PIDs correspondentes | Barras horizontais |
| Gráfico dos últimos 60 s | Séries selecionáveis | Atualização por WebSocket |
| Diagnóstico | MIL e lista de DTCs | MIL acende com DTC; clicar no código mostra a descrição |
| Cabeçalho | Estado da conexão, taxa (Hz), ciclo (ms), latência | Janela de 3 s |
| Eventos | Timeouts e reconexões | Lista com hora |

Estados da tela: conectado, reconectando e sem dados (fundo cinza e aviso, nunca valores antigos sem marca).

## Painel de controle do simulador (porta 8001)

| Controle | Ação na API |
| --- | --- |
| Sliders de rotação, velocidade, temperatura, borboleta, combustível e tensão | `PUT /sim/override/{nome}` |
| Botão "voltar ao automático" por variável | `DELETE /sim/override/{nome}` |
| Seletor de perfil de condução | `POST /sim/profile` |
| Lista de falhas com botão de injetar e limpar | `POST` e `DELETE /sim/dtc` |
| Sliders de atraso, perda e corrupção | `PUT /sim/latency` e `/sim/network` |
| Chave "ECU sem resposta" | `POST /sim/unresponsive` |
| Campo de sementes e botão reiniciar | `POST /sim/seed` |
| Monitor de quadros | `WS /sim/stream` mostra requisições e respostas em hexadecimal |
