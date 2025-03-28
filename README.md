# Proyecto OCR para Documentos del MOP

Este proyecto implementa un prototipo de OCR que extrae texto de PDFs oficiales combinando
la extracción de texto digital y OCR para páginas escaneadas. Además, se extraen tablas, se detectan
formularios y se indexa el contenido para búsquedas posteriores.

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
   pip install -r requirements.txt
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
