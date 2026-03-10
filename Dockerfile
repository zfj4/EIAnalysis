FROM python:3.13-slim

WORKDIR /app

COPY dependencies.txt .
RUN pip install --no-cache-dir -r dependencies.txt

COPY . .

EXPOSE 9000

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:9000"]
