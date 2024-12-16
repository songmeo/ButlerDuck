FROM python:3.9-slim

ARG XAI_API_KEY
ARG TOKEN
ARG OPENAI_API_KEY

ENV XAI_API_KEY=${XAI_API_KEY}
ENV TOKEN=${TOKEN}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

WORKDIR /app

RUN mkdir -p ./db && chmod -R 777 ./db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

COPY telegrambot.db ./db/telegrambot.db

CMD ["python", "main.py"]
