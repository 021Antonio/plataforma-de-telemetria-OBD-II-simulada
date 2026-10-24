# CONSIDERAÇÕES FINAIS

Este trabalho propôs, implementou e validou uma plataforma de telemetria OBD-II inteiramente em software, com o objetivo de oferecer um ambiente em que a cadeia completa de coleta, armazenamento e visualização possa ser desenvolvida, medida e repetida sem hardware. Este capítulo retoma os objetivos, resume as contribuições, declara as limitações e descreve a segunda etapa do projeto.

## CONCLUSÕES

O objetivo geral foi atingido no escopo definido. A plataforma reproduz a cadeia de telemetria OBD-II (veículo simulado, ECU virtual conforme a ISO 15765-4, transporte plugável, coletor, servidor com banco de dados, dashboard e painel de controle) e pode ser executada com um comando. Quanto aos objetivos específicos:

1. **Requisitos.** Doze requisitos funcionais e oito não funcionais foram especificados com critérios de aceitação. Dos oito não funcionais, seis foram atendidos e dois (RNF04 e RNF05) foram atendidos parcialmente, por motivos declarados: a taxa de 500 kbit/s não é medida em um barramento virtual, e a repetição em segunda máquina não foi feita.
2. **Protocolo.** O núcleo de protocolo implementa ISO-TP completo, os modos 01, 02, 03, 04, 07 e 09, dez PIDs, a descoberta de PIDs e a codificação de DTCs, sem entrada e saída, com 97% a 100% de cobertura de testes.
3. **Simulador.** O modelo de veículo e a ECU virtual são determinísticos, e o catálogo de falhas cobre DTCs, atraso, perda, corrupção, ECU muda e atraso de ISO-TP.
4. **Coletor, servidor e interfaces.** Foram implementados e integrados, e funcionam em HTTP e MQTT.
5. **Transporte plugável.** A interface `Transport` tem três implementações, e o coletor não muda entre elas.
6. **ELM327.** A camada de compatibilidade foi validada com a biblioteca python-OBD e com o aplicativo OBD Auto Doctor, depois de correções motivadas pela falha inicial dos dois.
7. **Medições.** Em 19070 leituras do ensaio E1, nenhuma teve erro de decodificação acima de metade da resolução; o ciclo de 10 PIDs teve p95 de 115,6 ms, a latência do coletor ao banco teve p95 de 3,5 ms, e não houve perdas. Os ensaios E2 a E5 mostraram que o ciclo cresce linearmente com o atraso da ECU e com o número de PIDs, que a perda de quadros reduz a vazão sem perda de dados no servidor, e que o tempo de remontagem do VIN é o custo base somado ao STmin. O E7 mostrou, com um *broker* Mosquitto real no mesmo computador, latência média de 0,6 ms no MQTT contra 3,0 ms no HTTP.
8. **Documentação.** As escolhas, as decisões e as limitações estão registradas no repositório, em especial em `docs/spec/` e `docs/duvidas.md`.

## CONTRIBUIÇÕES

A principal contribuição é metodológica: um ambiente em que o valor real de cada grandeza é conhecido e gravado ao lado do valor decodificado, o que permite medir a exatidão do sistema em vez de supô-la. A segunda é a possibilidade de injetar falhas de comunicação e de aplicação de modo repetível, a partir de sementes numéricas. A terceira é a camada de compatibilidade ELM327, que transforma bibliotecas e aplicativos de terceiros em clientes de teste independentes, e cujo desenvolvimento mostrou que testes escritos pelos próprios autores deixaram passar divergências que clientes externos expuseram. A quarta é a interface de transporte, que deixa o ponto de integração com o hardware definido e estável.

Do ponto de vista de engenharia de software, o projeto demonstra um fluxo de trabalho em que a especificação precede o código, os testes precedem a implementação, as decisões não especificadas ficam registradas, e cada alteração entra por pedido de alteração revisado. O fluxo também incorpora um assistente de inteligência artificial como ferramenta, com os autores responsáveis pela definição dos objetivos, pela revisão e pela validação.

## LIMITAÇÕES

As limitações abaixo delimitam o que os resultados permitem afirmar.

- **Nenhum veículo real foi usado.** Todos os resultados valem para o simulador e para a plataforma que o cerca. O trabalho não afirma nada sobre o comportamento de um veículo, de uma ECU real ou de um adaptador físico.
- **Barramento virtual.** Os ensaios usam o laço local, sem camada física CAN. Não há medida de taxa de bits, terminação, arbitragem ou erros de bit.
- **Uma única máquina.** Os tempos vêm de um computador. Os ensaios E1 a E3 foram repetidos uma vez em contêiner isolado, na mesma máquina, com resultados muito próximos, mas essa repetição não é independente e não permite estimar a variação estatística; a variação entre máquinas não foi estimada.
- **ECU e veículo são modelos.** O atraso da ECU é uniforme e o modelo do veículo é ilustrativo e não calibrado. A norma foi interpretada pelos autores e validada contra dois clientes de terceiros, o que reduz, mas não elimina, o risco de divergência em relação a outros clientes e a uma ECU real.
- **Validação de aplicativos de celular.** Car Scanner e Torque não foram testados. O OBD Auto Doctor foi observado manualmente em uma sessão, sem medida estatística.
- **Segurança.** O sistema não usa TLS nem autenticação. A API de controle do simulador deve ser exposta apenas em rede local de confiança.
- **Escopo do protocolo.** Apenas CAN de 11 bits (ISO 15765-4), um conjunto de dez PIDs e seis modos de serviço. K-Line, J1850, CAN de 29 bits, o modo 06 e outros PIDs ficam fora.
- **Explicações não verificadas.** Duas explicações apresentadas no Capítulo 5 (a diferença de ciclos por segundo entre HTTP e MQTT, e o comportamento do ciclo com 10% de perda) são coerentes com o funcionamento do sistema, mas não foram confirmadas por medição específica, e o máximo de latência de 42,2 ms no E1 não foi investigado.

## TRABALHOS FUTUROS

### Segunda etapa: hardware

A segunda etapa do projeto, planejada e ainda não executada, substitui o simulador por hardware. A ideia é usar uma placa de desenvolvimento com o microcontrolador ESP32, com o periférico TWAI (a interface CAN do chip) e um transceptor CAN de 3,3 V como o SN65HVD230, ligado ao conector OBD-II do veículo pelos pinos de sinal CAN (6 e 14), terra (4 e 5) e, se for o caso, alimentação (16) (ESPRESSIF SYSTEMS, [s.d.]a; [s.d.]b; TEXAS INSTRUMENTS, [s.d.]; SAE INTERNATIONAL, 2016a). O firmware faria dois papéis: falar CAN com o veículo, usando a mesma lógica do núcleo de protocolo deste trabalho, e expor ao exterior um servidor TCP no dialeto ELM327, por Wi-Fi. Com isso, o computador que executa a plataforma, ou um aplicativo de celular, conectaria ao dispositivo exatamente como se conecta ao simulador, pela porta 35000.

Algumas decisões já tomadas para a segunda etapa, que dependem de validação em campo:

- o dispositivo seria **somente de leitura**: o modo 04 ficaria desabilitado no firmware, em coerência com o RNF08 e com a literatura de segurança (KOSCHER et al., 2010; CHECKOWAY et al., 2011);
- como a rede CAN do veículo já tem as terminações próprias, a terminação de 120 Ω do módulo transceptor deveria ser removida ou desabilitada;
- o dispositivo teria dois modos de rede: ponto de acesso próprio (endereço fixo, como um adaptador comercial) ou cliente de uma rede existente, com descoberta por nome (mDNS);
- as tarefas 17, 18 e 19 do repositório descrevem, respectivamente, a ampliação da conformidade do servidor ELM327, a adaptação do coletor a um adaptador real e o firmware.

Antes de qualquer ligação ao veículo, o protocolo de diagnóstico suportado por ele precisa ser verificado, porque a plataforma implementa apenas CAN de 11 bits a 500 kbit/s, e veículos mais antigos podem usar outro protocolo. Qualquer resultado da segunda etapa deve ser tratado como um trabalho distinto, com metodologia e limitações próprias, e não como extensão automática das conclusões deste.

### Melhorias da plataforma

- Repetir os ensaios em uma segunda máquina e com várias execuções por ensaio, para estimar a variação entre execuções.
- Requisitar mais de um PID por mensagem, para reduzir o ciclo com ECUs de maior atraso.
- Implementar a leitura dos modos 06 e 07 no coletor e de mais PIDs, incluindo os de consumo de combustível e de sensores de oxigênio.
- Adicionar TLS e autenticação ao canal HTTP e ao MQTT.
- Medir o canal MQTT em rede real entre máquinas, com QoS 1 e perdas de pacotes induzidas.
- Validar Car Scanner e Torque e documentar o resultado, e salvar as capturas de tela do OBD Auto Doctor no repositório.
- Construir um aplicativo móvel e considerar armazenamento especializado em séries temporais para volumes maiores de dados.
- Explorar análise dos dados coletados, como detecção de anomalias e manutenção preditiva.

## CONSIDERAÇÃO FINAL

O trabalho mostra que boa parte da engenharia de um sistema de telemetria veicular pode ser feita, medida e repetida sem tocar em um carro, desde que o ambiente de simulação conheça a verdade que o sistema tenta medir. A distância entre esse ambiente e um veículo real é grande e foi mantida explícita ao longo do texto. A interface de transporte é o lugar onde essa distância será percorrida na segunda etapa.
