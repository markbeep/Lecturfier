FROM python:3.10-alpine

RUN apk --no-cache add gcc musl-dev libpq-dev linux-headers zlib-dev jpeg-dev g++

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY images .
COPY config .
COPY helper .
COPY cogs .
COPY bot.py .

CMD ["python", "bot.py"]
