FROM python:3.11.4-alpine3.18
LABEL authors="pavel"

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000