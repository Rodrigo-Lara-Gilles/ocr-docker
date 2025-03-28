import os
import json
import pytest
import tempfile
from pathlib import Path

import app

# Pruebas para calcular_precision_aproximada

def test_calcular_precision_aproximada_vacio():
    assert app.calcular_precision_aproximada("") == 0
    assert app.calcular_precision_aproximada("   ") == 0

def test_calcular_precision_aproximada_normal():
    # En "abc123", todos los caracteres son alfanuméricos, precision = 6/6 = 1.0
    assert app.calcular_precision_aproximada("abc123") == 1.0
    # En "a!b@c#", solo se consideran a, b, c; precisión = 3/6 = 0.5
    assert app.calcular_precision_aproximada("a!b@c#") == 0.5

# Pruebas para descargar_pdf usando monkeypatch para simular la respuesta HTTP

def test_descargar_pdf_success(tmp_path, monkeypatch):
    class FakeResponse:
        def __init__(self, content, status_code):
            self.content = content
            self.status_code = status_code
    def fake_get(url):
        return FakeResponse(b"fake pdf content", 200)
    monkeypatch.setattr(app.requests, "get", fake_get)
    output_file = str(tmp_path / "temp.pdf")
    result = app.descargar_pdf("http://example.com/fake.pdf", output_file)
    assert os.path.exists(output_file)
    with open(output_file, "rb") as f:
        content = f.read()
    assert content == b"fake pdf content"

def test_descargar_pdf_failure(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.content = b""
    def fake_get(url):
        return FakeResponse(404)
    monkeypatch.setattr(app.requests, "get", fake_get)
    with pytest.raises(ValueError):
        app.descargar_pdf("http://example.com/fake.pdf")

# Prueba para guardar_tablas_separadas

def test_guardar_tablas_separadas(tmp_path):
    tablas = ["+---+\n| a |\n+---+"]
    carpeta_salida = tmp_path / "salida"
    carpeta_salida.mkdir()
    resultado = app.guardar_tablas_separadas(tablas, str(carpeta_salida), "1")
    assert os.path.exists(resultado)
    with open(resultado, "r", encoding="utf-8") as f:
         data = json.load(f)
    assert isinstance(data, list)
    assert data[0]["tabla_num"] == 1
    assert isinstance(data[0]["contenido"], list)

# Prueba para crear y buscar en el índice de búsqueda

def test_crear_y_buscar_indice(tmp_path):
    carpeta_indice = str(tmp_path / "indice")
    texto = "Este es un documento de prueba. Contiene información sobre OCR."
    app.crear_indice_y_indexar(carpeta_indice, texto)
    results = app.buscar_en_indice(carpeta_indice, "prueba")
    assert isinstance(results, list)
    assert len(results) > 0