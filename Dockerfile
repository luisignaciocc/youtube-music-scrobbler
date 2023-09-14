FROM python:3.9-alpine3.13
ENV PYTHONUNBUFFERED 1
RUN apk update

RUN apk add --no-cache chromium

RUN pip install --upgrade pip

ADD ./requirements.txt /
RUN pip install -r /requirements.txt

COPY . .