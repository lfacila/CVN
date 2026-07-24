import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
import io

# Configuración de la página
st.set_page_config(page_title="Actualizador CVN-PDF", page_icon="📄")
st.title("Actualizador Automático de CVN-PDF con Gemini Pro")

# Configurar API Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Falta configurar la GEMINI_API_KEY en los secretos de Streamlit.")

st.header("1. Sube tu CVN-PDF actual")
st.info("Sube el PDF que descargas desde FECYT (contiene el XML incrustado).")
base_pdf = st.file_uploader("Sube tu CVN base", type=["pdf"], key="base")

st.header("2. Sube el nuevo mérito")
nuevo_doc = st.file_uploader("Sube el artículo, diploma, certificado, etc.", type=["pdf"], key="nuevo")

categoria = st.selectbox("¿Qué tipo de mérito es?", [
    "Publicación / Artículo Científico", 
    "Ponencia en Congreso", 
    "Póster / Comunicación", 
    "Ensayo Clínico",
    "Tesis Dirigida",
    "Mérito Académico / Título"
])

if st.button("Procesar e inyectar al CVN-PDF"):
    if base_pdf and nuevo_doc:
        with st.spinner("Extrayendo XML y procesando con Inteligencia Artificial..."):
            
            # --- 1. Extraer el XML del PDF Base ---
            pdf_bytes = base_pdf.read()
            doc_base = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Buscar archivos incrustados
            embedded_files = doc_base.embfile_names()
            xml_text = ""
            xml_filename = ""
            
            if embedded_files:
                for emb in embedded_files:
                    if emb.endswith(".xml"):
                        xml_filename = emb
                        xml_bytes = doc_base.embfile_get(emb)
                        xml_text = xml_bytes.decode('utf-8', errors='ignore')
                        break
            
            if not xml_text:
                st.error("No se ha encontrado ningún archivo XML incrustado en el PDF base. Asegúrate de que es el PDF exportado por FECYT.")
                st.stop()
                
            # --- 2. Extraer texto del nuevo mérito ---
            doc_nuevo = fitz.open(stream=nuevo_doc.read(), filetype="pdf")
            texto_nuevo = ""
            for page in doc_nuevo:
                texto_nuevo += page.get_text()
                
            # --- 3. Llamada a Gemini para generar el nuevo nodo XML ---
            prompt = f"""
            Eres un experto en el estándar CVN de FECYT.
            A continuación te proporciono un documento de un nuevo mérito de la categoría '{categoria}'.
            Extrae los datos relevantes de este documento.
            
            Luego, analiza la estructura del CVN-XML base para ver exactamente cómo se etiquetan los méritos de esta categoría y devuelve ÚNICAMENTE el fragmento de código XML necesario para añadir este nuevo mérito. No inventes etiquetas que no existan en el estándar CVN.
            
            Texto del nuevo mérito:
            {texto_nuevo}
            """
            
            model = genai.GenerativeModel('gemini-pro')
            respuesta = model.generate_content(prompt)
            nuevo_nodo_xml = respuesta.text.replace("```xml", "").replace("```", "").strip()
            
            st.success("Información extraída y estructurada correctamente.")
            with st.expander("Ver el nodo XML generado"):
                st.code(nuevo_nodo_xml, language="xml")
            
            # --- 4. Inserción simple en el XML ---
            # Nota: Esto insertará el nodo generado justo antes de la etiqueta de cierre correspondiente.
            # Al ser un prototipo, lo insertamos al final del documento justo antes del cierre principal </cvn>
            # En producción, Gemini puede indicar dónde inyectarlo o usar ElementTree.
            
            xml_actualizado = xml_text.replace("</cvn>", f"\n{nuevo_nodo_xml}\n</cvn>")
            
            # --- 5. Reincrustar el XML en el PDF ---
            # Borramos el XML antiguo e incrustamos el nuevo
            doc_base.embfile_del(xml_filename)
            doc_base.embfile_add(xml_filename, xml_actualizado.encode('utf-8'), filename=xml_filename)
            
            pdf_actualizado_bytes = doc_base.write()
            
            st.download_button(
                label="Descargar CVN-PDF Actualizado",
                data=pdf_actualizado_bytes,
                file_name="CVN_Actualizado_Importable.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("Falta subir alguno de los documentos.")