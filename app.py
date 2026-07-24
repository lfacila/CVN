import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import pandas as pd
import json
import re

# Configuración de la página
st.set_page_config(page_title="Extractor CVN FECYT", page_icon="📄", layout="wide")
st.title("Extractor Automático de Méritos para CVN (FECYT)")

# Configurar API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Falta configurar la GEMINI_API_KEY en los secretos de Streamlit.")
    st.stop()

# Inicializar un historial en la sesión para guardar los méritos extraídos
if "historial_meritos" not in st.session_state:
    st.session_state.historial_meritos = []

# Interfaz principal
col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Configuración")
    
    # Extraer la lista real de modelos autorizados
    try:
        modelos_disponibles = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        st.error("Error al conectar con la API de Google. Comprueba tu clave API.")
        st.stop()
        
    if not modelos_disponibles:
        st.error("Tu API Key no tiene acceso a modelos de generación de texto.")
        st.stop()
        
    modelo_elegido = st.selectbox("Selecciona el motor de Inteligencia Artificial", modelos_disponibles)
    
    st.header("2. Subir Documentos")
    st.info("Sube diplomas sueltos o tu CV completo. El sistema detectará automáticamente el tipo de mérito de cada elemento.")
    documentos = st.file_uploader("Sube los PDFs", type=["pdf"], accept_multiple_files=True)
    
    procesar_btn = st.button("Extraer Datos")

with col2:
    st.header("3. Resultados Listos para Copiar")
    
    if procesar_btn and documentos:
        model = genai.GenerativeModel(modelo_elegido)
        
        # Diccionario con las estructuras requeridas para FECYT
        esquemas_fecyt = """
        - "Artículo Científico": ["Título", "Autores", "Posición de firma", "Revista", "Año", "Volumen y Páginas", "DOI", "PMID", "Importancia del mérito"]
        - "Ponencia / Comunicación en Congreso": ["Título del trabajo", "Nombre del congreso", "Tipo de evento", "Tipo de participación", "Ciudad", "Fecha", "Entidad organizadora", "Importancia del mérito"]
        - "Ensayo Clínico / Proyecto": ["Nombre del proyecto", "Grado de contribución", "Entidad financiadora", "Fecha de inicio", "Importancia del mérito"]
        - "Tesis Dirigida": ["Título del trabajo", "Alumno", "Entidad de realización", "Calificación", "Fecha de defensa", "Importancia del mérito"]
        - "Formación Académica / Títulos Propios": ["Título del trabajo", "Entidad de realización", "Fecha", "Calificación", "Importancia del mérito"]
        - "Méritos de Innovación / Gestión Clínica": ["Tipo de mérito", "Cargo", "Entidad", "Fecha de inicio", "Fecha de fin", "Logros", "Importancia del mérito"]
        - "Organización de Actividades de Formación y I+D+i": ["Tipo de actividad", "Título de la actividad", "Entidad convocante", "Fecha", "Asistentes/Horas", "Importancia del mérito"]
        """

        for doc in documentos:
            with st.spinner(f"Analizando {doc.name} en busca de méritos..."):
                pdf_file = fitz.open(stream=doc.read(), filetype="pdf")
                texto_pdf = ""
                for page in pdf_file:
                    texto_pdf += page.get_text()
                
                # Prompt con auto-detección
                prompt = f"""
                Eres un asistente experto en extracción de datos curriculares para el estándar FECYT.
                Analiza el siguiente documento y extrae TODOS los méritos que encuentres (pueden ser decenas si es un CV completo).
                
                Para cada mérito, debes:
                1. Identificar a qué categoría pertenece utilizando ÚNICAMENTE una de las opciones de esta lista:
                {esquemas_fecyt}
                
                2. Redactar en el campo 'Importancia del mérito' un breve párrafo (2 o 3 líneas) justificando su valor para un cardiólogo clínico especializado en insuficiencia cardiaca y riesgo cardiovascular, o su aporte para un profesor universitario asociado. Sé riguroso.
                
                REGLAS ESTRICTAS:
                1. Devuelve ÚNICAMENTE un ARRAY JSON válido que empiece por [ y termine por ]. No añadas texto introductorio.
                2. Cada objeto dentro del array DEBE tener una clave llamada "Categoría detectada" con el nombre exacto de la categoría elegida.
                3. El resto de claves del objeto deben ser EXACTAMENTE las que corresponden a esa categoría según la lista anterior.
                4. Escapa comillas dobles internas con barra invertida (\").
                
                Texto del documento:
                {texto_pdf}
                """
                
                try:
                    respuesta = model.generate_content(prompt)
                    texto_respuesta = respuesta.text.strip()
                    
                    # Limpieza de formato
                    bloque_codigo = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', texto_respuesta, re.DOTALL | re.IGNORECASE)
                    if bloque_codigo:
                        clean_json = bloque_codigo.group(1)
                    else:
                        match = re.search(r'\[.*\]', texto_respuesta, re.DOTALL)
                        if match:
                            clean_json = match.group(0)
                        else:
                            start = texto_respuesta.find('[')
                            end = texto_respuesta.rfind(']')
                            clean_json = texto_respuesta[start:end+1] if start != -1 and end != -1 else texto_respuesta
                            
                    lista_extraida = json.loads(clean_json)
                    if isinstance(lista_extraida, dict):
                        lista_extraida = [lista_extraida]
                    
                    st.success(f"✔️ {doc.name} procesado: ¡Se han detectado {len(lista_extraida)} mérito(s)!")
                    
                    for i, datos in enumerate(lista_extraida):
                        # Extraer y normalizar la categoría detectada
                        cat_detectada = datos.pop("Categoría detectada", "Desconocida")
                        datos["Categoría"] = cat_detectada
                        datos["Archivo Origen"] = doc.name
                        
                        st.session_state.historial_meritos.append(datos)
                        
                        st.markdown(f"### Mérito {i+1} - {cat_detectada}")
                        for clave, valor in datos.items():
                            if clave not in ["Archivo Origen", "Categoría"]:
                                st.markdown(f"**{clave}:** {valor}")
                        st.divider()
                    
                except json.JSONDecodeError as json_error:
                    st.error(f"Error de formato en {doc.name}. El texto contiene caracteres que rompen la estructura.")
                    with st.expander("Ver detalle del error"):
                        st.write("Asegúrate de no exceder los límites de la IA si el CV es demasiado largo.")
                        if 'clean_json' in locals():
                            st.write(clean_json)
                        else:
                            st.write(texto_respuesta)
                except Exception as e:
                    st.error(f"Error técnico procesando {doc.name}.")
                    with st.expander("Ver detalle del error"):
                        st.write(str(e))

# Sección de Exportación
st.header("4. Repositorio Acumulado")
if st.session_state.historial_meritos:
    # Convertir a DataFrame. Pandas automáticamente alineará las columnas distintas creando huecos vacíos (NaN) donde no aplique.
    df = pd.DataFrame(st.session_state.historial_meritos)
    
    # Reordenar columnas para que Categoría y Archivo Origen salgan primero
    cols = df.columns.tolist()
    for col_name in ["Archivo Origen", "Categoría"]:
        if col_name in cols:
            cols.remove(col_name)
            cols.insert(0, col_name)
    df = df[cols]
    
    st.dataframe(df)
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar todos los méritos en CSV (Para Excel)",
        data=csv,
        file_name='Meritos_CVN_Extraidos.csv',
        mime='text/csv',
    )
    
    if st.button("Limpiar historial"):
        st.session_state.historial_meritos = []
        st.rerun()
else:
    st.info("Aún no has procesado ningún documento.")
