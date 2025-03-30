import os
import json
import logging
import fitz
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
from pathlib import Path

# Configuración de logging para registrar eventos y errores
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

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
        raise ValueError(
            f"No se pudo descargar el PDF. Estado: {r.status_code}")

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
    df = pytesseract.image_to_data(
        img, output_type=Output.DATAFRAME, lang='spa')
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
        tables = camelot.read_pdf(
            pdf_path, pages=str(page_number), flavor="lattice")
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
        widgets = page.widgets()
        if widgets:
            for w in widgets:
                formularios.append({
                    "pagina": i + 1,
                    "campo_name": getattr(w, "field_name", ""),
                    "campo_value": getattr(w, "field_value", "")
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

# Aseguramos las importaciones necesarias para el OCR optimizado
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from concurrent.futures import ProcessPoolExecutor

# Configuración personalizada para Tesseract
CUSTOM_CONFIG = r'--oem 1 --psm 6'

def procesar_pdf(pdf_path, carpeta_salida, idioma="spa"):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"No se encontró: {pdf_path}")
    os.makedirs(carpeta_salida, exist_ok=True)

    doc = fitz.open(pdf_path)
    plumber_pdf = pdfplumber.open(pdf_path)
    npages = doc.page_count
    md = doc.metadata or {}

    # Debug
    print("DEBUG >>> metadata:", md)
    print("DEBUG >>> type of metadata:", type(md))
    logging.info(f"DEBUG >>> metadata: {md}")
    logging.info(f"DEBUG >>> type: {type(md)}")

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
            # Optimización: extraer solo la imagen de la página actual con dpi reducido
            images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=250)
            if images:
                contenido = pytesseract.image_to_string(images[0], config=CUSTOM_CONFIG)
            else:
                contenido = ""
            ocr_flag = True
            pags_ocr += 1

        prec = calcular_precision_aproximada(contenido)
        info_paginas.append({
            "pagina": page_num,
            "texto": contenido,
            "ocr": ocr_flag,
            "precision_aproximada": prec,
            "tablas": tablas_pagina if tablas_pagina else []
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
    texto_path = os.path.join(carpeta_salida, "resultado.txt")
    with open(texto_path, "w", encoding="utf-8") as ft:
        lineas_txt = []
        for p in info_paginas:
            lineas_txt.append(f"[Página {p['pagina']}]\n{p['texto']}")
            if p.get("tablas"):
                for idx, tabla in enumerate(p["tablas"], start=1):
                    lineas_txt.append(f"[Tabla {idx} - Página {p['pagina']}]\n{tabla}")
        ft.write("\n\n".join(lineas_txt))

    # Crear índice de búsqueda
    indice_dir = os.path.join(carpeta_salida, "indice_whoosh")
    todo_el_texto = "\n".join(texto_global_completo)
    crear_indice_y_indexar(indice_dir, todo_el_texto)

    logging.info("Proceso de extracción completado.")
    return json_path, texto_path

######################################
# MENÚ Y EJECUCIÓN
######################################

import os

def obtener_ruta_valida():
    ruta = input("Ingrese la ruta completa del archivo PDF: ").strip()

    # Quitar comillas dobles o simples al inicio y fin de la ruta (si las hubiera)
    ruta = ruta.strip('\"').strip('\'')

    # Reemplazar barras invertidas usadas para escapar espacios
    ruta = ruta.replace("\\", "")

    # Expandir caracteres especiales (como ~ para home)
    ruta = os.path.expanduser(ruta)

    # Normalizar la ruta
    ruta = os.path.normpath(ruta)

    # Si la ruta existe, devolverla
    if os.path.exists(ruta):
        return ruta
    else:
        print("No se encontró el archivo especificado.")
        return None

def menu():
    while True:
        print("\n=== MENÚ PRINCIPAL ===")
        print("1. Ingresar URL de PDF")
        print("2. Subir archivo PDF desde el escritorio")
        print("3. Probar con enlace del MOP")
        print("4. Terminar proceso")

        import sys

        def is_interactive():
            return sys.stdin.isatty() and sys.stdout.isatty()

        if not is_interactive():
            print("Entorno no interactivo detectado. Finalizando ejecución.")
            return

        opcion = input("Seleccione una opción (1-4): ").strip()

        if opcion == "1":
            url = input("Ingrese la URL del PDF: ").strip()
            if not url:
                print("No se ingresó una URL válida.")
                continue
            try:
                procesar_desde_url(url)
            except Exception as e:
                logging.error(f"Error: {e}")
            continue

        elif opcion == "2":
            ruta = input("Ingrese la ruta completa del archivo PDF: ").strip()
            if not os.path.isfile(ruta):
                print("No se encontró el archivo especificado.")
                continue
            try:
                procesar_desde_archivo(ruta)
            except Exception as e:
                logging.error(f"Error: {e}")
            continue

        elif opcion == "3":
            enlace_mop = "https://planeamiento.mop.gob.cl/uploads/sites/12/2025/02/indices_enero_2025-copia.pdf"
            try:
                procesar_desde_url(enlace_mop)
            except Exception as e:
                logging.error(f"Error: {e}")
            continue

        elif opcion == "4":
            print("Proceso finalizado.")
            break

        else:
            print("Opción no válida. Intente nuevamente.")

def procesar_desde_url(url):
    pdf_path = "temp.pdf"
    carpeta_salida = "resultado"
    os.makedirs(carpeta_salida, exist_ok=True)
    descargar_pdf(url, pdf_path)
    generar_resultados(pdf_path, carpeta_salida)

def procesar_desde_archivo(path):
    carpeta_salida = "resultado"
    os.makedirs(carpeta_salida, exist_ok=True)
    temp_path = "temp.pdf"
    shutil.copy(path, temp_path)
    generar_resultados(temp_path, carpeta_salida)

def generar_resultados(pdf_path, carpeta_salida):
    json_path, txt_path = procesar_pdf(pdf_path, carpeta_salida)
    pdf_output = os.path.join(carpeta_salida, "original.pdf")
    shutil.copy(pdf_path, pdf_output)
    import subprocess
    subprocess.run(["zip", "-j", "resultado.zip", json_path, txt_path, pdf_output], check=True)
    destino = os.path.join(os.getcwd(), "resultado.zip")  # Guardar en el directorio actual
    shutil.move("resultado.zip", destino)
    print(f"Proceso completado. ZIP guardado en: {destino}")

if __name__ == "__main__":
    menu()

