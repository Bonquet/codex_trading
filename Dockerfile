FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8787

WORKDIR /app

COPY . .

EXPOSE 8787

CMD ["sh", "-c", "python -m xauusd_scalp_master serve --host ${HOST:-0.0.0.0} --port ${PORT:-8787}"]
