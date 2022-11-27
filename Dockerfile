FROM python:3.10-alpine3.16

RUN apk --no-cache add gcc musl-dev libpq-dev linux-headers zlib-dev jpeg-dev g++ freetype-dev

# makes numpy install quicker
RUN apk add --no-cache --update py3-numpy
ENV PYTHONPATH=/usr/lib/python3.10/site-packages

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY images images
COPY config config
COPY helper helper
COPY cogs cogs
COPY bot.py .

CMD ["python", "bot.py"]
