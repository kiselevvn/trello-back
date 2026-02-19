FROM python:3.14-slim

WORKDIR /app

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка uv (современный альтернативный менеджер пакетов для Python)
RUN pip install --no-cache-dir uv

# Копирование файлов зависимостей
COPY pyproject.toml uv.lock ./

# Установка зависимостей с использованием uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Копирование исходного кода
COPY . .

EXPOSE 8000

CMD ["gunicorn", "your_project.wsgi:application", "--bind", "0.0.0.0:8000"]