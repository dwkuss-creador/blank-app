import io
import os
import json
import re
from datetime import datetime
import requests
import pandas as pd
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN GENERAL Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="Vecinos Calandrias",
    page_icon="🏡",
    layout="centered",
    initial_sidebar_state="auto"
)

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .vecino-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .btn-llamar {
        display: inline-block;
        background-color: #2b6cb0;
        color: white !important;
        padding: 6px 14px;
        border-radius: 6px;
        text-decoration: none !important;
        font-weight: 600;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# URL definitiva y directa del backend Google Apps Script
DEFAULT_API_URL = "https://script.google.com/macros/s/AKfycbxb8b9zDC6NMnEkd2vhxorM2co5ieLG0XcrVAi67OHkSZoekFTy7uRopbyFFhor8RQd/exec"
API_URL = st.secrets.get("SHEETS_API_URL", DEFAULT_API_URL)

# ==============================================================================
# CARGA Y PROCESAMIENTO BLINDADO DE DATOS (VERSIÓN 1)
# ==============================================================================
@st.cache_data(ttl=180)
def cargar_datos_backend():
    """
    Carga blindada: interpreta correctamente tanto si Google Apps Script
    devuelve la lista plana tradicional [[...], [...]] como si devuelve
    el nuevo formato {'vecinos': [...], 'telefonos': [...]}.
    """
    try:
        res = requests.get(API_URL, timeout=12)
        res.raise_for_status()
        
        texto = res.text.strip()
        if texto.startswith("<") or "<html" in texto.lower():
            st.error(
                "⚠️ **Aviso de permisos:** La URL devolvió una pantalla de Google en lugar de datos JSON. "
                "Verificá en Google Apps Script > Implementar > Administrar implementaciones que 'Quién tiene acceso' sea 'Cualquier persona'."
            )
            return []
            
        payload = res.json()
        
        # Si devuelve el diccionario nuevo
        if isinstance(payload, dict):
            return payload.get("vecinos", [])
        # Si devuelve la lista plana tradicional
        elif isinstance(payload, list):
            return payload
            
        return []
    except Exception as e:
        st.error(f"⚠️ Error al conectar con el servidor: {e}")
        return []

def procesar_vecinos(raw_data):
    """Limpia, normaliza, deduplica y ordena el padrón de vecinos."""
    if not raw_data or len(raw_data) < 2:
        return pd.DataFrame()
        
    headers = [str(c).strip().upper() for c in raw_data[0]]
    df = pd.DataFrame(raw_data[1:], columns=headers)
    
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        
    # Deduplicación: la última entrada tiene prioridad
    sub_cols = [c for c in ["MANZANA", "LOTE", "NOMBRE"] if c in df.columns]
    if sub_cols:
        df = df.drop_duplicates(subset=sub_cols, keep="last")
        
    # Ordenamiento de Manzanas y Lotes
    def parse_manzana(val):
        val_str = str(val).upper().replace("MANZANA", "").strip()
        num_match = re.search(r'\d+', val_str)
        num = int(num_match.group()) if num_match else 9999
        letra_match = re.search(r'[A-Z]', val_str)
        letra = letra_match.group() if letra_match else ""
        return (num, letra)

    def parse_lote(val):
        num_match = re.search(r'\d+', str(val))
        return int(num_match.group()) if num_match else 9999

    if "MANZANA" in df.columns and "LOTE" in df.columns:
        df["_m_key"] = df["MANZANA"].apply(parse_manzana)
        df["_l_key"] = df["LOTE"].apply(parse_lote)
        
        sort_cols = ["_m_key", "_l_key"]
        ascending = [True, True]
        
        if "ES_PRINCIPAL" in df.columns:
            df["_p_key"] = df["ES_PRINCIPAL"].str.upper().apply(lambda x: 0 if x in ["SI", "TRUE", "1"] else 1)
            sort_cols.append("_p_key")
            ascending.append(True)
            
        df = df.sort_values(by=sort_cols, ascending=ascending)
        df = df.drop(columns=[c for c in ["_m_key", "_l_key", "_p_key"] if c in df.columns])
        
    return df

# Carga de datos
raw_vecinos = cargar_datos_backend()
df_vecinos = procesar_vecinos(raw_vecinos)

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    if os.path.exists("logo_navidad.png"):
        st.image("logo_navidad.png", use_container_width=True)
    elif os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("🏡 Calandrias")
        
    st.markdown("### **Comunidad Calandrias**")
    st.caption("Padrón Vecinal Oficial - Versión 1 Blindada")
    st.write("---")
    
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Detección de Administrador
query_params = st.query_params
is_admin = query_params.get("admin", "").lower() in ["si", "true", "1"]

# ==============================================================================
# VISTA PRINCIPAL
# ==============================================================================
st.title("🏡 Padrón de Propietarios y Residentes")

if df_vecinos.empty:
    st.info("No se encontraron registros en el padrón o se está sincronizando con la base de datos.")
else:
    c1, c2 = st.columns([1, 2])
    with c1:
        manzanas_disp = ["Todas"] + sorted(list(df_vecinos["MANZANA"].unique())) if "MANZANA" in df_vecinos.columns else ["Todas"]
        sel_manzana = st.selectbox("Filtrar por Manzana:", manzanas_disp)
    with c2:
        query_busqueda = st.text_input("Buscar por Nombre o Lote:", placeholder="Ej: Perez, Lote 12...")
        
    df_mostrar = df_vecinos.copy()
    if sel_manzana != "Todas" and "MANZANA" in df_mostrar.columns:
        df_mostrar = df_mostrar[df_mostrar["MANZANA"] == sel_manzana]
        
    if query_busqueda:
        q = query_busqueda.lower().strip()
        mask = df_mostrar.apply(lambda row: row.astype(str).str.lower().str.contains(q).any(), axis=1)
        df_mostrar = df_mostrar[mask]
        
    st.caption(f"Mostrando **{len(df_mostrar)}** registros.")
    
    for _, row in df_mostrar.iterrows():
        mza = row.get("MANZANA", "-")
        lote = row.get("LOTE", "-")
        nombre = row.get("NOMBRE", "Sin Nombre")
        tel = row.get("TELEFONO", "")
        email = row.get("EMAIL", "")
        
        tel_html = f'📞 <a href="tel:{tel}" style="color: #2b6cb0; text-decoration: none;"><b>{tel}</b></a><br>' if tel and tel != '-' else ''
        email_html = f'✉️ <a href="mailto:{email}" style="color: #4a5568; text-decoration: none;">{email}</a>' if email and email != '-' else ''
        
        with st.container():
            st.markdown(f"""
            <div class="vecino-card">
                <strong style="font-size: 1.05rem;">{nombre}</strong><br>
                <span style="color: #4a5568;">📍 <b>Manzana:</b> {mza} | <b>Lote:</b> {lote}</span><br>
                {tel_html}
                {email_html}
            </div>
            """, unsafe_allow_html=True)

# Panel Administrativo para agregar filas si entra con ?admin=si
if is_admin:
    st.write("---")
    st.subheader("⚙️ Panel de Carga Rápida (Administrador)")
    with st.form("form_alta_vecino", clear_on_submit=True):
        f_mza = st.text_input("Manzana:")
        f_lote = st.text_input("Lote:")
        f_nombre = st.text_input("Nombre y Apellido:")
        f_tel = st.text_input("Teléfono:")
        f_email = st.text_input("Email:")
        f_princ = st.selectbox("¿Es Contacto Principal?", ["SI", "NO"])
        
        btn_enviar = st.form_submit_button("Guardar Vecino")
        if btn_enviar:
            if not f_mza or not f_lote or not f_nombre:
                st.warning("Completá Manzana, Lote y Nombre.")
            else:
                nueva_fila = [f_mza, f_lote, f_nombre, f_tel, f_email, f_princ]
                payload_post = {
                    "action": "append",
                    "rows": [nueva_fila]
                }
                try:
                    r = requests.post(API_URL, json=payload_post, timeout=10)
                    if r.status_code == 200:
                        st.success("Vecino agregado correctamente.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {r.text}")
                except Exception as ex:
                    st.error(f"Error de conexión: {ex}")
