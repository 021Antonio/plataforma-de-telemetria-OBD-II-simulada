---
id: "11"
title: Reescrita dos capítulos do TCC com os resultados reais
model: sonnet
session: 12
order: 12
depends_on: ["10"]
parallel_with: []
weight: M
escalate_if: "revisão final de coerência entre objetivos, método e conclusões: usar opus uma vez"
spec: docs/spec/01-visao-requisitos.md, docs/spec/08-testes.md
---

## Escopo

Reescrever em `docs/tcc/` os capítulos afetados, usando apenas números medidos em `runs/` e em `docs/ensaios.md`.

## Arquivos

- `docs/tcc/01-objetivos.md`: pergunta de pesquisa, objetivo geral e específicos coerentes com o escopo (plataforma em software, validada por simulação e testes).
- `docs/tcc/02-materiais-metodos.md`: arquitetura, interfaces, ambiente de simulação e procedimentos de ensaio.
- `docs/tcc/03-resultados.md`: resultados E1 a E6 com tabelas e figuras, e a comparação entre duas máquinas.
- `docs/tcc/04-limitacoes-conclusao.md`: limitações declaradas (sem veículo, sem hardware embarcado, SIL) e trabalhos futuros (ESP32, ELM327 real, ensaio de campo).

## Regras

- Usar o termo "software-in-the-loop" e nunca "hardware-in-the-loop".
- Nenhuma afirmação sobre veículo real ou firmware embarcado sem evidência medida.
- Não usar travessões longos nem marcadores típicos de texto gerado por IA.
- Citar apenas referências já presentes no TCC original ou verificadas.

## Critério de pronto

- Cada número do texto tem origem em um arquivo de `runs/` ou em `docs/ensaios.md` (listar a origem em uma tabela no fim de cada capítulo).
- Objetivos, método, resultados e conclusão se respondem entre si (checklist de coerência no topo de `docs/tcc/04-limitacoes-conclusao.md`).

## Fora desta tarefa

Formatação final no modelo do IBMR e declaração de uso de IA, que são do autor.

## Prompt de lançamento

```text
Leia apenas tasks/11-texto-tcc.md, docs/ensaios.md e os arquivos de runs/ citados. Reescreva os capítulos indicados, liste a origem de cada número e mostre só o que ficou pendente.
```
