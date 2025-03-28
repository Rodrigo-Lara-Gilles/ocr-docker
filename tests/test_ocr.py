import pytest
import app

def test_procesar_pdf_inexistente():
    with pytest.raises(FileNotFoundError):
        app.procesar_pdf("archivo_inexistente.pdf", "salida_test")
