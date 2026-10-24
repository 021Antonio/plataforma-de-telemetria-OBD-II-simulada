# 9. Dialeto ELM327 (porta TCP 35000)

Descreve o que `src/obd/simulator/elm327_server.py` faz hoje. O firmware do ESP32 (tarefa 19) deve responder igual. A suíte `tests/conformance` confere byte a byte; as respostas esperadas estão em `tests/conformance/dourado.json`.

Execução: `python -m tests.conformance --host H --port P [--config perfil.json]`. O perfil JSON aceita `ignorar` (lista de comandos) e `esperado` (comando para resposta crua), para valores que mudam por alvo (ex.: `ATRV`). Sai com código 1 se houver divergência e 2 se não conectar.

## Formato da resposta

- A linha de entrada termina em `\r` (ou `\n`); espaços são ignorados e a caixa é indiferente.
- Saída: [eco da linha, se `ATE1`] + uma linha por item + linha vazia + `>`. O fim de linha é `\r` (`ATL0`) ou `\r\n` (`ATL1`). Logo, toda resposta termina em `\r\r>` (ou `\r\n\r\n>`).
- `ATZ` nunca ecoa. `ATE1` responde `OK` sem eco (o eco liga depois).
- Linha vazia não gera resposta (nem prompt).
- Estado inicial (e após `ATZ`): `ATE1`, `ATL0`, `ATS1`, `ATH0`, protocolo automático, `SEARCHING...` pendente.

## Comandos AT

| Entrada | Resposta | Observação |
| --- | --- | --- |
| `ATZ` | `ELM327 v1.5` | Reinicia o estado |
| `ATI`, `ATWS` | `ELM327 v1.5` | |
| `ATE0` / `ATE1` | `OK` | Eco desligado / ligado |
| `ATL0` / `ATL1` | `OK` | Fim de linha `\r` / `\r\n` |
| `ATS0` / `ATS1` | `OK` | Sem espaços / com espaços nos bytes |
| `ATH0` / `ATH1` | `OK` | Sem cabeçalho / com cabeçalho |
| `ATSP0`, `ATSPA0`, `ATTP0` | `OK` | Protocolo automático |
| `ATSP6`, `ATSPA6`, `ATTP6` | `OK` | Fixo em CAN 11/500 (`ATSPA6` mantém o automático) |
| `ATDP` | `AUTO, ISO 15765-4 (CAN 11/500)` ou, fixo, `ISO 15765-4 (CAN 11/500)` | |
| `ATDPN` | `A6` (automático) ou `6` (fixo) | |
| `ATRV` | `14.0V` | Tensão do PID 0x42 com uma casa; `12.6V` se a ECU não responde |
| `ATIGN` | `ON` | |
| `ATAT`, `ATST`, `ATSH`, `ATCAF`, `ATCRA`, `ATAL`, `ATD`, `ATM`, `ATR`, `ATPC`, `ATJHF`, `ATJS`, `ATFE`, `ATSW`, `ATWM`, `ATCF`, `ATCM`, `ATCS`, `ATV`, `ATKW`, `ATIB`, `ATBI`, `ATSS`, `ATCV` (qualquer sufixo) | `OK` | Aceitos sem efeito |
| `AT@1` | `OBD-II simulator (software-in-the-loop)` | |
| outro `AT...` | `?` | |

## Comandos OBD

Requisição em hexadecimal, de 1 a 7 bytes. Qualquer outra coisa (não hexadecimal, número ímpar de dígitos, mais de 7 bytes) responde `?`.

| Entrada | Resposta com `ATH0`, `ATS1` | Observação |
| --- | --- | --- |
| `0100` | `41 00 9C 3A 80 01` | Máscara dos PIDs suportados (valores do ensaio) |
| `0120` | `41 20 00 02 00 01` | |
| `010C` | `41 0C 30 DE` | Rotação 3127,5 rpm |
| `010D`, `0105`, `0111`, `0101` | `41 0D 4D`, `41 05 80`, `41 11 2F`, `41 01 00 00 00 00` | |
| `03` | `NO DATA` | Sem DTCs; com DTC: `43 01 03 00` |
| `0900` | `49 00 40 00 00 00` | Só o PID 0x02 do modo 09 |
| `0902` | `49 02 01 39 42 ... 31` | VIN remontado em uma linha |
| PID/serviço sem suporte (`01FF`, `0600`) | `NO DATA` | A negativa `7F` da ECU nunca chega ao cliente |
| desconhecido (`XYZ`) | `?` | |

### Variações

- **`ATS0`:** bytes sem espaço: `410C30DE`.
- **`ATH1`:** um quadro CAN por linha, `7E8` e o quadro ISO-TP sem o preenchimento `0x55`. Com espaços: `7E8 04 41 0C 30 DE`; sem: `7E8` imediatamente seguido dos bytes. Multiquadro (`0902`): `7E8 10 14 49 02 01 39 42 57`, `7E8 21 ...`, `7E8 22 ...` (FF, CF, CF).
- **`SEARCHING...`:** aparece como primeira linha só no primeiro `0100` depois de `ATZ` (ou da conexão); nas consultas seguintes não.
- **`ATE1`:** a resposta começa com a linha digitada (`010C\r41 0C 30 DE`).
- **`ATL1`:** `41 0C 30 DE\r\n\r\n>`.

## Respostas de erro do chip real

| Resposta | Significado no chip | O simulador gera? |
| --- | --- | --- |
| `?` | Comando não entendido | Sim |
| `NO DATA` | Nenhuma ECU respondeu no tempo | Sim (timeout, PID/serviço sem suporte, negativa) |
| `SEARCHING...` | Procurando protocolo | Sim, só no primeiro `0100` |
| `UNABLE TO CONNECT` | Nenhum protocolo achou a ECU | Não |
| `BUS INIT: ERROR` | Falha na inicialização (ISO 9141/KWP) | Não |
| `CAN ERROR` | Falha no barramento CAN | Não |
| `STOPPED` | Consulta interrompida por outro caractere | Não |
| `BUFFER FULL` | Buffer de recepção cheio | Não |

## Conferência

Os formatos vêm do conhecimento do protocolo e dos clientes testados na tarefa 16; continuam sem comparação com um chip ELM327 real (ver `docs/duvidas.md`).
