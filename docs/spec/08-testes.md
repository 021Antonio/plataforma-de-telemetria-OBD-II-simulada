# 8. Testes e critérios de aceitação

## Pirâmide de testes

| Nível | O que cobre | Ferramenta |
| --- | --- | --- |
| Unitário | Fórmulas de PID, DTC, quadros, ISO-TP, validação de resposta | pytest |
| Propriedade | `decode(encode(x))` dentro de r/2 para 1.001 valores por PID; remontagem ISO-TP para qualquer comprimento de 8 a 4095 bytes | hypothesis |
| Integração | Coletor contra ECU simulada pelo `can_virtual`; servidor com `InMemoryStorage`; servidor ELM327 com cliente falso | pytest-asyncio |
| Ponta a ponta | Simulador, coletor, servidor e WebSocket no ar, com leitura do WebSocket | pytest + processos |
| Desempenho | Ensaios E1, E2 e E3 com coleta de métricas | scripts em `tests/benchmarks` |

## Ensaios de desempenho

| Ensaio | Cenário | Medidas |
| --- | --- | --- |
| E1 | 240 s, 10 PIDs, ECU em 10 ms ± 3 ms, falha P0300 aos 100 s | Erro por PID, RTT, ciclo, latência, perdas, tempo de detecção da falha |
| E2 | 4 execuções de 30 s com ECU em 0, 10, 25 e 50 ms | Ciclo e taxa em função do atraso |
| E3 | 4 execuções de 20 s com 1, 3, 5 e 10 PIDs | Taxa por PID e leituras por segundo |
| E4 (novo) | Perda de 0, 1, 5 e 10% dos quadros | Timeouts, recuperação, taxa efetiva |
| E5 (novo) | VIN por ISO-TP com `STmin` de 0, 1 e 10 ms | Tempo de remontagem |
| E6 (novo) | Cliente ELM327 comum contra o servidor TCP | Compatibilidade de comandos |

Cada ensaio grava um CSV e um JSON em `runs/<data>/` com a configuração e as sementes. A estatística reportada é média, desvio padrão, mediana, p95, p99 e máximo. Repetir cada ensaio em uma segunda máquina, como no TCC, e declarar as diferenças.

## Como o valor real chega para medir o erro

A ECU simulada registra, para cada resposta, o par `(request_id, true_value)`. O executor de ensaios junta esse registro ao `Sample` pelo `seq`, e grava o resultado em `readings.true_value`. O coletor nunca tem acesso ao valor real.

## Critérios de aceitação do projeto

- Todos os requisitos RF01 a RF12 com teste automatizado passando.
- RNF01 a RNF04 atendidos nos ensaios E1 a E3.
- Cobertura de testes de pelo menos 80% em `protocol/`.
- `make run` sobe a plataforma completa e o dashboard mostra dados em até 5 s.
- Um cliente ELM327 de terceiros lê rotação e DTCs do servidor TCP.
