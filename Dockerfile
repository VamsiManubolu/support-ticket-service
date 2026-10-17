FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
RUN useradd --create-home app && chown app /app

# deps first so this layer is cached; dev extras because tests run in this container
COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml --extra dev

COPY . .

USER app
EXPOSE 8000
CMD ["./entrypoint.sh"]
