# Executor noturno isolado: Python 3.12 + make + Node + Claude Code, usuário sem privilégios.
FROM python:3.12-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends make git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Node (só o necessário) copiado da imagem oficial
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && npm install -g @anthropic-ai/claude-code

RUN useradd -m -u 1000 dev \
 && python -m venv /opt/venv \
 && /opt/venv/bin/pip install -q pyyaml \
 && chown -R dev:dev /opt/venv

COPY docker/night-entrypoint.sh /usr/local/bin/night-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/night-entrypoint && chmod +x /usr/local/bin/night-entrypoint

USER dev
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PIP_REQUIRE_VIRTUALENV=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NIGHT_PUSH=0
WORKDIR /work
ENTRYPOINT ["night-entrypoint"]
CMD ["python", "scripts/run_night.py", "--skip", "00", "11"]
