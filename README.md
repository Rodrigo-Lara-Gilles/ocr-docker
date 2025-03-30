# OCR Dockerizado para Documentos del MOP
 
Este proyecto implementa un sistema completo de OCR capaz de procesar documentos PDF del Ministerio de Obras Públicas (MOP) de Chile. El sistema puede:
 
- Extraer texto digital y escaneado (OCR)
- Detectar y extraer tablas usando Camelot y pdfplumber
- Detectar formularios
- Indexar el contenido para búsquedas rápidas con Whoosh
- Empaquetar los resultados en un archivo `.zip`
 
El proyecto ahora está completamente contenido en un **contenedor Docker**. ¡No requiere instalar nada en tu sistema!
 
---
 
## 🚀 Requisitos
 
- [Docker](https://docs.docker.com/get-docker/) instalado (puede usarse con Colima si estás en Mac)
 
---
 
## 🐳 Ejecutar en Docker
 
1. Cloná el repositorio:
 
   ```bash
   git clone https://github.com/Rodrigo-Lara-Gilles/ocr-docker.git
   cd ocr-docker
   ```
 
2. Construí la imagen:
 
   ```bash
   docker build -t ocr-app .
   ```
 
3. Ejecutá la app interactiva:
 
   ```bash
   docker run --rm -it -v "$(pwd)":/app ocr-app
   ```
 
Esto iniciará el menú interactivo que te permite procesar un PDF desde URL o archivo local.
 
---
 
## 📂 Estructura de salida
 
- `resultado/`: Carpeta con los resultados procesados
- `resultado.zip`: Archivo comprimido con el `.pdf`, `.json`, `.txt` y el índice Whoosh
 
---
 
## 🧪 Pruebas
 
Este proyecto incluye pruebas automatizadas con `pytest`.
 
Ejecutalas con:
 
```bash
pytest
```
 
---
 
## 📦 CI/CD
 
El flujo de trabajo de GitHub Actions (`.github/workflows/ci.yaml`) incluye:
 
- Instalación de dependencias
- Ejecución de pruebas
- Validación del build Docker
- Test de ejecución del contenedor
 
---