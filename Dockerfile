FROM node:20-bookworm-slim AS web-build

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime

ENV APP_ENV=prod \
    LOOM_DATA_DIR=/data \
    LOOM_BINDING_DIR=/app/config/customers \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY loom/ ./loom/
COPY schemas/ ./schemas/
COPY registry/ ./registry/
COPY config/customers/example.hiagent.yaml ./config/customers/example.hiagent.yaml
COPY --from=web-build /app/web/dist ./web/dist

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir \
    -i "$PIP_INDEX_URL" \
    --timeout 120 --retries 5 \
    .

EXPOSE 8000
CMD ["uvicorn", "loom.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
