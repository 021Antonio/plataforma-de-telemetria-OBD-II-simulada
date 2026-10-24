# 4. Protocolo OBD-II

## Quadros CAN (ISO 15765-4, 11 bits, 500 kbit/s)

| Campo | Valor |
| --- | --- |
| Requisição funcional | ID `0x7DF` (todas as ECUs) ou físico `0x7E0` a `0x7E7` |
| Resposta da ECU do motor | ID `0x7E8` |
| Tamanho do quadro | Sempre 8 bytes, com preenchimento `0x55` nos bytes não usados |
| Tempo máximo de resposta (P2) | 50 ms |
| Tempo de quadro (pior caso, 8 bytes) | 270 µs (C = 47 + 8s + ⌊(34 + 8s − 1)/4⌋) |

## ISO-TP (primeiro byte do campo de dados)

| Tipo | Byte PCI | Conteúdo |
| --- | --- | --- |
| Quadro único (SF) | `0x0N` | N = bytes úteis (1 a 7) |
| Primeiro quadro (FF) | `0x1L LL` | Comprimento total em 12 bits, depois 6 bytes de dados |
| Quadro consecutivo (CF) | `0x2S` | S = sequência 0 a F, 7 bytes de dados |
| Controle de fluxo (FC) | `0x30 BS STmin` | Enviado pelo coletor após o FF: continuar, bloco, espaçamento |

A ECU simulada envia o FF, espera o FC, envia os CFs respeitando `STmin` e `BS`. O coletor remonta e valida o comprimento. Estouro de N_Cr (1 s) aborta a recepção.

## Serviços (modos)

| Modo | Requisição | Resposta | Observação |
| --- | --- | --- | --- |
| 01 | `01 PID` | `41 PID dados` | Dados atuais |
| 02 | `02 PID 00` | `42 PID 00 dados` | Freeze frame |
| 03 | `03` | `43 N` + N×2 bytes | N = número de DTCs (em CAN) |
| 04 | `04` | `44` | Limpa DTCs e freeze frame |
| 07 | `07` | `47 N` + N×2 bytes | DTCs pendentes |
| 09 | `09 02` | `49 02 01` + 17 bytes | VIN, resposta multiquadro |
| negativa | qualquer inválida | `7F modo código` | Ex.: `7F 01 12` (sub-função não suportada) |

PID sem suporte não recebe resposta. O coletor trata isso como timeout apenas se o PID não foi anunciado na descoberta.

## PIDs implementados

| PID | Grandeza | Bytes | Fórmula | Unidade | Resolução |
| --- | --- | --- | --- | --- | --- |
| 0x00, 0x20, 0x40 | PIDs suportados | 4 | Máscara de 32 bits, bit 31 = primeiro PID da faixa | n/a | n/a |
| 0x01 | Estado do monitor | 4 | A bit 7 = MIL, bits 0 a 6 = nº de DTCs | n/a | n/a |
| 0x04 | Carga calculada | 1 | A·100/255 | % | 0,392 |
| 0x05 | Temp. arrefecimento | 1 | A − 40 | °C | 1 |
| 0x06 | Ajuste combustível curto prazo | 1 | (A − 128)·100/128 | % | 0,781 |
| 0x0B | Pressão do coletor (MAP) | 1 | A | kPa | 1 |
| 0x0C | Rotação | 2 | (256A + B)/4 | rpm | 0,25 |
| 0x0D | Velocidade | 1 | A | km/h | 1 |
| 0x0F | Temp. ar de admissão | 1 | A − 40 | °C | 1 |
| 0x11 | Borboleta | 1 | A·100/255 | % | 0,392 |
| 0x2F | Nível de combustível | 1 | A·100/255 | % | 0,392 |
| 0x42 | Tensão do módulo | 2 | (256A + B)/1000 | V | 0,001 |

## DTC (2 bytes)

Os dois bits mais altos do primeiro byte dão o sistema (`00` P, `01` C, `10` B, `11` U), os dois seguintes o primeiro dígito (0 a 3) e o restante forma os três dígitos hexadecimais. Exemplo: `03 00` é `P0300`. A tabela de descrições fica em `protocol/dtc.py` e cobre, no mínimo, P0300 a P0304, P0171, P0172, P0420 e P0133.

## Camada ELM327 (porta TCP 35000)

| Entrada | Saída | Comportamento |
| --- | --- | --- |
| `ATZ` | `ELM327 v1.5` | Reinicia |
| `ATE0`, `ATL0`, `ATS0`, `ATH0` | `OK` | Sem eco, sem avanço de linha, sem espaços, sem cabeçalho |
| `ATSP6` ou `ATSP0` | `OK` | Protocolo CAN 11 bits 500 kbit/s |
| `ATDP` | `ISO 15765-4 (CAN 11/500)` | Protocolo atual |
| `ATRV` | `12.6V` | Tensão lida do modelo |
| `0100` | `41 00 BE 3F A8 13` | Em hexadecimal, com espaços se `ATS1` |
| `010C` | `41 0C 1F 40` | Resposta decodificável |
| `03` | `43 01 03 00` ou `NO DATA` | Sem DTCs |
| comando desconhecido | `?` | Conforme o ELM327 real |
| PID sem suporte | `NO DATA` | Idem |

Toda resposta termina com `\r\r>` (prompt). O primeiro `0100` após `ATZ` pode devolver `SEARCHING...` antes da resposta, como no chip real. Os formatos acima vêm do conhecimento do protocolo e devem ser conferidos contra um cliente ELM327 real.
