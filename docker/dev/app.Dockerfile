FROM python:3.11-slim-bookworm

LABEL com.class-git-forge.repo="class-git-forge" \
      com.class-git-forge.dev="true" \
      com.class-git-forge.service="app"

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash app

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /workspace \
    && chown -R app:app /workspace

USER app

CMD ["python", "-m", "app.main"]
