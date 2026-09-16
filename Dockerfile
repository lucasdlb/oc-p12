FROM apache/airflow:3.3.1

USER root
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

COPY --chown=airflow:0 pyproject.toml uv.lock README.md ./
RUN uv export --format requirements-txt --no-dev --no-emit-project --locked > requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

COPY --chown=airflow:0 src ./src
RUN uv pip install --system --no-cache --no-deps .

USER airflow
