# Aplicação completa (servidor, simulador, painel, ELM327 e coletor) num contêiner.
FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir -e .

EXPOSE 8000 8001 35000
VOLUME /app/data
CMD ["python", "-m", "obd", "run", "--host", "0.0.0.0", "--db", "/app/data/obd.db"]
