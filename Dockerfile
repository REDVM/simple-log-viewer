FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv


WORKDIR /app
COPY src/pyproject.toml .
COPY src/uv.lock .
COPY src/*.py .

# Installation des dépendances
# RUN /uvbin/uv pip install --system psycopg[binary] requests apscheduler loguru
RUN /uvbin/uv venv --python 3.12

CMD ["/uvbin/uv", "run", "python", "main.py"]