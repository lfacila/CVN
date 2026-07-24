import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import pandas as pd
import json
import re

# Configuración de la página
st.set_page_config(page_title="Extractor CVN FECYT", page_icon="📄", layout="wide")
st.title("Extractor de Méritos para CVN (FECYT)")

# Configurar API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Falta configurar la GEMINI_API_KEY en los secretos de Streamlit.")

# Inicializar un historial en la sesión para guardar los méritos extraídos
if "historial_meritos" not in st.session_state:
    st.session_state.historial_meritos = []

# Interfaz principal
col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Configuración")
    categoria = st.selectbox("¿Qué tipo de mérito vas a procesar?", [
        "Artículo Científico", 
        "Ponencia / Comunicación en Congreso", 
        "Ensayo Clínico / Proyecto",
        "Tesis Dirigida"
    ])
    
    st.header("2. Subir Documentos")
    st.info("Puedes subir varios PDFs a la vez si son del mismo tipo.")
    documentos = st.file_uploader("Sube los PDFs", type=["pdf"], accept_multiple_files=True)
    
    procesar_btn = st.button("Extraer Datos")

with col2:
    st.header("3. Resultados Listos para Copiar")
    
    if procesar_btn and documentos:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Definir los campos a extraer según la categoría
        if categoria == "Artículo Científico":
            formato_esperado = '{"Título": "", "Autores": "", "Posición de firma": "", "Revista": "", "Año": "", "Volumen y Páginas": "", "DOI": "", "PMID": ""}'
        elif categoria == "Ponencia / Comunicación en Congreso":
            formato_esperado = '{"Título del trabajo": "", "Nombre del congreso": "", "Tipo de evento": "", "Tipo de participación": "", "Ciudad": "", "Fecha": "", "Entidad organizadora": ""}'
        elif categoria == "Ensayo Clínico / Proyecto":
            formato_esperado = '{"Nombre del proyecto": "", "Grado de contribución": "", "Entidad financiadora": "", "Fecha de inicio": ""}'
        else: # Tesis Dirigida
            formato_esperado = '{"Título del trabajo": "", "Alumno": "", "Entidad de realización": "", "Calificación": "", "Fecha de defensa": ""}'

        for doc in documentos:
            with st.spinner(f"Analizando: {doc.name}..."):
                # Extraer texto del PDF
                pdf_file = fitz.open(stream=doc.read(), filetype="pdf")
                texto_pdf = ""
                for page in pdf_file:
                    texto_pdf += page.get_text()
                
                # Prompt estructurado pidiendo JSON estricto
                prompt = f"""
                Eres un asistente experto en extracción de datos.
                Extrae los datos del siguiente documento correspondiente a un '{categoria}'.
                
                REGLAS ESTRICTAS:
                1. Devuelve ÚNICAMENTE un objeto JSON válido.
                2. No añadas introducciones, ni texto antes o después de las llaves {{ e }}.
                3. Escapa correctamente cualquier comilla doble (") dentro de los textos usando la barra invertida (\").
                4. Elimina los saltos de línea dentro de los valores extraídos.
                5. Usa esta estructura exacta (deja en blanco lo que no encuentres):
                {formato_esperado}
                
                Texto del documento:
                {texto_pdf}
                """
                
                try:
                    respuesta = model.generate_content(prompt)
                    
                    # Limpieza agresiva del texto devuelto
                    texto_respuesta = respuesta.text.strip()
                    
                    # Quitar las etiquetas de bloque de código si Gemini las pone
                    if texto_respuesta.startswith("```json"):
                        texto_respuesta = texto_respuesta[7:]
                    elif texto_respuesta.startswith("```"):
                        texto_respuesta = texto_respuesta[3:]
                        
                    if texto_respuesta.endswith("```"):
                        texto_respuesta = texto_respuesta[:-3]
                        
                    texto_respuesta = texto_respuesta.strip()
                    
                    # Buscar el bloque JSON
                    match = re.search(r'\{.*\}', texto_respuesta, re.DOTALL)
                    
                    if match:
                        clean_json = match.group(0)
                        datos_extraidos = json.loads(clean_json)
                        
                        # Añadir el nombre del archivo de origen y la categoría
                        datos_extraidos["Archivo Origen"] = doc.name
                        datos_extraidos["Categoría"] = categoria
                        
                        st.session_state.historial_meritos.append(datos_extraidos)
                        
                        st.success(f"✔️ {doc.name} procesado correctamente.")
                        # Mostrar en texto plano fácil de copiar
                        for clave, valor in datos_extraidos.items():
                            if clave not in ["Archivo Origen", "Categoría"]:
                                st.markdown(f"**{clave}:** {valor}")
                        st.divider()
                    else:
                        st.error(f"Error en {doc.name}: No se encontró un formato válido.")
                        with st.expander("Ver respuesta de la IA (Para depurar)"):
                            st.write(texto_respuesta)
                    
                except json.JSONDecodeError as json_error:
                    st.error(f"Error de formato en {doc.name}. El PDF tiene caracteres complejos que rompieron la estructura.")
                    with st.expander("Ver detalle del error"):
                        st.write(str(json_error))
                        st.write("Texto que intentó procesar:")
                        st.write(clean_json)
                except Exception as e:
                    st.error(f"Error técnico inesperado procesando {doc.name}.")
                    with st.expander("Ver detalle del error"):
                        st.write(str(e))

# Sección de Exportación
st.header("4. Repositorio Acumulado")
if st.session_state.historial_meritos:
    df = pd.DataFrame(st.session_state.historial_meritos)
    st.dataframe(df)
    
    # Botón para descargar en CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar todos los méritos en CSV (Para Excel)",
        data=csv,
        file_name='Meritos_CVN_Extraidos.csv',
        mime='text/csv',
    )
    
    if st.button("Limpiar historial"):
        st.session_state.historial_meritos = []
        st.experimental_rerun()
else:
    st.info("Aún no has procesado ningún documento. Los resultados aparecerán aquí y podrás exportarlos.")
