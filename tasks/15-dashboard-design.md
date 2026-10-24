---
id: "15"
title: Redesenho visual do dashboard e do painel do simulador
model: sonnet
session: 15
order: 15
depends_on: ["14"]
parallel_with: []
weight: M
escalate_if: "o resultado visual continua desorganizado ou parecido com o anterior após 2 iterações: usar opus uma vez para direção de design"
spec: docs/spec/07-dados-web.md
---

## Escopo

Melhorar o design do dashboard (porta 8000) e do painel do simulador (porta 8001). Hoje o aspecto é de protótipo: cartões soltos, hierarquia fraca, painel sem acabamento. Os dois devem parecer um produto único.

## Direção de design

- **Tema claro e limpo**: fundo branco ou cinza muito claro, sem tema escuro. Cartões com borda fina e sombra leve, cantos arredondados, espaçamento generoso e consistente (escala de 4 ou 8 px).
- **Tipografia**: uma família sem serifa legível (pilha de fontes do sistema ou uma fonte local, sem depender de CDN). Números grandes e com algarismos tabulares nos valores principais; rótulos pequenos em maiúsculas com espaçamento entre letras e cinza médio.
- **Hierarquia**: o conta-giros e a velocidade são os destaques; temperatura, combustível, tensão e carga ficam em um bloco secundário; diagnóstico e eventos em faixa própria. Alinhar tudo a uma grade de colunas.
- **Cor com significado**: azul para valores normais, âmbar para atenção, vermelho para alerta (faixa vermelha do conta-giros, MIL aceso, temperatura alta). Estado de conexão com ponto colorido e texto. Contraste mínimo AA.
- **Medidores em SVG** mais refinados: arco com gradiente sutil, marcações limpas, ponteiro fino, valor digital no centro, animação suave de transição.
- **Gráfico dos últimos 60 s**: linha fina, área sob a linha com cor suave, grade discreta, eixo de tempo legível, seleção da variável por abas em vez de lista suspensa.
- **Painel do simulador**: controles agrupados por função, sliders estilizados com o valor ao lado, chave "ECU sem resposta" com estilo de interruptor, botões com hierarquia (primário e secundário), monitor de quadros em fonte monoespaçada com entrada e saída em cores diferentes e rolagem automática.
- **Estados**: conectado, reconectando e sem dados bem distintos. Valores defasados esmaecidos (comportamento da tarefa 14).
- **Responsivo** de 1280 px até 1920 px, sem rolagem horizontal e sem controle cortado.
- Sem bibliotecas externas e sem arquivos de CDN. Textos da interface em português do Brasil, sem travessões longos.

## Processo

1. Gere as capturas "antes" com `python scripts/capturar_telas.py --saida docs/img/antes`.
2. Implemente por partes (tokens de cor e espaçamento em `style.css` compartilhado, depois dashboard, depois painel).
3. Gere as capturas "depois", **abra os PNGs e critique o resultado** (alinhamento, contraste, hierarquia, texto cortado). Itere até os pontos corrigidos.
4. Compare com as capturas "antes" e escreva em `docs/duvidas.md` o que mudou e o que ainda incomoda.

## Testes

- Os testes existentes continuam passando (ids usados pelo JavaScript, `node --check`, entrega no WebSocket).
- Teste que verifica que o HTML servido não referencia nenhuma URL externa (`http://` ou `https://` fora de `localhost`).

## Critério de pronto

```bash
pytest -q --tb=short tests/unit tests/integration tests/e2e
make lint
python scripts/capturar_telas.py --saida docs/img    # dashboard.png e painel.png novos
```

## Fora desta tarefa

Novas funções, novos PIDs e mudança de API.

## Prompt de lançamento

```text
Leia apenas tasks/15-dashboard-design.md e docs/spec/07-dados-web.md. Capture o antes, redesenhe, capture o depois, abra os PNGs para criticar e iterar, e mostre só o que ficou pendente.
```
