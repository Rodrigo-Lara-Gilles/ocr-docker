FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    ghostscript \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libxml2 \
    libxslt1-dev \
    libpoppler-cpp-dev \
    build-essential \
    python3-dev \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt
RUN pip install pytest

WORKDIR /app
COPY . /app

CMD ["python", "app.py"]