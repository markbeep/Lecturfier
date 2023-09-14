FROM python:3.11-alpine3.17 as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_helloNO_CACHE_DIR=1 \
    POETRY_VERSION=1.3

WORKDIR /app

RUN apk add --no-cache gcc musl-dev linux-headers g++ #zlib-dev jpeg-dev freetype-dev

RUN pip install --no-cache "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt | /venv/bin/pip install -r /dev/stdin


# lecturfier specific copies
FROM base as final

WORKDIR /app

COPY server.py .

CMD /venv/bin/python server.py
