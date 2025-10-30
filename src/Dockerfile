FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium


ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=8080

COPY . .

CMD ["python", "main.py"]