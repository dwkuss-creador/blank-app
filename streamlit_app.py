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

# Estilos CSS personalizados (Mobile-First y Tarjetas de Teléfonos)
st.markdown("""
<style>
    /* Estilos generales */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Tarjeta de Emergencias - Ancho completo y destaque */
    .card-emergencias {
        background-color: #fff5f5;
        border: 2px solid #e53e3e;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px rgba(229, 62, 62, 0.1);
    }
    .card-emergencias h3 {
        color: #c53030 !important;
        margin-top: 0;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Filas de contactos y botones táctiles directos */
    .contacto-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid #edf2f7;
    }
    .contacto-row:last-child {
        border-bottom: none;
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
    .btn-llamar-emergencia {
        background-color: #e53e3e !important;
    }
    
    /* Tarjetas de vecinos */
    .vecino-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

# URL del backend Google Apps Script (desde st.secrets o fallback)
DEFAULT_API_URL = "https://script.google.com/macros/s/AKfycbyfD0jK3Pvhc05w6eQWzH5g4f6yD8u7i5o_example/exec"
API_URL = st.secrets.get("SHEETS_API_URL", DEFAULT_API_URL)

# ==============================================================================
# CARGA Y PROCESAMIENTO INTELIGENTE DE DATOS
# ==============================================================================
@st.cache_data(ttl=180)
def cargar_datos_backend():
    """
    Obtiene los datos desde Google Apps Script.
    Maneja tanto la respuesta combinada {vecinos: [...], telefonos: [...]}
    como la respuesta plana tradicional [[...], [...]] para garantizar compatibilidad.
    """
    try:
        res = requests.get(API_URL, timeout=12)
        res.raise_for_status()
        
        texto_respuesta = res.text.strip()
        # Verificación para detectar si Google devolvió pantalla HTML de login por falta de permisos públicos
        if texto_respuesta.startswith("<") or "<html" in texto_respuesta.lower():
            st.error(
                "⚠️ **Error de acceso en Google Apps Script:** La URL devolvió una página de Google en vez de datos JSON. "
                "Para solucionarlo: En Apps Script hacé clic en **Implementar > Administrar implementaciones**, "
                "editá la versión activa y verificá que **Quién tiene acceso** esté configurado en **Cualquier persona** (Anyone)."
            )
            return [], []
            
        payload = res.json()
        raw_vecinos = []
        raw_telefonos = []
        
        # 1. Si es un diccionario con la nueva estructura combinada
        if isinstance(payload, dict):
            raw_vecinos = payload.get("vecinos", [])
            raw_telefonos = payload.get("telefonos", [])
        # 2. Si es una lista directa tradicional
        elif isinstance(payload, list):
            raw_vecinos = payload
            raw_telefonos = []
            
        return raw_vecinos, raw_telefonos
    except json.JSONDecodeError:
        st.error(
            "⚠️ Error al interpretar los datos recibidos (no es JSON válido). "
            "Asegurate de que la Web App en Google Apps Script tenga acceso público ('Cualquier persona')."
        )
        return [], []
    except Exception as e:
        st.error(f"⚠️ Error al conectar con el servidor: {e}")
        return [], []

def procesar_vecinos(raw_vecinos):
    """Limpia, normaliza y ordena el padrón de vecinos."""
    if not raw_vecinos or len(raw_vecinos) < 2:
        return pd.DataFrame()
        
    headers = [str(c).strip().upper() for c in raw_vecinos[0]]
    df = pd.DataFrame(raw_vecinos[1:], columns=headers)
    
    # Normalizar columnas necesarias
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        
    # Deduplicación: última entrada ingresada tiene prioridad
    sub_cols = [c for c in ["MANZANA", "LOTE", "NOMBRE"] if c in df.columns]
    if sub_cols:
        df = df.drop_duplicates(subset=sub_cols, keep="last")
        
    # Ordenamiento personalizado (Manzana 15 A, 15 B... Lote ascendente)
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

def procesar_telefonos(raw_telefonos):
    """Limpia y estructura la solapa Directorio_Telefonos."""
    if not raw_telefonos or len(raw_telefonos) < 2:
        return pd.DataFrame(columns=["ID", "TARJETA", "CATEGORIA", "NOMBRE", "TELEFONO", "ACTIVO"])
        
    headers = [str(c).strip().upper() for c in raw_telefonos[0]]
    df = pd.DataFrame(raw_telefonos[1:], columns=headers)
    
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        
    # Filtrar solo contactos activos
    if "ACTIVO" in df.columns:
        df = df[df["ACTIVO"].str.upper() != "NO"]
        
    return df

# Cargar datos
raw_vecinos, raw_telefonos = cargar_datos_backend()
df_vecinos = procesar_vecinos(raw_vecinos)
df_telefonos = procesar_telefonos(raw_telefonos)

# ==============================================================================
# SIDEBAR: LOGO, INFO Y HERRAMIENTAS
# ==============================================================================
with st.sidebar:
    # Logo Navideño Veraniego en Diciembre o Logo estándar
    es_diciembre = (datetime.now().month == 12)
    if es_diciembre and os.path.exists("logo_navidad.png"):
        st.image("logo_navidad.png", use_container_width=True)
    elif os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("🏡 Calandrias")
        
    st.markdown("### **Comunidad Calandrias**")
    st.caption("Plataforma vecinal oficial - Versión 2.0")
    st.write("---")
    
    # Botón para refrescar datos en vivo
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Detección de modo Administrador mediante ?admin=si
query_params = st.query_params
is_admin = query_params.get("admin", "").lower() in ["si", "true", "1"]

# ==============================================================================
# VISTA PRINCIPAL POR PESTAÑAS
# ==============================================================================
tabs = ["🔍 Padrón de Vecinos", "ℹ️ Datos Útiles"]
if is_admin:
    tabs.append("⚙️ Gestión Admin")

tab_vecinos, tab_utiles, *tab_admin_list = st.tabs(tabs)

# ------------------------------------------------------------------------------
# 1. PESTAÑA: PADRÓN DE VECINOS
# ------------------------------------------------------------------------------
with tab_vecinos:
    st.subheader("Padrón de Propietarios y Residentes")
    
    if df_vecinos.empty:
        st.info("No se encontraron registros en el padrón de vecinos o no se pudo cargar la base.")
    else:
        # Buscador y filtros rápidos
        c1, c2 = st.columns([1, 2])
        with c1:
            manzanas_disponibles = ["Todas"] + sorted(list(df_vecinos["MANZANA"].unique())) if "MANZANA" in df_vecinos.columns else ["Todas"]
            sel_manzana = st.selectbox("Filtrar por Manzana:", manzanas_disponibles)
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
        
        # Presentación en tarjetas legibles
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

# ------------------------------------------------------------------------------
# 2. PESTAÑA: DATOS ÚTILES (EMERGENCIAS Y TELÉFONOS ÚTILES)
# ------------------------------------------------------------------------------
with tab_utiles:
    # ----------------------------------------------------
    # TARJETA 1: TELÉFONOS DE EMERGENCIAS (BANNER COMPLETO)
    # ----------------------------------------------------
    st.markdown('<div class="card-emergencias">', unsafe_allow_html=True)
    st.markdown("<h3>🚨 TELÉFONOS DE EMERGENCIAS</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color: #742a2a; margin-bottom: 12px; font-size: 0.95rem;'>Contactos prioritarios y asistencia inmediata las 24 horas.</p>", unsafe_allow_html=True)
    
    df_emergencias = pd.DataFrame()
    if not df_telefonos.empty and "TARJETA" in df_telefonos.columns:
        df_emergencias = df_telefonos[df_telefonos["TARJETA"].str.upper() == "EMERGENCIAS"]
        
    if not df_emergencias.empty:
        for _, row in df_emergencias.iterrows():
            nombre_em = row.get("NOMBRE", "Emergencia")
            tel_em = row.get("TELEFONO", "")
            tel_clean = re.sub(r'[^0-9+]', '', tel_em)
            st.markdown(f"""
            <div class="contacto-row">
                <span style="font-weight: 600; color: #2d3748; font-size: 1rem;">{nombre_em}</span>
                <a href="tel:{tel_clean}" class="btn-llamar btn-llamar-emergencia">📞 Llamar {tel_em}</a>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No se han cargado teléfonos de emergencia en la solapa Directorio_Telefonos.")
        
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ----------------------------------------------------
    # TARJETA 2: TELÉFONOS ÚTILES (4 RENGLONES COLAPSADOS)
    # ----------------------------------------------------
    st.markdown("### 📞 Teléfonos Útiles y Servicios")
    st.write("Seleccioná la categoría correspondiente para ver los números de contacto:")
    
    categorias_fijas = [
        ("DELIVERYS", "🛵 Deliverys y Gastronomía"),
        ("REMISES Y TRASLADOS", "🚕 Remises y Traslados"),
        ("SERVICIOS DE OBRA", "🔨 Servicios de Obra y Mantenimiento"),
        ("VARIOS", "📦 Varios y Profesionales")
    ]
    
    df_utiles = pd.DataFrame()
    if not df_telefonos.empty and "TARJETA" in df_telefonos.columns:
        df_utiles = df_telefonos[df_telefonos["TARJETA"].str.upper() == "UTILES"]
        
    for cat_clave, cat_titulo in categorias_fijas:
        with st.expander(cat_titulo, expanded=False):
            df_cat = pd.DataFrame()
            if not df_utiles.empty and "CATEGORIA" in df_utiles.columns:
                df_cat = df_utiles[df_utiles["CATEGORIA"].str.upper() == cat_clave]
                
            if not df_cat.empty:
                for _, r in df_cat.iterrows():
                    nom = r.get("NOMBRE", "Servicio")
                    num = r.get("TELEFONO", "")
                    num_clean = re.sub(r'[^0-9+]', '', num)
                    st.markdown(f"""
                    <div class="contacto-row">
                        <div>
                            <span style="font-weight: 600; color: #2d3748;">{nom}</span><br>
                            <span style="color: #718096; font-size: 0.9rem;">{num}</span>
                        </div>
                        <a href="tel:{num_clean}" class="btn-llamar">📞 Llamar</a>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption(f"No hay contactos registrados actualmente en {cat_titulo}.")

# ------------------------------------------------------------------------------
# 3. PESTAÑA: ADMINISTRACIÓN (SOLO CON ?admin=si)
# ------------------------------------------------------------------------------
if is_admin and tab_admin_list:
    tab_admin = tab_admin_list[0]
    with tab_admin:
        st.subheader("⚙️ Panel de Administración de Contactos")
        st.info("Este panel solo es visible porque ingresaste con `?admin=si`.")
        
        # Subir nuevo contacto a Directorio_Telefonos
        st.markdown("#### ➕ Agregar Nuevo Teléfono")
        with st.form("form_alta_telefono", clear_on_submit=True):
            tipo_tarjeta = st.selectbox("Tarjeta Destino:", ["UTILES", "EMERGENCIAS"])
            categoria = st.selectbox("Categoría:", ["DELIVERYS", "REMISES Y TRASLADOS", "SERVICIOS DE OBRA", "VARIOS", "EMERGENCIAS"])
            nombre_contacto = st.text_input("Nombre o Comercio:")
            telefono_contacto = st.text_input("Teléfono (incluir código de área):")
            
            btn_guardar = st.form_submit_button("Guardar en Google Sheets")
            if btn_guardar:
                if not nombre_contacto or not telefono_contacto:
                    st.warning("Completá el nombre y el teléfono antes de guardar.")
                else:
                    nuevo_id = f"TEL_{int(datetime.now().timestamp())}"
                    payload_post = {
                        "action": "add_phone",
                        "data": {
                            "ID": nuevo_id,
                            "TARJETA": tipo_tarjeta,
                            "CATEGORIA": categoria,
                            "NOMBRE": nombre_contacto,
                            "TELEFONO": telefono_contacto,
                            "ACTIVO": "SI"
                        }
                    }
                    try:
                        res = requests.post(API_URL, json=payload_post, timeout=10)
                        if res.status_code == 200:
                            st.success(f"Contacto '{nombre_contacto}' registrado con éxito.")
                            st.cache_data.clear()
                        else:
                            st.error(f"Error al enviar datos: {res.text}")
                    except Exception as err:
                        st.error(f"Error de conexión: {err}")
                        
        st.write("---")
        
        # Desactivación lógica de contacto
        st.markdown("#### 🗑️ Desactivar Contacto Existente")
        if not df_telefonos.empty and "ID" in df_telefonos.columns and "NOMBRE" in df_telefonos.columns:
            opciones_baja = {f"{r['NOMBRE']} ({r.get('CATEGORIA', '-')})": r['ID'] for _, r in df_telefonos.iterrows()}
            contacto_a_borrar = st.selectbox("Seleccionar contacto a desactivar:", list(opciones_baja.keys()))
            
            if st.button("Desactivar Contacto", type="primary"):
                id_seleccionado = opciones_baja[contacto_a_borrar]
                payload_baja = {
                    "action": "deactivate_phone",
                    "id": id_seleccionado
                }
                try:
                    res = requests.post(API_URL, json=payload_baja, timeout=10)
                    if res.status_code == 200:
                        st.success("Contacto desactivado correctamente en Google Sheets.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Error al desactivar: {res.text}")
                except Exception as err:
                    st.error(f"Error de conexión: {err}")
        else:
            st.caption("No hay contactos disponibles para desactivar.")
