FROM python:3.12-slim

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

EXPOSE 8000
