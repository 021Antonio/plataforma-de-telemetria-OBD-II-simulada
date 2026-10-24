#!/bin/sh
# Ajustes de git para o repositório montado do Windows, depois executa o comando.
git config --global --add safe.directory /work
git config --global core.autocrlf input
git config --global user.name "${GIT_AUTHOR_NAME:-night-runner}"
git config --global user.email "${GIT_AUTHOR_EMAIL:-night-runner@users.noreply.github.com}"
exec "$@"
