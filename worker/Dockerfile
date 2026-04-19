FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

CMD ["python", "-m", "tasks.scheduler"]
