---
name: plan-sessions
description: Lê as tarefas do projeto (tasks/*.md ou a spec), agrupa em sessões, define a ordem de execução e pré-seleciona o modelo mais barato que dá conta de cada uma. Use ao planejar ou replanejar o trabalho.
---

# plan-sessions

Transforma tarefas em um plano de sessões enxuto em tokens. Só recomenda; não troca o modelo sozinho.

## Entrada

1. Liste `tasks/*.md`. Leia **apenas o cabeçalho (frontmatter) e a seção Escopo** de cada uma.
2. Se `tasks/` estiver vazio, derive as tarefas das fases do plano em `docs/spec/` (seção de plano) e crie os arquivos antes de seguir.
3. Não leia a spec inteira nem o código.

## Passos

1. **Grafo de dependências** a partir de `depends_on`. Detecte ciclos e avise.
2. **Ordem**: ordenação topológica; entre tarefas livres, primeiro o caminho crítico, depois as de menor peso.
3. **Sessões**: uma tarefa por sessão. Divida tarefas de peso G em duas. Nunca junte duas tarefas.
4. **Paralelismo**: marque as tarefas sem dependência entre si (`parallel_with`).
5. **Modelo** (o mais barato que serve):
   - `haiku`: boilerplate, estrutura, CRUD, scripts, interfaces simples, documentação mecânica.
   - `sonnet`: lógica de protocolo, concorrência, parsing, SVG/UI, análise de dados, texto técnico.
   - `opus`: apenas revisão de arquitetura, bug que resistiu a 2 tentativas do Sonnet e revisão final de coerência.
   - Em dúvida, escolha o mais barato e escreva a condição de escalada. Nunca suba "por precaução".
6. **Escalada**: confirme que cada tarefa tem `escalate_if` concreto e mensurável (ex.: "falha após 2 iterações"). Complete se faltar.
7. **Cabeçalhos**: garanta `model`, `session`, `order`, `depends_on`, `parallel_with`, `weight`, `escalate_if` e `spec` em cada tarefa. Edite só o frontmatter.

## Saída

Escreva `docs/PLAN.md` com:

- Tabela: Ordem | Sessão | Tarefa | Modelo | Depende de | Paralelizável com | Peso | Escalar se.
- Caminho crítico e marco do MVP.
- Seção "Como lançar": `/clear`, `/model <x>` e o prompt de uma linha da tarefa.
- Regras de economia: um `/clear` por sessão, testes primeiro, saída curta (`pytest -q --tb=short`), pedir diffs, buscas amplas em subagente.

Termine com um relatório de até 10 linhas: número de sessões, divisão por modelo, caminho crítico e riscos.

## Replanejamento

Se o usuário disser que uma tarefa terminou, mudou ou escalou, atualize só as linhas afetadas de `docs/PLAN.md` e os cabeçalhos envolvidos. Não regere tudo.
