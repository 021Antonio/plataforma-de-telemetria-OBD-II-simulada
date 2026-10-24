---
id: "16"
title: Compatibilidade do ELM327 simulado com clientes reais (python-OBD)
model: sonnet
session: 16
order: 16
depends_on: ["09", "13"]
parallel_with: []
weight: M
escalate_if: "o python-OBD ainda não lê rotação, velocidade e DTCs após 2 iterações"
spec: docs/spec/04-protocolo.md
---

## Contexto

O cliente real python-OBD (versão 0.7.3, `pip install obd`) foi apontado para `socket://127.0.0.1:35000` e **conectou** (reconheceu "ISO 15765-4 (CAN 11/500)"), mas **não leu nenhum PID** (`010C`, `010D`, `0105`... retornam "not supported"). Os testes unitários passavam porque o servidor foi testado contra o nosso próprio cliente. Troca observada:

```
ATZ     -> ELM327 v1.5
ATE0    -> ATE0 OK
ATH1    -> OK                      (mas as respostas continuam sem cabeçalho)
ATL0    -> OK
AT RV   -> 14.1V
ATSP0   -> OK
0100    -> SEARCHING... / 41 00 9C 3A 80 01     <- python-OBD: "Dropping frame for being odd"
ATDPN   -> ?                       <- deveria responder o protocolo (A6)
ATTP6   -> ?                       <- deveria responder OK
0600    -> 7F 06 11
0900    -> 7F 09 12                <- python-OBD espera a máscara de PIDs do modo 09
```

## Correções

1. **Cabeçalhos (`ATH1`).** Com cabeçalhos ligados, cada resposta CAN de 11 bits deve vir como `7E8 06 41 00 9C 3A 80 01` (identificador, byte de comprimento do ISO-TP, dados). Com `ATH0`, só os dados (`41 00 9C 3A 80 01`). Respostas multiquadro com `ATH1`: uma linha por quadro (`7E8 10 14 49 02 01 ...`, `7E8 21 ...`).
2. **`ATDPN`** devolve `A6` (automático, ISO 15765-4 CAN 11/500) após `ATSP0` e `6` após `ATSP6`; **`ATDP`** devolve `AUTO, ISO 15765-4 (CAN 11/500)`.
3. **`ATTP6`, `ATTP0`, `ATSPn`, `ATAT0/1/2`, `ATST hh`, `ATSH`, `ATCAF`, `ATS0/1`, `ATAL`, `ATCRA`** respondem `OK` (aceitos; só `6` e `0` mudam algo). `AT@1` devolve a descrição do dispositivo.
4. **`0900`** devolve a máscara de PIDs suportados do modo 09 (`49 00 40 00 00 00`, só o PID 0x02) e **`0600`** devolve `NO DATA`. Em geral, serviço ou PID sem suporte responde `NO DATA`, não `7F ...`, como o chip real.
5. Manter o que já funciona: eco ligado/desligado, `SEARCHING...` na primeira consulta, prompt `\r\r>`.

## Testes (escrever primeiro)

- Unidade: formatação de cada resposta com `ATH0` e `ATH1`, `ATDPN`/`ATDP` e comandos `AT` aceitos.
- Integração com **cliente real**: `tests/integration/test_elm327_python_obd.py`, marcado `@pytest.mark.realclient`. O teste cria um venv temporário, instala `obd` nele (**nunca no venv do projeto**: o pacote PyPI `obd` tem o mesmo nome do nosso pacote `obd` e o encobre) e roda um script em subprocesso contra o servidor, conferindo:
  - `status()` igual a "Car Connected" e protocolo "ISO 15765-4 (CAN 11/500)";
  - RPM, velocidade, temperatura do líquido, carga, borboleta e combustível iguais ao estado do simulador dentro da resolução;
  - com override de rotação em 3000 no simulador, `RPM` lê 3000;
  - com P0300 injetado, `GET_DTC` devolve P0300; sem falhas, lista vazia.
  O teste é pulado sem rede e fica fora do `make test` padrão (`-m "not broker and not realclient"`).

## Documentação

- `docs/ensaios.md`, seção "Cliente real": resultado do python-OBD (versão, o que leu, o que não leu).
- `README.md`, seção "Conectar um app OBD": IP e porta 35000, como liberar a porta no firewall do Windows, e exemplos de configuração em Car Scanner, Torque e OBD Auto Doctor (adaptador Wi-Fi/TCP, protocolo automático).
- Atualizar `docs/duvidas.md` (tarefa 09): o formato de resposta agora foi validado contra um cliente de terceiros.

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration -m "not broker and not realclient"
pytest -q --tb=short tests/integration -m realclient
make lint
```

## Fora desta tarefa

Adaptadores ELM327 físicos e Bluetooth.

## Prompt de lançamento

```text
Leia apenas tasks/16-elm327-clientes-reais.md e docs/spec/04-protocolo.md. Testes primeiro, depois corrija o servidor, rode os dois comandos de pytest do critério de pronto e mostre só as falhas.
```
