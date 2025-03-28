# Proyecto OCR para Documentos del MOP

Este proyecto implementa un prototipo de OCR que extrae texto de PDFs oficiales combinando  
la extracción de texto digital y OCR para páginas escaneadas. Además, se extraen tablas, se detectan  
formularios y se indexa el contenido para búsquedas posteriores.

## Requisitos del sistema

- **Python 3.7+** (se recomienda usar Python 3.12.9 o superior)
- **Poppler** instalado en el sistema:
  - **macOS**:
    ```bash
    brew install poppler
    ```
  - **Ubuntu/Debian**:
    ```bash
    sudo apt-get update
    sudo apt-get install poppler-utils
    ```
  - **Windows**:
    1. Descarga la versión precompilada de [Poppler para Windows](http://blog.alivate.com.au/poppler-windows/).
    2. Descomprime el contenido en una carpeta (por ejemplo, `C:\poppler\`).
    3. Agrega la ruta `C:\poppler\bin` a la variable de entorno `PATH`.
- **Tesseract OCR** instalado en el sistema:
  - **macOS**:
    ```bash
    brew install tesseract
    ```
  - **Ubuntu/Debian**:
    ```bash
    sudo apt-get update
    sudo apt-get install tesseract-ocr
    ```
  - **Windows**:
    1. Descarga el instalador de Tesseract desde [la página de Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
    2. Instálalo y asegúrate de que la ruta del ejecutable esté en la variable de entorno `PATH`.

## Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/Rodrigo-Lara-Gilles/ocr-project.git
   cd ocr-project
   ```
2. Crea y activa un entorno virtual:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Instala las dependencias:
   ```
   python3 -m pip install -r requirements.txt
   ```

## Uso

- Para procesar un PDF local:
  ```
  python app.py --pdf ruta_al_pdf.pdf --output salida
  ```
- Para procesar un PDF desde una URL:
  ```
  python app.py --url https://ejemplo.com/archivo.pdf --output salida
  ```

## Pruebas

Ejecuta las pruebas unitarias con:
```
pytest tests/
```

## CI/CD

Este proyecto incluye un workflow para GitHub Actions en `.github/workflows/ci.yml` que ejecuta
las pruebas en cada push o pull request.
