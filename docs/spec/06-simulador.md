# 6. Simulador e mocks

## Modelo de veículo (`vehicle_model.py`)

O modelo avança em passos de 10 ms e mantém o estado físico real, que serve de referência para medir o erro de decodificação. Os valores são ilustrativos de um compacto 1.6 aspirado e podem ser trocados em `config/default.yaml`.

| Variável | Como é calculada |
| --- | --- |
| Velocidade | Segue o perfil de condução com aceleração limitada |
| Marcha | Escolhida pela velocidade (trocas em faixas fixas) |
| Rotação | Pela velocidade, marcha, relação final e raio do pneu (fórmula abaixo); marcha lenta em 800 rpm |
| Borboleta | Pela aceleração pedida pelo perfil |
| Carga e MAP | Crescem com a borboleta e a rotação; MAP limitado à pressão atmosférica (101 kPa), pois o motor é aspirado |
| Temp. arrefecimento | Aproximação exponencial de 25 °C até 90 °C (constante de tempo configurável) |
| Temp. ar de admissão | Ambiente mais um acréscimo lento com a temperatura do motor |
| Ajuste de mistura (STFT) | Oscila em torno de 0 % com amplitude de 3 %, simulando a malha fechada |
| Nível de combustível | Decresce proporcionalmente à carga integrada |
| Tensão | 14,1 V com o motor ligado e 12,4 V desligado |
| Ruído | Gaussiano de baixa amplitude, semente fixa |

```latex
n_{rpm} = \frac{v/3{,}6}{r_{pneu}} \cdot i_{marcha} \cdot i_{final} \cdot \frac{60}{2\pi}
```

## Perfis de condução (YAML)

```yaml
name: urbano
loop: true
steps:
  - {t: 0,   speed: 0,  throttle: 0.0}      # marcha lenta
  - {t: 10,  speed: 50, throttle: 0.45}     # aceleração
  - {t: 40,  speed: 50, throttle: 0.20}     # cruzeiro
  - {t: 50,  speed: 0,  throttle: 0.0}      # desaceleração e parada
```

Perfis entregues: `parado`, `urbano`, `rodovia`, `ciclo_120s` (o do TCC: marcha lenta, 0 a 80 km/h, cruzeiro e desaceleração) e `esforco` (rotação alta para testar PIDs rápidos).

## Catálogo de falhas (`faults.py`)

| Falha | Parâmetros | O que testa |
| --- | --- | --- |
| DTC armazenado | código, instante | Modo 03, MIL, freeze frame |
| DTC pendente | código | Modo 07 |
| Atraso de resposta | mínimo e máximo em ms | Sensibilidade (ensaio E2) |
| Perda de quadros | probabilidade | Timeout e recuperação |
| Quadro corrompido | probabilidade | Validação do eco de modo e PID |
| ECU muda | liga e desliga | Recuo progressivo |
| PID não suportado | lista | Descoberta de PIDs (0x00) |
| Resposta negativa | modo e código | Tratamento de `7F` |
| Atraso de ISO-TP | `STmin` e `BS` | Remontagem multiquadro |

## Mocks e dublês de teste

| Dublê | Substitui | Uso |
| --- | --- | --- |
| `LoopbackTransport` | Barramento e ECU | Testes do coletor sem rede nem simulador |
| `ScriptedTransport` | ECU real | Responde a uma lista fixa de requisições, para casos de borda e quadros inválidos |
| `FakeClock` | Relógio do sistema | Tempo determinístico nos testes de latência, timeout e recuo |
| `FakeVehicleModel` | Modelo físico | Valores constantes ou em rampa para verificar a decodificação |
| `InMemoryStorage` | SQLite | Testes do servidor e do publisher |
| `RecordingPublisher` | Servidor | Verifica o que o coletor publica |
| `FakeElm327Client` | App OBD | Sequências de comandos AT contra o servidor ELM327 |

**Determinismo:** o simulador recebe duas sementes (modelo e ECU) e o relógio é injetável. Com as mesmas sementes e o mesmo perfil, a sequência de valores físicos é idêntica entre execuções.
