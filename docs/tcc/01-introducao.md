# INTRODUÇÃO

Um automóvel moderno é, em boa medida, uma rede de computadores sobre rodas. Dezenas de unidades eletrônicas de controle (ECU, do inglês *Electronic Control Unit*) medem, calculam e decidem a todo instante: quanto combustível injetar, quando gerar a centelha, se a mistura está rica ou pobre, se a temperatura do motor está dentro da faixa esperada (DENTON, 2017; GUIMARÃES, 2007). Todas essas grandezas existem, em formato digital, dentro do veículo. O que varia é o quanto o proprietário, o mecânico independente, o estudante ou o pesquisador conseguem enxergar delas.

A porta de entrada padronizada para essas informações é o diagnóstico de bordo de segunda geração, o OBD-II (*On-Board Diagnostics*). Ele define um conector, um conjunto de serviços e uma lista de parâmetros que qualquer ferramenta compatível pode requisitar à ECU do motor (SAE INTERNATIONAL, 2016a; 2017). No Brasil, a Resolução CONAMA nº 354/2004 trata dos requisitos para a adoção de sistemas OBD nos veículos leves, com o objetivo de preservar a funcionalidade dos sistemas de controle de emissões (BRASIL, 2004). Na prática, isso significa que existe uma interface comum, mas o que se constrói em cima dela (leitura, armazenamento, visualização, análise) fica por conta de quem a usa.

Este trabalho trata dessa camada superior. Ele apresenta uma plataforma de telemetria OBD-II construída inteiramente em software: um veículo simulado, uma ECU virtual que responde conforme a norma, um coletor que requisita e decodifica os parâmetros, um servidor que armazena e distribui os dados, e um painel web que os exibe em tempo real. Nenhum componente físico é necessário para executá-la, e todos os resultados reportados foram obtidos por esse caminho.

## CONTEXTO

A telemetria veicular reúne a coleta, a transmissão e a análise remota de dados de um veículo em operação. Ela sustenta aplicações como gestão de frotas, manutenção preditiva, seguros baseados em uso e diagnóstico remoto (COPPOLA; MORISIO, 2016; MALEKIAN et al., 2017). Em paralelo, a Internet das Coisas (IoT, do inglês *Internet of Things*) tornou comum a ideia de que objetos físicos publicam medições por uma rede, e que serviços em nuvem ou locais as consomem (ATZORI; IERA; MORABITO, 2010; GUBBI et al., 2013; AL-FUQAHA et al., 2015). O veículo é um caso particularmente rico dessa ideia, porque já traz sensores, redes internas e uma interface de diagnóstico normatizada.

Por outro lado, o acesso aos dados veiculares é historicamente concentrado. Ferramentas de diagnóstico profissionais têm custo elevado e arquitetura fechada, e debates regulatórios sobre o chamado "direito de reparar" mostram que a disponibilidade de informação técnica é uma questão econômica e política, além de técnica (FEDERAL TRADE COMMISSION, 2021; UNIÃO EUROPEIA, 2018). Adaptadores baratos baseados no chip ELM327 popularizaram a leitura de dados por aplicativos de celular, mas o que se faz com os dados depois da leitura continua sendo, quase sempre, um problema de cada projeto.

Há ainda um aspecto de método. Quem desenvolve software de telemetria precisa testá-lo. Testar contra um veículo real traz limitações práticas: nem todo estudante tem acesso a um veículo com a interface adequada, o ensaio depende das condições do momento (temperatura, estado do motor, carga elétrica), e provocar uma falha de propósito para verificar se o sistema a detecta é, no mínimo, imprudente. Além disso, mesmo quando a leitura funciona, falta uma referência: o software informa que a rotação é 2000 rpm, mas qual era a rotação verdadeira? Sem essa resposta, não há como medir o erro do próprio sistema.

## PROBLEMA E MOTIVAÇÃO

A dor que motiva este trabalho pode ser resumida em quatro pontos.

1. **Dependência de hardware para desenvolver e testar.** O ciclo "alterar o código, ligar o adaptador, conectar ao veículo, observar" é lento, caro e nem sempre possível. Isso afasta estudantes e pequenos laboratórios do tema.
2. **Ausência de verdade de referência.** Em um veículo real, o valor físico exato de cada grandeza em cada instante é desconhecido para quem mede. Sem ele, a exatidão da decodificação só pode ser afirmada, não medida.
3. **Falhas difíceis de reproduzir.** Códigos de falha, perda de mensagens, respostas atrasadas e quadros corrompidos são exatamente as situações que um sistema de telemetria precisa tratar bem, e são as mais difíceis de provocar de forma controlada e repetível em um carro.
4. **Resultados não repetíveis.** Ensaios com hardware e veículo reais dificilmente podem ser repetidos por outra pessoa nas mesmas condições, o que enfraquece a verificação independente dos resultados.

A motivação, portanto, é construir um ambiente em que o protocolo OBD-II, a camada de transporte, o coletor, o servidor e a interface possam ser desenvolvidos e medidos sem hardware, com valores de referência conhecidos, falhas injetáveis por comando e execuções repetíveis a partir de sementes numéricas fixas.

## SOLUÇÃO PROPOSTA

A solução é uma plataforma de telemetria OBD-II simulada, aberta e executável com um comando (`make run` ou `docker compose up`). Ela reproduz a cadeia completa em cinco blocos:

- **Simulador.** Um modelo de veículo em passos de 10 ms gera velocidade, marcha, rotação, borboleta, carga, pressão do coletor, temperaturas, nível de combustível e tensão, seguindo perfis de condução. Sobre ele, uma ECU virtual responde às requisições conforme a ISO 15765-4, com ISO-TP completo e os modos 01, 02, 03, 04, 07 e 09.
- **Transporte plugável.** O coletor conhece apenas a interface `Transport`. Há implementações para laço local (*loopback*), barramento CAN virtual (`python-can`) e adaptador ELM327 por TCP.
- **Coletor.** Descobre os PIDs suportados, monta um plano de leitura com PIDs rápidos e lentos, valida cada resposta, decodifica pelas fórmulas da SAE J1979, mede o tempo de ida e volta e publica amostras numeradas.
- **Servidor.** Uma aplicação FastAPI recebe as amostras por HTTP ou MQTT, grava em SQLite, detecta perdas e duplicações pelo número de sequência e retransmite por WebSocket.
- **Interfaces.** Um painel web mostra a telemetria em tempo real e um segundo painel controla o simulador (valores, perfis, falhas, atraso e perda de quadros), com um monitor de quadros em hexadecimal.

Como o simulador conhece o valor físico verdadeiro de cada grandeza, o banco de dados guarda, ao lado de cada leitura decodificada, o valor real (`true_value`). Isso permite calcular o erro de decodificação por uma simples consulta SQL. Como toda a aleatoriedade vem de sementes, qualquer pessoa pode repetir um ensaio e comparar os resultados.

Uma camada de compatibilidade ELM327 por TCP, na porta 35000, faz o simulador se comportar como um adaptador Wi-Fi. Com isso, bibliotecas e aplicativos de terceiros, escritos sem nenhum conhecimento deste projeto, conseguem conectar e ler dados, o que funciona como validação externa do formato das respostas.

## OBJETIVOS

### Objetivo geral

Projetar, implementar e validar, por testes automatizados e ensaios de desempenho, uma plataforma aberta de telemetria OBD-II independente de hardware, em que a cadeia completa de coleta, armazenamento e visualização possa ser desenvolvida, medida e repetida em ambiente de *software-in-the-loop*.

### Objetivos específicos

1. Especificar os requisitos funcionais e não funcionais da plataforma e os critérios de aceitação de cada um.
2. Implementar o protocolo OBD-II sobre CAN (ISO 15765-4) como núcleo puro, sem entrada e saída, com ISO-TP, modos de serviço, PIDs e códigos de falha.
3. Implementar um simulador de veículo e uma ECU virtual determinísticos, com injeção de falhas de aplicação e de comunicação.
4. Implementar o coletor, o servidor, a persistência, o dashboard e o painel de controle do simulador.
5. Disponibilizar o transporte como interface plugável, de modo que um adaptador real possa substituir o simulador sem alterar o coletor.
6. Implementar a camada ELM327 por TCP e validá-la contra clientes de terceiros.
7. Medir exatidão de decodificação, tempo de ciclo, latência, perdas e sensibilidade a atraso, perda de quadros, tamanho do ciclo, espaçamento ISO-TP e canal de publicação (HTTP e MQTT).
8. Documentar as escolhas de tecnologia, as decisões tomadas e as limitações, de forma que o trabalho possa ser continuado em uma segunda etapa com hardware.

## DELIMITAÇÃO DO ESCOPO

Este trabalho corresponde à **primeira etapa** de um projeto maior. A primeira etapa é inteiramente em software. A segunda etapa, fora deste texto, prevê a substituição do simulador por hardware (um microcontrolador emulando um adaptador ELM327 por Wi-Fi, ligado à rede CAN de um veículo) e um ensaio de campo. Ficam, portanto, fora do escopo deste trabalho:

- qualquer construção ou ensaio com hardware embarcado e qualquer medição em veículo real;
- a camada física do CAN (níveis elétricos, terminação, confirmação de recebimento entre nós) e a taxa de 500 kbit/s como grandeza medida;
- os protocolos K-Line, J1850 e CAN de 29 bits;
- comandos que atuem sobre o veículo: a plataforma é somente de leitura;
- Bluetooth, TLS e aplicativo móvel.

Por esse motivo, o trabalho não afirma nada sobre o comportamento de um veículo real. As conclusões valem para o simulador e para a plataforma que o cerca, e o termo adequado para o método é *software-in-the-loop*: o software sob teste (coletor e servidor) interage com um modelo em software do restante do sistema.

## METODOLOGIA

Quanto à natureza, a pesquisa é aplicada, pois busca produzir uma solução para um problema prático. Quanto aos objetivos, é exploratória e descritiva, e quanto aos procedimentos, é um desenvolvimento experimental, com construção de um artefato e medição de seu desempenho em ensaios controlados (GIL, 2017; PRODANOV; FREITAS, 2013).

O desenvolvimento seguiu um fluxo em quatro passos, descritos em detalhe no Capítulo 4:

1. **Especificação.** Os requisitos (RF01 a RF12 e RNF01 a RNF08) e as interfaces entre módulos foram escritos antes do código, em documentos versionados no repositório.
2. **Implementação orientada por testes.** O trabalho foi dividido em tarefas pequenas, cada uma com seus testes escritos primeiro, e integrada por pedido de alteração (*pull request*) em um repositório Git.
3. **Ensaios.** Sete ensaios (E1 a E7) medem exatidão, desempenho e robustez; cada um grava configuração, sementes, máquina e resultados em arquivos CSV e JSON.
4. **Validação externa.** A camada ELM327 foi exercitada por bibliotecas e aplicativos de terceiros (python-OBD e OBD Auto Doctor).

Todas as medições deste texto vêm de um único computador, descrito na Seção 4.10. Não há segunda máquina medida, e o trabalho declara essa limitação em vez de supor reprodutibilidade entre máquinas. A repetição por outra pessoa é possível e está documentada (Apêndice B), mas não foi executada.

## ESTRUTURA DO TRABALHO

O Capítulo 2 revisa a literatura sobre diagnóstico eletrônico, redes intraveiculares, telemetria e IoT, mensageria, segurança e simulação. O Capítulo 3 apresenta a fundamentação técnica: OBD-II, CAN, ISO-TP, ELM327 e as tecnologias de software empregadas. O Capítulo 4 descreve os materiais e métodos: requisitos, arquitetura, cada módulo, as escolhas de tecnologia com suas alternativas, a estratégia de testes e o desenho dos ensaios. O Capítulo 5 apresenta e discute os resultados. O Capítulo 6 reúne as considerações finais, as limitações e os trabalhos futuros, incluindo a segunda etapa com hardware.
