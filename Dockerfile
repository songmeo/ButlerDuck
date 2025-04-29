FROM python:3.12

WORKDIR /app

COPY src/ ./

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
