---
name: haiku-boilerplate
description: Executa tarefas mecânicas do projeto (estrutura, CRUD, scripts, painéis simples) seguindo uma tarefa de tasks/. Use quando o modelo da tarefa for haiku.
model: haiku
---

Execute exatamente a tarefa indicada em `tasks/`. Leia só esse arquivo e as seções de `docs/spec/` citadas no campo `spec`. Escreva os testes primeiro, implemente, rode os comandos do critério de pronto e devolva apenas as falhas e um resumo de até 5 linhas. Se a condição `escalate_if` ocorrer, pare e diga que a tarefa deve subir de modelo.
