::: {custom-style="Capa"}
**CENTRO UNIVERSITÁRIO IBMR**
:::

::: {custom-style="Capa"}
**ELIAS BORGES VIANA**
:::

::: {custom-style="Capa"}
**ARTHUR SILVA DE CERQUEIRA**
:::

::: {custom-style="CapaTitulo"}
**PLATAFORMA DE TELEMETRIA OBD-II SIMULADA: PROJETO E VALIDAÇÃO EM SOFTWARE-IN-THE-LOOP**
:::

::: {custom-style="CapaRodape"}
Rio de Janeiro

2026
:::

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="Capa"}
**ELIAS BORGES VIANA**
:::

::: {custom-style="Capa"}
**ARTHUR SILVA DE CERQUEIRA**
:::

::: {custom-style="CapaTitulo"}
**PLATAFORMA DE TELEMETRIA OBD-II SIMULADA: PROJETO E VALIDAÇÃO EM SOFTWARE-IN-THE-LOOP**
:::

::: {custom-style="Natureza"}
Trabalho de Conclusão de Curso apresentado ao curso de Engenharia da Computação do Centro Universitário IBMR como requisito parcial para obtenção do título de Bacharel em Engenharia da Computação.

Orientador: Prof. FRANCISCO JOSÉ RODRIGUES DA SILVA JUNIOR
:::

::: {custom-style="CapaRodape"}
Rio de Janeiro

2026
:::

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="Capa"}
**ELIAS BORGES VIANA**
:::

::: {custom-style="Capa"}
**ARTHUR SILVA DE CERQUEIRA**
:::

::: {custom-style="CapaTitulo"}
**PLATAFORMA DE TELEMETRIA OBD-II SIMULADA: PROJETO E VALIDAÇÃO EM SOFTWARE-IN-THE-LOOP**
:::

::: {custom-style="Natureza"}
Este Trabalho de Conclusão de Curso foi julgado adequado à obtenção do título de Bacharel em Engenharia da Computação e aprovado em sua forma final pelo Curso de Engenharia da Computação do Centro Universitário IBMR.

Rio de Janeiro, ____ de ______________ de 2026.
:::

::: {custom-style="Capa"}
**BANCA EXAMINADORA:**
:::

::: {custom-style="Assinatura"}
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Orientador: Prof. Francisco José Rodrigues da Silva Junior

Centro Universitário IBMR
:::

::: {custom-style="Assinatura"}
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Prof. Nome do Professor, Dr./Ms./Bel./Lic.

Centro Universitário IBMR
:::

::: {custom-style="Assinatura"}
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Prof. Nome do Professor, Dr./Ms./Bel./Lic.

Centro Universitário IBMR
:::

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="Dedicatoria"}
Às nossas famílias, pelo apoio e pela paciência ao longo de toda a graduação.
:::

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**AGRADECIMENTOS**
:::

Agradecemos às nossas famílias, pelo apoio constante durante o curso. Ao professor Francisco José Rodrigues da Silva Junior, pela orientação deste trabalho. Aos professores e colegas do curso de Engenharia da Computação do Centro Universitário IBMR, pelo aprendizado compartilhado ao longo da graduação.

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**DECLARAÇÃO DE USO DE INTELIGÊNCIA ARTIFICIAL**
:::

( ) Não utilizei ferramentas de Inteligência Artificial na elaboração deste trabalho.

(X) Utilizei ferramentas de Inteligência Artificial como apoio nas seguintes etapas:

Finalidade do uso: foi utilizado o assistente Claude (Anthropic) na redação do texto dos capítulos, na organização das referências, no desenvolvimento do código do simulador, do coletor, do servidor, do dashboard e do painel de controle, na elaboração dos scripts de ensaio e dos gráficos e na execução dos testes e dos ensaios em ambiente computacional. Os autores foram responsáveis pela definição do tema, dos objetivos e do escopo, pela execução do ensaio com o *broker* Mosquitto e da validação com aplicativos de terceiros em computador próprio, e pela leitura e revisão do conteúdo final.

Declaro que a análise crítica, reflexiva e a autoria intelectual deste trabalho são de minha responsabilidade.

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**RESUMO**
:::

::: {custom-style="Resumo"}
O acesso aos dados que um veículo produz depende, em grande parte, de ferramentas de diagnóstico de custo elevado e arquitetura fechada, e desenvolver software de telemetria exige um veículo, um adaptador e condições repetíveis que nem sempre existem. Além disso, em um veículo real o valor verdadeiro de cada grandeza é desconhecido, de modo que a exatidão da leitura só pode ser afirmada, não medida. Este trabalho apresenta uma plataforma aberta de telemetria OBD-II construída inteiramente em software, na qual um veículo simulado, uma unidade de controle virtual conforme a ISO 15765-4 (com ISO-TP e os modos 01, 02, 03, 04, 07 e 09), um coletor, um servidor com banco SQLite, um dashboard web e um painel de controle do simulador reproduzem a cadeia completa de coleta, armazenamento e visualização. O coletor depende apenas de uma interface de transporte, o que permite substituir o simulador por hardware sem alterá-lo, e uma camada de compatibilidade ELM327 por TCP permite que bibliotecas e aplicativos de terceiros funcionem como clientes. A pesquisa é aplicada e exploratória, por desenvolvimento experimental, com método de software-in-the-loop e sementes fixas. Foram executados 405 testes automatizados, com cobertura de 89% e de 97% a 100% nos módulos de protocolo, e sete ensaios de desempenho em uma única máquina. Em 19.070 leituras, nenhuma apresentou erro de decodificação acima de metade da resolução; o ciclo de dez parâmetros teve percentil 95 de 115,6 ms, a latência do coletor ao banco teve percentil 95 de 3,5 ms e não houve perdas. Os ensaios mostraram que o ciclo cresce linearmente com o atraso da ECU e com o número de parâmetros e que a perda de quadros reduz a vazão sem perda de dados no servidor; com um intermediário Mosquitto real no mesmo computador, o MQTT teve latência média de 0,6 ms contra 3,0 ms do HTTP. A camada ELM327 foi validada com a biblioteca python-OBD e com o aplicativo OBD Auto Doctor. Os resultados valem para o simulador e não afirmam nada sobre veículos reais; a substituição do simulador por hardware e o ensaio de campo ficam como segunda etapa.
:::

**Palavras-chave:** Telemetria veicular. OBD-II. Simulação. *Software-in-the-loop*. ELM327.

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**ABSTRACT**
:::

::: {custom-style="Resumo"}
Access to the data a vehicle produces still depends largely on expensive, closed diagnostic tools, and developing telemetry software requires a vehicle, an adapter and repeatable conditions that are not always available. Moreover, on a real vehicle the true value of each quantity is unknown, so the accuracy of a reading can only be asserted, not measured. This work presents an open OBD-II telemetry platform built entirely in software, in which a simulated vehicle, a virtual control unit compliant with ISO 15765-4 (with ISO-TP and services 01, 02, 03, 04, 07 and 09), a collector, a server with an SQLite database, a web dashboard and a simulator control panel reproduce the whole chain of acquisition, storage and visualization. The collector depends only on a transport interface, so the simulator can be replaced by hardware without changing it, and an ELM327 compatibility layer over TCP lets third-party libraries and apps work as clients. The research is applied and exploratory, based on experimental development, using a software-in-the-loop method with fixed seeds. A total of 405 automated tests were run, with 89% coverage overall and 97% to 100% in the protocol modules, along with seven performance experiments on a single machine. In 19,070 readings, none showed a decoding error above half of the resolution; the ten-parameter cycle had a 95th percentile of 115.6 ms, the collector-to-database latency had a 95th percentile of 3.5 ms and there were no losses. The experiments showed that the cycle grows linearly with the ECU delay and with the number of parameters, and that frame loss reduces throughput without losing data on the server; with a real Mosquitto broker on the same computer, MQTT had a mean latency of 0.6 ms against 3.0 ms for HTTP. The ELM327 layer was validated with the python-OBD library and with the OBD Auto Doctor app. The results hold for the simulator and say nothing about real vehicles; replacing the simulator with hardware and a field test remain as a second stage.
:::

**Keywords:** Vehicle telemetry. OBD-II. Simulation. Software-in-the-loop. ELM327.

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**LISTA DE FIGURAS**
:::

<!--LISTA_FIGURAS-->

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**LISTA DE TABELAS**
:::

<!--LISTA_TABELAS-->

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**LISTA DE ABREVIATURAS E SIGLAS**
:::

<!--SIGLAS-->

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

::: {custom-style="TituloPre"}
**SUMÁRIO**
:::

<!--SUMARIO-->
