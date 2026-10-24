# REVISÃO BIBLIOGRÁFICA

Este capítulo situa o trabalho na literatura. Ele percorre a evolução do diagnóstico veicular, as redes intraveiculares, a telemetria e a Internet das Coisas, os protocolos de mensageria, a segurança de sistemas automotivos e o papel da simulação no desenvolvimento, e termina com os trabalhos relacionados e a lacuna que esta plataforma pretende preencher.

## DA MANUTENÇÃO MECÂNICA AO DIAGNÓSTICO ELETRÔNICO

Durante décadas, o diagnóstico de um motor dependeu da experiência do mecânico e de instrumentos simples: o som do motor, a cor da fumaça, a leitura de um manômetro. A introdução da injeção eletrônica de combustível e do controle eletrônico de ignição mudou esse quadro, porque o funcionamento do motor passou a ser decidido por programas que leem sensores e comandam atuadores (DENTON, 2017; GUIMARÃES, 2007). Esses programas conhecem, a cada instante, o estado do motor com uma precisão que nenhuma inspeção externa alcança.

A pressão regulatória sobre emissões acelerou a padronização. Para verificar que os sistemas de controle de emissões continuam funcionando durante toda a vida do veículo, as autoridades passaram a exigir que o próprio veículo se autodiagnostique e sinalize falhas ao condutor, por meio da lâmpada indicadora de mau funcionamento (MIL, do inglês *Malfunction Indicator Lamp*). O OBD-II é a segunda geração desse requisito, com conector, modos de serviço e códigos de falha padronizados (SAE INTERNATIONAL, 2016a; 2016b; 2017). No Brasil, a Resolução CONAMA nº 354/2004 estabelece os requisitos para a adoção desses sistemas nos veículos automotores leves (BRASIL, 2004), e na União Europeia a homologação de veículos também prevê o acesso a informações de diagnóstico e reparo (UNIÃO EUROPEIA, 2018).

O resultado é um ecossistema de ferramentas. Há *scanners* profissionais, de custo elevado e software proprietário, e há adaptadores de baixo custo, em geral baseados no chip ELM327, que se conectam por Bluetooth ou Wi-Fi a aplicativos de celular. A discussão sobre o direito de reparar mostra que o acesso a esses dados tem peso econômico: restrições de acesso e de informação técnica podem limitar o reparo independente (FEDERAL TRADE COMMISSION, 2021). Para um projeto acadêmico, essa realidade se traduz em uma oportunidade: o padrão é aberto o bastante para que uma implementação independente seja possível, e é por isso que este trabalho a constrói.

## REDES INTRAVEICULARES E O PROTOCOLO CAN

O número de ECUs por veículo cresceu de forma tão acentuada que ligar cada sensor a cada controlador por um fio dedicado tornou-se inviável. A solução foi usar barramentos digitais compartilhados. Navet et al. (2005) e Zeng, Khalid e Chowdhury (2016) descrevem esse panorama, em que coexistem várias tecnologias, cada uma com seu custo e sua finalidade (LIN para funções simples, CAN para controle, FlexRay para aplicações críticas).

O CAN (*Controller Area Network*) foi proposto pela Bosch e especificado na versão 2.0 em 1991 (BOSCH, 1991), e posteriormente padronizado pela ISO 11898 (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2015; 2016a). Suas características mais relevantes para este trabalho são: comunicação por difusão, em que toda mensagem chega a todos os nós; arbitragem não destrutiva por identificador, em que o identificador de menor valor vence a disputa pelo barramento; quadros curtos, com até 8 bytes de dados no CAN clássico; e detecção de erros por CRC e outros mecanismos. Johansson, Törngren e Nielsen (2005) discutem o uso do CAN em aplicações veiculares, e Davis et al. (2007) tratam da análise de escalonabilidade de mensagens CAN, ou seja, de como garantir que mensagens cumpram seus prazos em um barramento compartilhado.

Um ponto importante para a comparação com este trabalho é que o OBD-II usa o CAN como meio, mas não é o CAN. O OBD-II define o que se pergunta (modos e PIDs) e como se responde (formatos de mensagem), enquanto o CAN define como os bytes viajam. Entre os dois fica a camada de transporte ISO-TP, que permite enviar mensagens maiores que 8 bytes sobre quadros de 8 bytes. Esse conjunto é o que a ISO 15765-4 especifica para sistemas relacionados a emissões (INTERNATIONAL ORGANIZATION FOR STANDARDIZATION, 2021).

## TELEMETRIA VEICULAR E INTERNET DAS COISAS

A Internet das Coisas descreve um cenário em que objetos com sensores e capacidade de comunicação publicam dados por redes IP. Atzori, Iera e Morabito (2010) organizam a área em torno de três visões (orientada a "coisas", a internet e a semântica), Gubbi et al. (2013) propõem uma arquitetura de referência centrada em nuvem e Al-Fuqaha et al. (2015) levantam tecnologias habilitadoras e protocolos, incluindo os de camada de aplicação.

No setor automotivo, o termo "carro conectado" abrange serviços que vão do infoentretenimento à gestão de frotas e ao diagnóstico remoto (COPPOLA; MORISIO, 2016). Uma arquitetura típica de telemetria tem quatro estágios: aquisição (leitura dos dados na rede interna do veículo), transmissão (envio por rede sem fio ou celular), armazenamento (banco local ou em nuvem) e visualização ou análise (painéis, alertas, aprendizado de máquina). A plataforma deste trabalho implementa os quatro estágios, com a aquisição sobre uma ECU simulada.

## PROTOCOLOS DE MENSAGERIA

A escolha do protocolo que leva a amostra do coletor ao servidor é um problema clássico de IoT. O HTTP é universal e simples de depurar, mas é orientado a requisição e resposta e acrescenta cabeçalhos a cada envio. O MQTT (*Message Queuing Telemetry Transport*) adota o modelo de publicação e assinatura com um intermediário (*broker*), tem cabeçalhos mínimos e define três níveis de qualidade de serviço (QoS 0, 1 e 2) para escolher entre custo e garantia de entrega (OASIS, 2014). Hunkeler, Truong e Stanford-Clark (2008) apresentam a variante MQTT-S para redes de sensores sem fio, e Naik (2017) compara MQTT, CoAP, AMQP e HTTP em sistemas IoT, destacando que a escolha depende de requisitos de latência, consumo e confiabilidade. O Mosquitto, usado neste trabalho como *broker*, é uma implementação de código aberto do MQTT (LIGHT, 2017).

A plataforma deste trabalho suporta os dois canais, HTTP e MQTT, justamente para poder compará-los com as mesmas condições de coleta (ensaio E7). O WebSocket, padronizado pela RFC 6455 (FETTE; MELNIKOV, 2011), é usado em outro trecho: do servidor ao navegador, para o dashboard receber dados sem consultar repetidamente.

## SEGURANÇA DE SISTEMAS AUTOMOTIVOS

A abertura das redes veiculares tem um lado de risco. Koscher et al. (2010) e Checkoway et al. (2011) mostraram, em análises experimentais, que interfaces externas (inclusive a de diagnóstico) podem ser vetores de ataque a funções do veículo, e Smith (2016) sistematiza técnicas de análise de segurança automotiva. Dessa literatura decorre uma decisão de projeto assumida neste trabalho: a plataforma é **somente de leitura**. O modo 04 (limpeza de códigos de falha) existe apenas no simulador, para exercitar o protocolo, e a API de controle do simulador escuta, por padrão, apenas em `127.0.0.1`. Segurança de transporte (TLS) e autenticação ficam como trabalho futuro.

## SIMULAÇÃO NO DESENVOLVIMENTO AUTOMOTIVO

A simulação é prática consolidada no desenvolvimento automotivo. Fathy et al. (2006) revisam a simulação com hardware no laço (HIL, do inglês *hardware-in-the-loop*), em que um controlador físico real é ligado a um modelo simulado da planta. Em contraste, no *software-in-the-loop* (SIL), tanto o software sob teste quanto o modelo do restante do sistema rodam em software, o que dispensa qualquer hardware, permite execução mais rápida ou determinística e facilita a automação de testes. Este trabalho se enquadra no segundo caso: o coletor e o servidor são o software sob teste, e a ECU e o veículo são modelos.

O preço do SIL é a distância em relação à realidade. Um modelo simplificado não reproduz toda a complexidade de um veículo, e o barramento virtual não tem a temporização do CAN físico. Por isso este trabalho evita extrapolações: os resultados descrevem a plataforma e o simulador, e não um veículo. A decisão de manter a interface `Transport` estável cumpre o papel inverso, o de deixar pronto o ponto em que o hardware real entrará.

## TRABALHOS RELACIONADOS

Malekian et al. (2017) descrevem um sistema de gestão de frotas com OBD-II sem fio, em que um módulo conectado ao veículo transmite dados a um servidor. Rodríguez Rodríguez, Vento Álvarez e Inouye Rodríguez (2018) implementam uma ferramenta de diagnóstico OBD-II sobre CAN com Arduino, com foco na leitura e interpretação de parâmetros. Silva (2025) desenvolve, em trabalho de conclusão de curso, um sistema embarcado para telemetria veicular. Esses trabalhos concentram o esforço no hardware e na integração com o veículo, e validam o resultado por meio dele.

A contribuição pretendida aqui é complementar. Em vez de construir mais um dispositivo, constrói-se o ambiente em que a cadeia de software pode ser validada antes e independentemente do dispositivo: com referência conhecida, falhas injetáveis, execuções repetíveis e um transporte intercambiável. A Tabela 1 resume a comparação.

::: {custom-style="LegendaTabela"}
Tabela 1: Comparação entre trabalhos centrados em hardware e esta plataforma
:::

| Aspecto | Trabalhos centrados em hardware | Esta plataforma |
| --- | --- | --- |
| Foco | Dispositivo conectado ao veículo | Cadeia de software completa |
| Verdade de referência | Desconhecida em veículo real | Conhecida, gravada com cada leitura |
| Falhas de comunicação | Difíceis de provocar | Injetadas por comando, com semente |
| Repetibilidade | Depende do veículo e do momento | Determinística, por sementes |
| Custo para reproduzir | Hardware e veículo | Um computador, com ou sem Docker |
| Ponto de integração com hardware | Já é o produto | Interface `Transport` pronta |

::: {custom-style="Fonte"}
Fonte: elaborada pelos autores.
:::

## SÍNTESE

Os trabalhos revisados mostram que o OBD-II é um padrão estável e aberto, que o CAN é a base de transporte dominante, que a telemetria e a IoT oferecem modelos arquiteturais e protocolos de mensageria maduros, que a segurança exige cautela no acesso a interfaces de diagnóstico e que a simulação é prática estabelecida. A lacuna que sobra é um ambiente aberto, pequeno e repetível para validar a cadeia de software da telemetria OBD-II antes de ligá-la a um veículo. É essa lacuna que o restante do texto procura preencher.
