# Manual: montar, gravar, testar e validar o adaptador ESP32

Este manual leva uma pessoa que nunca mexeu com eletrônica do zero até um adaptador OBD-II por Wi-Fi funcionando, com testes em cada etapa. Leia na ordem. **Não pule etapas**: cada fase só vale se a anterior passou.

Se algo não funcionar e vocês quiserem desistir do hardware, o plano B está em [`voltar-ao-simulador.md`](voltar-ao-simulador.md). Desistir do hardware não perde nada do que já foi feito.

## 0. Leia antes de começar

### O que isto é (em uma frase)

Uma plaquinha (ESP32) que se liga na porta OBD-II do carro, conversa com o carro por CAN e conversa com o computador por Wi-Fi, fingindo ser um adaptador ELM327. O computador usa **o mesmo coletor do simulador**, só que apontando para a plaquinha em vez do simulador.

```
Carro (CAN)  <-->  transceptor SN65HVD230  <-->  ESP32  <-- Wi-Fi -->  computador (coletor)
```

### O que NÃO foi testado (honestidade)

O firmware foi escrito e testado **só no PC**. Nunca foi gravado numa placa. Por isso:

- pode haver erro de compilação na primeira gravação (veja a seção 9);
- os pinos padrão (GPIO 5 e GPIO 4) são uma escolha, não foram conferidos na placa de vocês;
- o comportamento com um carro real é desconhecido.

Nada neste projeto afirma algo sobre veículo real até que a fase 4 seja feita e registrada.

### Regras de ouro de segurança

1. **Fases 1 a 3 são sem carro.** Só vá ao carro na fase 4, com tudo já aprovado.
2. **Nunca ligue o 12 V sem o fusível e o diodo.** O fusível protege a fiação; o diodo protege se vocês inverterem os fios.
3. **Nunca ligue USB e buck ao mesmo tempo no ESP32.** Use uma fonte por vez: ou o cabo USB (bancada) ou o 5 V do buck (carro).
4. **Só leitura.** O firmware já vem com o modo 04 (apagar falhas) desligado (`ALLOW_CLEAR_DTC 0`). Não mude isso.
5. **O carro fica parado, em local aberto, freio de mão puxado, câmbio em neutro ou P.** Uma pessoa mexe no computador, outra fica atenta ao carro.
6. **Algo esquentou, cheirou a queimado ou fez faísca?** Desconecte da porta OBD-II imediatamente e pare.
7. **Não faça nada no painel do carro** (não dirija olhando o computador). Nada de coletar enquanto se dirige, a não ser que outra pessoa dirija.

## 1. Lista de compras

| # | Peça | Para que serve | Cuidado ao comprar |
| --- | --- | --- | --- |
| 1 | ESP32 DevKit (ESP32-WROOM-32) | É o "cérebro". Já tem Wi-Fi e o controlador CAN (TWAI) dentro | Precisa ser o **ESP32 comum** (WROOM-32). O firmware e a configuração (`esp32dev`) foram escritos para ele; S2, S3 e C3 não foram considerados |
| 2 | Módulo transceptor CAN SN65HVD230 | Traduz os sinais do ESP32 (3,3 V) para o barramento CAN do carro | Precisa ser o **3,3 V** (SN65HVD230). **Não use o TJA1050 nem o MCP2551**: são de 5 V e podem queimar o ESP32 |
| 3 | Conector OBD-II macho (J1962), de preferência com fios soltos | Encaixa na porta do carro | Confirme que os pinos 4, 5, 6, 14 e 16 têm fio |
| 4 | Conversor buck 12 V para 5 V (ex.: tipo LM2596 ou mini-buck) | Baixa os 12 V do carro para 5 V que o ESP32 aguenta | Regule **antes** de ligar no ESP32 (seção 5) |
| 5 | Fusível de 1 A com porta-fusível | Protege a fiação | 1 A, não maior |
| 6 | Diodo 1N5819 | Bloqueia corrente se a polaridade for invertida | Ele tem uma faixa de um lado (o lado do cátodo) |
| 7 | Cabo USB de **dados** (micro-USB ou USB-C, conforme a placa) | Gravar o firmware | Cabo só de carga não funciona. Se o computador não "vê" a placa, troque o cabo primeiro |
| 8 | Protoboard e fios jumper macho-macho e macho-fêmea | Montar na bancada sem solda | |
| 9 | Multímetro | Medir tensão e resistência | Qualquer um que meça volts e ohms |
| 10 | Fonte 12 V de bancada (ou bateria 12 V pequena) | Simular o carro nas fases 2 e 3 | Opcional, mas muito recomendado |

## 2. Fase 0: preparar o computador

Faça isto uma vez. Tudo fica dentro da pasta do projeto, nada é instalado no sistema.

```bash
git clone https://github.com/021Antonio/plataforma-de-telemetria-obd-ii-simulada
cd plataforma-de-telemetria-obd-ii-simulada
git checkout main && git pull
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install platformio
```

**Teste 0 (deve passar antes de qualquer coisa):**

```bash
make -C firmware test
```

Resultado esperado, a última linha: `28 teste(s), 0 falha(s)`.

```bash
make -C firmware host_server
firmware/build/host_server 35100 &
python -m tests.conformance --host 127.0.0.1 --port 35100
```

Resultado esperado, a última linha: `41/41 OK, 0 divergência(s)`. Depois encerre o servidor de teste (`kill %1`).

Se o Teste 0 falhou, **pare**: o problema é do software, não do hardware. Anote a mensagem e peça ajuda.

> No Windows, o `make` e o `g++` precisam estar instalados. Se não estiverem, rode o Teste 0 no WSL ou no Docker. Essa parte não depende da placa.

## 3. Fase 1: ESP32 sozinho em modo bancada (sem transceptor, sem carro)

Objetivo: provar que o Wi-Fi, o servidor TCP e o dialeto ELM327 funcionam. O ESP32 usa uma ECU **falsa** com valores fixos.

### 3.1 Conferir a configuração

Abra `firmware/include/config.h` e confira. Para esta fase, tem que estar assim (é o padrão):

```c
#define BENCH_MODE 1       // ECU falsa, sem CAN
#define WIFI_AP_MODE 1     // o ESP32 cria o próprio Wi-Fi
#define ALLOW_CLEAR_DTC 0  // nunca mude para 1
```

O Wi-Fi criado se chama `OBD-ESP32`, senha `obd12345`, e o endereço da placa é `192.168.0.10`. Se quiserem outra senha, troque `WIFI_AP_PASSWORD` (mínimo 8 caracteres).

### 3.2 Gravar

1. Ligue o ESP32 no computador pelo cabo USB de dados.
2. Rode:

```bash
cd firmware
pio run -e esp32dev -t upload
```

A primeira vez baixa a plataforma e demora alguns minutos. Se pedir, segure o botão **BOOT** da placa enquanto aparece `Connecting...` e solte quando começar a gravar.

3. Abra o monitor serial:

```bash
pio device monitor
```

**Resultado esperado:** uma linha como `AP OBD-ESP32 em 192.168.0.10`. Se aparecer `TWAI: falha ao iniciar`, em modo bancada isso não impede o teste (o CAN nem é usado), mas anote.

### 3.3 Conectar o computador ao Wi-Fi da placa

1. Nas redes Wi-Fi do computador, escolha `OBD-ESP32` e use a senha.
2. O computador fica **sem internet** enquanto estiver nessa rede. Isso é normal.
3. Teste se enxerga a placa:

```bash
ping 192.168.0.10
```

### 3.4 Teste 1A: suíte de conformidade

```bash
cd ..    # volta para a raiz do projeto
python -m tests.conformance --host 192.168.0.10 --port 35000
```

**Aprovado:** última linha `41/41 OK, 0 divergência(s)`.

Se alguma linha mostrar `DIFERENÇA`, copie a linha inteira. Divergência em `ATRV` (tensão da bateria) pode acontecer legitimamente; qualquer outra deve ser registrada e investigada.

Se der `ERRO de conexão ou tempo esgotado`, vá para a seção 9.

### 3.5 Teste 1B: o coletor real lendo a placa

```bash
python scripts/coletar_adaptador.py --host 192.168.0.10 --port 35000 --ciclos 20 | tee docs/ensaios/hw_bancada.txt
```

**Resultado esperado (na bancada):**

- primeira linha: `PIDs suportados: [...]` com `0x0C`, `0x0D`, etc.;
- 20 linhas `seq=0 ...` até `seq=19 ...`, sem pular número;
- valores fixos, por exemplo `0x0C=3127.5rpm`, `0x0D=77km/h`, `0x42=14V`;
- no final, pode aparecer `evento adapter_error: 012f: NO DATA`. Na ECU falsa o PID `0x2F` (nível de combustível) é anunciado mas não tem dado. **Isso é conhecido e não é defeito da placa.**
- `erros(timeout=0,...)`: timeout diferente de zero repetidamente indica Wi-Fi ruim; aproxime a placa.

O arquivo `docs/ensaios/hw_bancada.txt` é a sua **evidência**. Guarde.

### 3.6 Teste 1C: queda de Wi-Fi

Com o script rodando (use `--ciclos 200`), desligue e ligue o ESP32 (tire o USB e coloque). **Esperado:** o script mostra falhas por alguns segundos e volta a ler sozinho, com `seq` continuando sem pular. Se o script morrer, anote o erro.

**Fase 1 aprovada quando:** Teste 0, 1A (41/41), 1B e 1C passaram. Só então vá adiante.

## 4. Fase 2: ligar o transceptor CAN (ainda sem carro)

Objetivo: ligar o SN65HVD230 ao ESP32 e provar que o ESP32 sobe sem erro de CAN.

### 4.1 Desligue tudo

Tire o USB do ESP32 antes de mexer em fios. **Sempre** mexa em fios com tudo desligado.

### 4.2 Remover a terminação de 120 Ω do módulo

O barramento CAN do carro já tem os resistores de terminação. O módulo costuma ter mais um de 120 Ω, e **um a mais derruba a comunicação**.

1. Olhe o módulo: procure um resistor pequeno marcado `121` ou `120`, ou um jumper/solda marcado `TERM` ou `120R`.
2. Remova o resistor ou abra o jumper.
3. **Confirme com o multímetro** (módulo desligado): em ohms, meça entre os terminais `CANH` e `CANL`. Tem que dar **circuito aberto** (infinito ou "OL"). Se der perto de 120 Ω, a terminação ainda está lá.

### 4.3 Ligações na protoboard

Use a tabela do projeto (`docs/hardware/esp32.md`). Passe cada linha e marque:

| Marque | De | Para |
| --- | --- | --- |
| [ ] | 3V3 do ESP32 | VCC do módulo |
| [ ] | GND do ESP32 | GND do módulo |
| [ ] | GPIO 5 do ESP32 | pino **D** (ou TXD) do módulo |
| [ ] | GPIO 4 do ESP32 | pino **R** (ou RXD) do módulo |
| [ ] | pino **Rs** do módulo | GND (modo rápido) |

Lembrete que confunde todo mundo: o TX do ESP32 vai no **D/TXD** do módulo, e o RX do ESP32 vai no **R/RXD**. Não é cruzado como em comunicação serial comum, porque os nomes do módulo são do ponto de vista do chip dele. Se na sua placa estiver diferente, vale o que está escrito no módulo e no datasheet dele.

Os pinos CANH e CANL do módulo ficam **soltos** nesta fase.

### 4.4 Trocar para modo carro e regravar

Em `firmware/include/config.h`:

```c
#define BENCH_MODE 0
```

Regrave (`pio run -e esp32dev -t upload` dentro de `firmware/`) e abra o monitor.

**Aprovado:** o monitor mostra `AP OBD-ESP32 em 192.168.0.10` e **não** mostra `TWAI: falha ao iniciar`.

Reconecte o computador ao Wi-Fi `OBD-ESP32` e rode a suíte de conformidade de novo. Sem carro, as respostas de dados virão como `NO DATA` ou `CAN ERROR`, porque não há ninguém no barramento para responder. **Isso é o esperado**; o que se verifica aqui é que a placa não trava e continua respondendo aos comandos `AT`.

**Fase 2 aprovada quando:** a placa sobe sem erro de TWAI e responde aos comandos `AT` em modo carro.

## 5. Fase 3: alimentação por 12 V (ainda sem carro)

Objetivo: provar que a alimentação aguenta e protege.

### 5.1 Regular o buck ANTES de ligar no ESP32

1. Ligue só o buck: 12 V da fonte de bancada na entrada (passando por **fusível e diodo**, nessa ordem, no fio positivo).
2. Com o multímetro na saída do buck, gire o parafuso do trimpot até ler **5,0 V**.
3. Só então ligue a saída 5 V no pino **VIN (5V)** do ESP32 e o GND no GND. **Com o USB desconectado.**

Montagem do positivo: `12 V da fonte → fusível 1 A → diodo (faixa para o lado do buck) → entrada + do buck`. O negativo vai direto ao GND comum.

### 5.2 Testes

- O ESP32 liga só com o 12 V (o LED da placa acende).
- O Wi-Fi `OBD-ESP32` aparece.
- A suíte de conformidade roda como na fase 2.
- **Teste do diodo (opcional, com cuidado):** inverta os fios da fonte por um instante. Nada pode esquentar e o ESP32 não pode ligar. Se esquentar, tire imediatamente.

**Fase 3 aprovada quando:** o conjunto liga sozinho por 12 V e passa a conformidade em modo AT.

## 6. Fase 4: no carro

Só faça esta fase com as fases 1 a 3 aprovadas e registradas.

### 6.1 O carro serve?

A plataforma só entende **CAN de 11 bits a 500 kbit/s** (ISO 15765-4). Carros mais antigos podem usar outro protocolo, e aí a placa não vai funcionar (nem machuca nada, só não lê).

Confira no manual do carro ou com um adaptador ELM327 comum e um aplicativo (o protocolo aparece como "ISO 15765-4 CAN 11/500"). Carros mais novos costumam usar CAN, mas isso varia por fabricante e ano, então **confirme no seu**. Se o carro não for compatível, encerre aqui e vá para `voltar-ao-simulador.md`.

### 6.2 Ligação ao conector

Use a tabela do projeto:

| Pino do conector OBD-II | Vai para |
| --- | --- |
| 6 (CAN-H) | CANH do módulo |
| 14 (CAN-L) | CANL do módulo |
| 4 e 5 (terra) | GND comum |
| 16 (12 V permanente) | fusível, diodo, entrada do buck |

Conferência com multímetro, **antes de plugar no carro**: nada de curto entre 16 e GND (medir resistência entre eles, deve ser alta).

### 6.3 Primeira leitura

1. Carro parado, **desligado**, chave fora.
2. Conecte o conjunto na porta OBD-II (geralmente embaixo do painel, lado do motorista).
3. Ligue a ignição (posição "ligado", motor ainda desligado).
4. Espere uns 10 segundos e veja se o Wi-Fi `OBD-ESP32` aparece.
5. Conecte o computador ao Wi-Fi `OBD-ESP32` e rode:

```bash
python scripts/coletar_adaptador.py --host 192.168.0.10 --port 35000 --ciclos 30 | tee docs/ensaios/hw_carro_ignicao.txt
```

6. Depois, com o motor em marcha lenta (carro parado, em local aberto), rode de novo e salve em `docs/ensaios/hw_carro_motor.txt`.

### 6.4 O que é "valor razoável"

Compare com o painel do carro e com o bom senso:

| Grandeza | Motor desligado, ignição ligada | Marcha lenta |
| --- | --- | --- |
| Rotação (`0x0C`) | 0 rpm | cerca de 700 a 1000 rpm |
| Velocidade (`0x0D`) | 0 km/h | 0 km/h |
| Temperatura do líquido (`0x05`) | próxima da do ambiente, se o motor estiver frio | sobe com o tempo, até cerca de 90 °C |
| Tensão (`0x42`) | cerca de 12 V | cerca de 13,5 a 14,5 V |

Valores muito diferentes disso, ou números absurdos (rotação de 20000), indicam erro de leitura. Anote.

### 6.5 Sobre a suíte de conformidade no carro

Não rode a suíte de 41 testes esperando `41/41` no carro: os valores reais do carro são diferentes dos valores fixos do arquivo dourado, então vão aparecer divergências **de valor**, que não são defeito. No carro, use o `coletar_adaptador.py` e a tabela acima. Se quiserem rodar a suíte mesmo assim, o perfil `--config` aceita uma lista `ignorar` de comandos cujo valor muda (veja `docs/spec/09-elm327-dialeto.md`).

### 6.6 Quando parar

Pare imediatamente e desconecte se:

- aparecer luz nova no painel do carro que não existia antes;
- o carro apresentar comportamento estranho (falha de rádio, vidros, etc.);
- qualquer peça esquentar demais;
- o script mostrar `CAN ERROR` em quase todo ciclo (algo errado no barramento: terminação, fiação, protocolo).

O firmware só lê, mas um fio mal ligado pode atrapalhar o barramento. Por isso a conferência de terminação e a parada rápida.

**Fase 4 aprovada quando:** o script lê por 30 ciclos seguidos com valores razoáveis, sem luz nova no painel, e as evidências foram salvas.

## 7. Tabela de decisão: aprovado ou não

| Fase | Aprovado quando | Evidência para guardar |
| --- | --- | --- |
| 0 | `28 teste(s), 0 falha(s)` e `41/41 OK` no PC | print do terminal |
| 1 | `41/41 OK` na placa em bancada, coleta de 20 ciclos sem pular `seq`, recuperação de queda | `hw_bancada.txt` |
| 2 | placa sobe sem erro de TWAI, responde `AT` em modo carro | print do monitor serial |
| 3 | liga só por 12 V, passa em modo AT, diodo protege | foto da montagem e print |
| 4 | 30 ciclos no carro com valores razoáveis | `hw_carro_ignicao.txt`, `hw_carro_motor.txt` |

## 8. Como contar isso no TCC (sem exagerar)

Escreva exatamente o que foi feito, nada além:

- Se só a fase 1 foi feita: "o firmware foi validado em bancada, com ECU simulada no próprio chip; não houve ligação a veículo".
- Se a fase 4 foi feita: "foi feito um ensaio em um único veículo (marca, modelo, ano), com o carro parado, durante N ciclos; os resultados não permitem generalizar".
- Nunca escreva "hardware-in-the-loop". O termo do trabalho continua sendo *software-in-the-loop*, e qualquer ensaio com o carro é tratado como trabalho distinto, com limitações próprias (como já está no Capítulo 6).
- Se a placa não funcionou, escreva isso: um resultado negativo honesto vale mais que um positivo inventado. Veja `voltar-ao-simulador.md`.

## 9. Problemas comuns

| Sintoma | Provável causa | O que fazer |
| --- | --- | --- |
| O computador não "vê" a placa na gravação | Cabo USB só de carga, ou falta driver | Troque o cabo. Em alguns ESP32 é preciso o driver CP210x ou CH340 |
| `Connecting........____` e falha ao gravar | A placa não entrou em modo de gravação | Segure **BOOT** durante o `Connecting...`; solte quando começar |
| Erro de compilação no `pio run` | O código de `firmware/src/` nunca foi compilado antes | Copie o erro inteiro; provavelmente é um ajuste pequeno de API do Arduino/TWAI |
| Não aparece o Wi-Fi `OBD-ESP32` | Placa não gravada ou sem energia | Veja o monitor serial; confira o USB |
| `ping 192.168.0.10` não responde | O computador não está na rede `OBD-ESP32` | Reconecte; desligue VPN |
| Suíte dá `ERRO de conexão` | Mesmo que acima, ou porta errada | Confira host `192.168.0.10`, porta `35000` |
| `TWAI: falha ao iniciar` | Pinos de CAN errados no `config.h` ou módulo mal ligado | Confira os pinos GPIO 5 e 4 contra o seu DevKit; refaça a tabela da fase 2 |
| No carro, tudo `CAN ERROR` / `NO DATA` | Terminação não removida, CANH/CANL trocados, protocolo do carro diferente, ignição desligada | Meça os 120 Ω (deve estar aberto), troque CANH e CANL, confirme CAN 11/500 |
| `timeout` frequente no script | Wi-Fi fraco | Aproxime o computador; teste com `--timeout-ms 1000` |
| O ESP32 reinicia sozinho | Alimentação fraca (buck mal regulado ou fio fino) | Meça 5,0 V no VIN com carga |

Se nada resolver: anote o sintoma, a fase e o que já foi tentado, e use `voltar-ao-simulador.md`.
