FROM python:3.13.1

WORKDIR /

COPY /requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY / .

CMD ["python", "bot.py"]