#!/usr/bin/env python3
"""
app.py - Prototipo OCR para Documentos Oficiales del MOP

Este script implementa la lógica para:
  - Descargar un PDF desde una URL.
  - Procesar el PDF extrayendo texto digital y aplicando OCR a páginas escaneadas.
  - Extraer tablas mediante Camelot y pdfplumber, y guardar cada conjunto en JSON.
  - Extraer formularios (campos de formulario) de las páginas.
  - Indexar el contenido global usando Whoosh.
  - Generar archivos de salida (resultado.json, resultado.txt).
  - Presentar una interfaz interactiva (con ipywidgets) para elegir método de ingreso.

Uso:
  - Desde consola:
      python app.py --pdf ruta_al_pdf.pdf --output salida
      python app.py --url https://ejemplo.com/archivo.pdf --output salida
  - En entornos interactivos (Google Colab, Jupyter Notebook) se mostrará una UI.
"""

import os
import json
import logging
import fitz                   # PyMuPDF
import requests
import pdfplumber
import camelot
import pytesseract
from pytesseract import Output
from PIL import Image
from pdf2image import convert_from_path
from tabulate import tabulate
import shutil
from whoosh import index
from whoosh.fields import Schema, TEXT, ID

# Configuración de logging para registrar eventos y errores
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

###################################
# FUNCIONES AUXILIARES
###################################

def descargar_pdf(url, output_file="temp.pdf"):
    """
    Descarga un PDF desde una URL y lo guarda en output_file.
    """
    logging.info(f"Descargando PDF desde: {url}")
    r = requests.get(url)
    if r.status_code == 200:
        with open(output_file, "wb") as f:
            f.write(r.content)
        logging.info(f"PDF descargado correctamente: {output_file}")
        return output_file
    else:
        raise ValueError(f"No se pudo descargar el PDF. Estado: {r.status_code}")

def calcular_precision_aproximada(texto):
    """
    Calcula la precisión aproximada del OCR en función del porcentaje de caracteres alfanuméricos.
    """
    t = texto.strip()
    if not t:
        return 0
    letras_numeros = sum(c.isalnum() for c in t)
    return round(letras_numeros / len(t), 2)

def bounding_boxes_a_tabla(img, threshold_vertical=10, threshold_horizontal=60):
    """
    Aplica OCR a la imagen y organiza el resultado en una tabla utilizando bounding boxes.
    """
    df = pytesseract.image_to_data(img, output_type=Output.DATAFRAME, lang='spa')
    df = df.dropna(subset=["text"])
    df = df[df.conf != -1].reset_index(drop=True)
    df = df.sort_values(by="top").reset_index(drop=True)
    filas, fila_actual = [], []
    last_top = None
    for _, row in df.iterrows():
        if last_top is None:
            fila_actual.append(row)
            last_top = row["top"]
        else:
            if abs(row["top"] - last_top) < threshold_vertical:
                fila_actual.append(row)
            else:
                filas.append(fila_actual)
                fila_actual = [row]
            last_top = row["top"]
    if fila_actual:
        filas.append(fila_actual)
    tabla_final = []
    for fila in filas:
        orden = sorted(fila, key=lambda x: x["left"])
        celdas = []
        current_col = [orden[0]["text"]]
        last_right = orden[0]["left"] + orden[0]["width"]
        for w in orden[1:]:
            gap = w["left"] - last_right
            if gap > threshold_horizontal:
                celdas.append(" ".join(current_col))
                current_col = [w["text"]]
            else:
                current_col.append(w["text"])
            last_right = w["left"] + w["width"]
        celdas.append(" ".join(current_col))
        tabla_final.append(celdas)
    max_cols = max(len(r) for r in tabla_final) if tabla_final else 0
    headers = [f"Col{i+1}" for i in range(max_cols)]
    ajustada = []
    for row in tabla_final:
        if len(row) < max_cols:
            row += [""] * (max_cols - len(row))
        ajustada.append(row)
    return tabulate(ajustada, headers=headers, tablefmt="grid")

def extraer_tablas_camelot(pdf_path, page_number):
    """
    Extrae tablas de una página del PDF usando Camelot.
    """
    try:
        tables = camelot.read_pdf(pdf_path, pages=str(page_number), flavor="lattice")
        ascii_tables = []
        for t in tables:
            df = t.df
            ascii_table = tabulate(df.values.tolist(), tablefmt="grid")
            ascii_tables.append(ascii_table)
        return ascii_tables
    except Exception as e:
        logging.warning(f"[Camelot] Error en la página {page_number}: {e}")
        return []

def extraer_tablas_pdfplumber(plumber_page):
    """
    Extrae tablas de una página del PDF usando pdfplumber.
    """
    ascii_tables = []
    tbls = plumber_page.extract_tables()
    if tbls:
        for tbl in tbls:
            ascii_tables.append(tabulate(tbl, tablefmt="grid"))
    return ascii_tables

def guardar_tablas_separadas(tablas, carpeta_salida, nombre_pag):
    """
    Guarda las tablas extraídas de una página en un archivo JSON separado.
    """
    if not tablas:
        return None
    data_tablas = []
    for idx, tab in enumerate(tablas, start=1):
        data_tablas.append({"tabla_num": idx, "contenido": tab.split("\n")})
    path_tablas = os.path.join(carpeta_salida, f"tablas_pag_{nombre_pag}.json")
    with open(path_tablas, "w", encoding="utf-8") as f:
        json.dump(data_tablas, f, indent=2, ensure_ascii=False)
    return path_tablas

def extraer_formularios(doc):
    """
    Extrae campos de formulario (widgets) de cada página del PDF.
    """
    formularios = []
    for i, page in enumerate(doc):
        if page.widgets:
            for w in page.widgets:
                formularios.append({
                    "pagina": i+1,
                    "campo_name": w.field_name,
                    "campo_value": w.field_value
                })
    return formularios

def crear_indice_y_indexar(carpeta_indice, texto_global):
    """
    Crea un índice con Whoosh e indexa el contenido global extraído.
    """
    if not os.path.exists(carpeta_indice):
        os.mkdir(carpeta_indice)
    schema = Schema(id=ID(stored=True), content=TEXT(stored=False))
    ix = index.create_in(carpeta_indice, schema)
    writer = ix.writer()
    writer.add_document(id="documento_pdf", content=texto_global)
    writer.commit()

def buscar_en_indice(carpeta_indice, consulta):
    """
    Realiza una búsqueda en el índice creado con Whoosh.
    """
    ix = index.open_dir(carpeta_indice)
    with ix.searcher() as searcher:
        from whoosh.qparser import QueryParser
        parser = QueryParser("content", ix.schema)
        query = parser.parse(consulta)
        results = searcher.search(query, limit=10)
        return [r.fields() for r in results]

######################################
# PROCESAMIENTO DEL PDF
######################################
def procesar_pdf(pdf_path, carpeta_salida, idioma="spa"):
    """
    Procesa el PDF extrayendo texto, tablas y formularios, y crea un índice de búsqueda.
    Genera los archivos resultado.json y resultado.txt.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"No se encontró: {pdf_path}")
    os.makedirs(carpeta_salida, exist_ok=True)

    doc = fitz.open(pdf_path)
    plumber_pdf = pdfplumber.open(pdf_path)
    npages = doc.page_count
    md = doc.metadata or {}

    # Extraer formularios (si existen)
    formularios_detectados = extraer_formularios(doc)

    pags_ocr, pags_texto = 0, 0
    info_paginas = []
    texto_global_completo = []  # Para indexar luego

    for i in range(npages):
        page_num = i + 1
        py_page = doc[i]
        txt_raw = py_page.get_text().strip()
        plumber_page = plumber_pdf.pages[i]
        contenido = ""
        ocr_flag = False
        tablas_pagina = []

        if txt_raw:
            pags_texto += 1
            contenido = txt_raw
            camelot_tables = extraer_tablas_camelot(pdf_path, page_num)
            if camelot_tables:
                tablas_pagina.extend(camelot_tables)
            else:
                plumber_tables = extraer_tablas_pdfplumber(plumber_page)
                if plumber_tables:
                    tablas_pagina.extend(plumber_tables)
        else:
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
            if images:
                contenido = bounding_boxes_a_tabla(images[0])
            ocr_flag = True
            pags_ocr += 1

        prec = calcular_precision_aproximada(contenido)
        info_paginas.append({
            "pagina": page_num,
            "texto": contenido,
            "ocr": ocr_flag,
            "precision_aproximada": prec
        })
        texto_global_completo.append(contenido)

        if tablas_pagina:
            guardar_tablas_separadas(tablas_pagina, carpeta_salida, str(page_num))

    doc.close()
    plumber_pdf.close()

    total = pags_ocr + pags_texto
    if total == 0:
        raise ValueError("No se procesaron páginas.")
    ocr_ratio = round(pags_ocr / total, 2)
    data_final = {
        "archivo_procesado": os.path.basename(pdf_path),
        "metadata_pdf": {
            "titulo": md.get("title", ""),
            "autor": md.get("author", ""),
            "num_paginas": npages
        },
        "estadisticas": {
            "paginas_totales": total,
            "paginas_con_ocr": pags_ocr,
            "paginas_texto_digital": pags_texto,
            "ocr_ratio": ocr_ratio
        },
        "contenido_paginas": info_paginas,
        "formularios": formularios_detectados
    }
    json_path = os.path.join(carpeta_salida, "resultado.json")
    with open(json_path, "w", encoding="utf-8") as fj:
        json.dump(data_final, fj, indent=2, ensure_ascii=False)

    texto_path = os.path.join(carpeta_salida, "resultado.txt")
    with open(texto_path, "w", encoding="utf-8") as ft:
        ft.write("\n\n".join([f"[Página {p['pagina']}]: {p['texto']}" for p in info_paginas]))

    # Crear índice de búsqueda
    indice_dir = os.path.join(carpeta_salida, "indice_whoosh")
    todo_el_texto = "\n".join(texto_global_completo)
    crear_indice_y_indexar(indice_dir, todo_el_texto)

    logging.info("Proceso de extracción completado.")
    return json_path, texto_path

######################################
# INTERFAZ CON IPYWIDGETS
######################################
import ipywidgets as widgets
from IPython.display import display, clear_output
from google.colab import files

lbl_info = widgets.Label(value="Escoge método para tu PDF:")
lbl_error = widgets.Label(value="", layout=widgets.Layout(width="50%"))
btn_url = widgets.Button(description="Ingresar URL")
btn_upload = widgets.Button(description="Subir Archivo")
btn_procesar = widgets.Button(description="Procesar PDF", disabled=True)
txt_url = widgets.Text(description="URL PDF:", layout=widgets.Layout(width='50%'))

def show_main_buttons():
    clear_output()
    lbl_error.value = ""
    display(lbl_info, lbl_error)
    display(btn_url, btn_upload, btn_procesar)

def on_btn_url_click(b):
    lbl_error.value = ""
    def on_descargar_click(_):
        global pdf_local_path
        if not txt_url.value.strip():
            lbl_error.value = "Ingresa una URL."
            return
        try:
            pdf_local_path = "temp.pdf"
            descargar_pdf(txt_url.value.strip(), pdf_local_path)
            lbl_error.value = "Descargado con éxito."
            btn_procesar.disabled = False
        except Exception as e:
            lbl_error.value = f"Error: {e}"
    btn_descargar = widgets.Button(description="Descargar PDF")
    btn_descargar.on_click(on_descargar_click)
    clear_output()
    display(widgets.HTML("<h4>Ingresa la URL del PDF</h4>"), txt_url, btn_descargar, lbl_error)
    display(btn_procesar)

def on_btn_upload_click(b):
    lbl_error.value = ""
    file_uploader = widgets.FileUpload(accept=".pdf", multiple=False)
    def on_upload_change(change):
        global pdf_local_path
        up_file = file_uploader.value
        if up_file:
            fname = list(up_file.keys())[0]
            with open(fname, 'wb') as f:
                f.write(up_file[fname]['content'])
            pdf_local_path = fname
            lbl_error.value = f"Archivo '{fname}' subido."
            btn_procesar.disabled = False
    file_uploader.observe(on_upload_change, names='value')
    clear_output()
    display(widgets.HTML("<h4>Subir PDF local</h4>"), file_uploader, lbl_error)
    display(btn_procesar)

def on_btn_procesar_click(b):
    global pdf_local_path
    if not pdf_local_path or not os.path.exists(pdf_local_path):
        lbl_error.value = "No hay PDF."
        return
    base_name = os.path.splitext(os.path.basename(pdf_local_path))[0]
    folder_name = base_name[:10]
    os.makedirs(folder_name, exist_ok=True)
    
    json_path, txt_path = procesar_pdf(pdf_local_path, folder_name)
    original_pdf_path = os.path.join(folder_name, "original.pdf")
    shutil.copy(pdf_local_path, original_pdf_path)
    
    import subprocess
    subprocess.run(["zip","-j","resultado.zip", json_path, txt_path, original_pdf_path], check=True)
    files.download("resultado.zip")
    lbl_error.value = "Proceso completado."
    btn_procesar.disabled = True
    show_main_buttons()

btn_url.on_click(on_btn_url_click)
btn_upload.on_click(on_btn_upload_click)
btn_procesar.on_click(on_btn_procesar_click)

show_main_buttons()

# (E) Notas de CI/CD
# Se recomienda agregar un archivo de pruebas unitarias y configurar un workflow (GitHub Actions o similar)
# para ejecutar los tests automáticamente en cada cambio.