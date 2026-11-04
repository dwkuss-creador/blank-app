
import io
import json
import os
import re
from fpdf import FPDF
import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ---------------------------------------------------------
st.set_page_config(
    page_title="APP VECINOS CALANDRIAS",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed",  # 📱 Menú colapsado en móviles
)

# Carpeta física persistente para la galería
CARPETA_GALERIA = "galeria_fotos"
os.makedirs(CARPETA_GALERIA, exist_ok=True)

# Estilos CSS: Bloqueo de oscurecimiento + Adaptabilidad móvil + Forzado modo claro en inputs/selectores
st.markdown(
    """
<style>
    /* EVITAR OSCURECIMIENTO / DESENFOQUE AL RECARGAR O PENSAR */
    [data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
    }
    div[data-testid="stAppViewBlockContainer"] {
        opacity: 1 !important;
    }
    .element-container, .stMarkdown, .stDataFrame, .stTextInput, .stButton {
        opacity: 1 !important;
    }
    /* Tipografía y encabezados */
    .main-header {
        font-size: 1.85rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #4B5563;
        font-size: 1rem;
        margin-bottom: 1rem;
    }

    /* Tarjeta destacada de Alarma */
    .alarma-card {
        background-color: #EFF6FF;
        padding: 14px 16px;
        border-radius: 10px;
        border: 2px solid #3B82F6;
        border-left: 8px solid #1D4ED8;
        margin-bottom: 12px;
    }

    /* Opciones del menú lateral más grandes */
    [data-testid="stSidebar"] .stRadio label {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
        cursor: pointer;
    }

    /* Campo de entrada de texto (Apellido, Nombre, Celular, etc.) */
    div[data-testid="stTextInput"] input {
        border: 2px solid #2563EB !important;
        background-color: #F8FAFC !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        border-radius: 8px !important;
    }

    /* SELECTORES (Manzana, Sector A/B, Lote) - Forzado total sobre BaseWeb */
    div[data-testid="stSelectbox"] [data-baseweb="select"],
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
    div[data-testid="stSelectbox"] [data-baseweb="select"] div {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        border: 2px solid #2563EB !important;
        border-radius: 8px !important;
        min-height: 44px !important;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] * {
        color: #0F172A !important;
        font-weight: 600 !important;
    }
    div[data-testid="stSelectbox"] svg {
        fill: #0F172A !important;
    }

    /* Menú desplegable flotante al hacer clic */
    div[data-baseweb="popover"],
    ul[data-baseweb="menu"],
    li[data-baseweb="menu-item"] {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
    }
    li[data-baseweb="menu-item"] * {
        color: #0F172A !important;
    }

    /* Botones táctiles */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }

    @media (max-width: 768px) {
        .main-header { font-size: 1.5rem !important; }
        .sub-header { font-size: 0.92rem !important; }
        .stButton>button {
            padding-top: 10px !important;
            padding-bottom: 10px !important;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)

COLUMNAS_BD = [
    "MANZANA",
    "SECTOR",
    "LOTE",
    "TIPO_CONTACTO",
    "APELLIDO",
    "NOMBRE",
    "CELULAR",
    "ALARMA_1",
    "ALARMA_2",
    "ALARMA_3",
    "ALARMA_4",
]

# ---------------------------------------------------------
# CONEXIÓN DIRECTA CON CACHÉ Y TIMEOUT AMPLIADO
# ---------------------------------------------------------
def get_api_url():
    url = st.secrets.get("SHEETS_API_URL", "")
    if not url:
        url = "https://script.google.com/macros/s/AKfycbxb8b9zDC6NMnEkd2vhxorM2co5ieLG0XcrVAi67OHkSZoekFTy7uRopbyFFhor8RQd/exec"
    return url

def normalizar_valor(val):
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2].strip()
    return s

def ordenar_padron(df):
    """Ordena estrictamente: Manzana 15 A, 15 B, 16 A, 16 B... por Lote y Contacto Principal primero."""
    if df.empty:
        return df
    df_ord = df.copy()
    df_ord["_mz_num"] = pd.to_numeric(df_ord["MANZANA"], errors="coerce").fillna(999)
    df_ord["_sec_str"] = df_ord["SECTOR"].astype(str).str.upper()
    df_ord["_lot_num"] = pd.to_numeric(df_ord["LOTE"], errors="coerce").fillna(999)
    # Contacto Principal (1) siempre antes que Secundario (2)
    df_ord["_tipo_prioridad"] = df_ord["TIPO_CONTACTO"].apply(
        lambda x: 1 if "PRINCIPAL" in str(x).upper() else 2
    )
    df_ord = df_ord.sort_values(
        by=["_mz_num", "_sec_str", "_lot_num", "_tipo_prioridad"],
        ascending=[True, True, True, True]
    )
    df_ord = df_ord.drop(columns=["_mz_num", "_sec_str", "_lot_num", "_tipo_prioridad"])
    return df_ord

@st.cache_data(ttl=60, show_spinner=False)
def obtener_datos_remotos(api_url):
    if not api_url:
        return None
    try:
        resp = requests.get(api_url, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None

def cargar_datos():
    api_url = get_api_url()
    data = obtener_datos_remotos(api_url)

    vecinos_raw = []
    telefonos_raw = []

    if isinstance(data, dict):
        vecinos_raw = data.get("vecinos", [])
        telefonos_raw = data.get("telefonos", [])
    elif isinstance(data, list):
        vecinos_raw = data

    # 1. Procesamiento padrón de vecinos
    df_v = pd.DataFrame(columns=COLUMNAS_BD)
    if vecinos_raw and len(vecinos_raw) > 1:
        headers = [str(h).strip().upper() for h in vecinos_raw[0]]
        df_v = pd.DataFrame(vecinos_raw[1:], columns=headers)
        for col in COLUMNAS_BD:
            if col not in df_v.columns:
                df_v[col] = ""
        df_v = df_v[COLUMNAS_BD]
        for col in COLUMNAS_BD:
            df_v[col] = df_v[col].apply(normalizar_valor)
        df_v = df_v.drop_duplicates(
            subset=["MANZANA", "SECTOR", "LOTE", "TIPO_CONTACTO"], keep="last"
        )
        df_v = ordenar_padron(df_v).fillna("")
    elif "db_local" in st.session_state:
        df_v = st.session_state.db_local

    st.session_state.db_local = df_v

    # 2. Procesamiento directorio de teléfonos (Hoja DIRECTORIO_TELEFONOS)
    df_t = pd.DataFrame()
    if telefonos_raw and len(telefonos_raw) > 1:
        headers_t = [str(h).strip().upper() for h in telefonos_raw[0]]
        df_t = pd.DataFrame(telefonos_raw[1:], columns=headers_t)
        for col in df_t.columns:
            df_t[col] = df_t[col].apply(normalizar_valor)

    return df_v, df_t

def agregar_filas_sheets(nuevas_filas_dicts):
    api_url = get_api_url()
    if not api_url:
        return False, "No está configurada la URL de Sheets en Secrets."
    filas_para_enviar = []
    for f in nuevas_filas_dicts:
        fila = [normalizar_valor(f.get(col, "")) for col in COLUMNAS_BD]
        filas_para_enviar.append(fila)
    payload = {"action": "append", "rows": filas_para_enviar}
    try:
        resp = requests.post(api_url, json=payload, timeout=30)
        if resp.status_code == 200:
            texto = resp.text.strip()
            if texto.startswith("<") or "<html" in texto.lower():
                return False, "Google Apps Script devolvió HTML. Verificá que 'Quién tiene acceso' sea 'Cualquier persona'."
            try:
                res_data = resp.json()
                if isinstance(res_data, dict) and res_data.get("status") == "error":
                    return False, f"Rechazado por Apps Script: {res_data.get('message', 'Acción no permitida')}"
            except Exception:
                pass
            st.cache_data.clear()
            return True, "Guardado exitoso."
        return False, f"Error HTTP {resp.status_code} desde Google Script."
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

# ---------------------------------------------------------
# VALIDACIÓN Y NORMALIZACIÓN DE CELULAR
# ---------------------------------------------------------
def validar_celular(celular):
    cel = str(celular).strip()
    cel_limpio = "".join(c for c in cel if c.isdigit())
    if not cel_limpio:
        return False, "El celular no puede estar vacío.", ""
    if len(cel_limpio) < 8 or len(cel_limpio) > 15:
        return False, "El celular debe contener entre 8 y 15 dígitos numéricos.", ""
    return True, "", cel_limpio

# ---------------------------------------------------------
# EXPORTACIÓN
# ---------------------------------------------------------
def exportar_excel(df):
    df_salida = ordenar_padron(df)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_salida.to_excel(writer, index=False, sheet_name="Vecinos")
    return output.getvalue()

def exportar_pdf(df, titulo="Reporte Vecinos - Calandrias"):
    df_salida = ordenar_padron(df)
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(4)
    headers = [
        "Mz",
        "Sec",
        "Lote",
        "Tipo",
        "Apellido",
        "Nombre",
        "Celular",
        "Alarma 1",
        "Alarma 2",
        "Alarma 3",
        "Alarma 4",
    ]
    col_widths = [12, 12, 12, 22, 35, 35, 28, 26, 26, 26, 26]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(220, 230, 242)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 7)
    for _, row in df_salida.iterrows():
        vals = [
            str(row.get("MANZANA", "")),
            str(row.get("SECTOR", "")),
            str(row.get("LOTE", "")),
            str(row.get("TIPO_CONTACTO", "")),
            str(row.get("APELLIDO", ""))[:22],
            str(row.get("NOMBRE", ""))[:22],
            str(row.get("CELULAR", "")),
            str(row.get("ALARMA_1", "")),
            str(row.get("ALARMA_2", "")),
            str(row.get("ALARMA_3", "")),
            str(row.get("ALARMA_4", "")),
        ]
        for i, val in enumerate(vals):
            pdf.cell(col_widths[i], 6, val, border=1, align="C")
        pdf.ln()
    return bytes(pdf.output())

# ---------------------------------------------------------
# ESTADO DE NAVEGACIÓN Y VARIABLES
# ---------------------------------------------------------
OPCIONES_MENU = [
    "🔍 Consultas",
    "ℹ️ Datos Útiles",
    "🖼️ Galería e Imágenes",
    "📝 Alta de Vecino",
]

params = st.query_params
es_admin = params.get("admin") == "si"

if "pagina_actual" not in st.session_state:
    st.session_state.pagina_actual = "🔍 Consultas"
if "precarga" not in st.session_state:
    st.session_state.precarga = None
if "mostrar_dialogo_otro_lote" not in st.session_state:
    st.session_state.mostrar_dialogo_otro_lote = False
if "filtro_alarma_activo" not in st.session_state:
    st.session_state.filtro_alarma_activo = ""

# ---------------------------------------------------------
# BARRA LATERAL (SIDEBAR) CON IMAGEN PERSISTENTE EN DISCO
# ---------------------------------------------------------
with st.sidebar:
    logo_encontrado = None
    for candidato in ["logo_navidad.png", "logo.png", "logo.jpg", "logo.jpeg", "calandrias.png", "calandrias.jpg"]:
        if os.path.exists(candidato):
            logo_encontrado = candidato
            break
    if logo_encontrado:
        st.image(logo_encontrado, use_container_width=True)
    else:
        st.image("https://img.icons8.com/fluency/96/neighborhood.png", width=70)
    st.title("CALANDRIAS")
    st.caption("Padrón Vecinal y Alarmas")

    indice_menu = 0
    if st.session_state.pagina_actual in OPCIONES_MENU:
        indice_menu = OPCIONES_MENU.index(st.session_state.pagina_actual)
    pagina = st.radio(
        "Secciones:",
        OPCIONES_MENU,
        index=indice_menu,
    )
    if pagina != st.session_state.pagina_actual:
        st.session_state.pagina_actual = pagina
        st.rerun()
    st.markdown("---")
    if get_api_url():
        st.success("🟢 Google Sheets Conectado")
    else:
        st.info("🟡 Modo de prueba")

# Carga de datos unificada
df_base, df_telefonos = cargar_datos()

# =========================================================
# SECCIÓN 1: CONSULTAS
# =========================================================
if st.session_state.pagina_actual == "🔍 Consultas":
    st.markdown(
        '<div class="main-header">🔍 Consulta de Vecinos</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Búsqueda rápida por Alarma o Ubicación.</div>',
        unsafe_allow_html=True,
    )
    # Tarjeta de Alarma
    st.markdown(
        """
    <div class="alarma-card">
        <h4 style="margin: 0; color: #1E40AF; font-size: 1.15rem;">🚨 Búsqueda Prioritaria por Número de Alarma</h4>
        <p style="margin: 4px 0 0 0; color: #374151; font-size: 0.94rem;">
            Ingrese el número de alarma disparada para ubicar inmediatamente al vecino correspondiente.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )
    with st.form(key="form_busqueda_alarma", clear_on_submit=True):
        c_input, c_btn = st.columns([5, 1.2])
        with c_input:
            alarma_escrita = st.text_input(
                "box_alarma",
                placeholder="Escribe el número de alarma y presiona Enter o Buscar...",
                label_visibility="collapsed",
            ).strip()
        with c_btn:
            buscar_disparado = st.form_submit_button(
                "🔍 Buscar", type="primary", use_container_width=True
            )
        if buscar_disparado:
            st.session_state.filtro_alarma_activo = normalizar_valor(alarma_escrita)
            st.rerun()

    alarma_activa = st.session_state.filtro_alarma_activo
    if alarma_activa:
        st.markdown(f"### Vecino de la Alarma Nº {alarma_activa}")
        df_alarma = df_base.copy()
        lotes_con_alarma = df_alarma[
            (df_alarma["ALARMA_1"] == alarma_activa)
            | (df_alarma["ALARMA_2"] == alarma_activa)
            | (df_alarma["ALARMA_3"] == alarma_activa)
            | (df_alarma["ALARMA_4"] == alarma_activa)
        ]
        if not lotes_con_alarma.empty:
            filtro_lotes = pd.Series(False, index=df_alarma.index)
            for _, fila_lote in lotes_con_alarma.iterrows():
                mz = fila_lote["MANZANA"]
                sec = fila_lote["SECTOR"]
                lt = fila_lote["LOTE"]
                filtro_lotes |= (
                    (df_alarma["MANZANA"] == mz)
                    & (df_alarma["SECTOR"] == sec)
                    & (df_alarma["LOTE"] == lt)
                )
            df_alarma_resultado = ordenar_padron(df_alarma[filtro_lotes])
            st.dataframe(df_alarma_resultado, use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos para esa seleccion")

    # SECCIÓN DE UBICACIÓN
    st.markdown("---")
    st.markdown("#### 📍 Buscar por Ubicación:")
    col_tipo, col_filtros = st.columns([1.5, 3])
    with col_tipo:
        tipo_ubicacion = st.radio(
            "Seleccione Criterio de visualización:",
            ["Mostrar Todos", "Por Manzana", "Por Lote Específico"],
            index=0,
        )
    df_resultado = df_base.copy()
    criterio_activo = ""
    with col_filtros:
        if tipo_ubicacion == "Por Manzana":
            cm, cs = st.columns(2)
            with cm:
                m_sel = st.selectbox(
                    "Manzana:", [str(i) for i in range(15, 26)], key="c_mz"
                )
            with cs:
                s_sel = st.selectbox("Sector (A/B):", ["A", "B"], key="c_sec")
            criterio_activo = f"Manzana {m_sel} Sector {s_sel}"
            df_resultado = df_resultado[
                (df_resultado["MANZANA"] == str(m_sel))
                & (df_resultado["SECTOR"] == str(s_sel))
            ]
        elif tipo_ubicacion == "Por Lote Específico":
            cm, cs, cl = st.columns(3)
            with cm:
                m_sel = st.selectbox(
                    "Manzana:", [str(i) for i in range(15, 26)], key="l_mz"
                )
            with cs:
                s_sel = st.selectbox("Sector:", ["A", "B"], key="l_sec")
            with cl:
                l_sel = st.selectbox(
                    "Lote:", [str(i) for i in range(1, 25)], key="l_lot"
                )
            criterio_activo = f"Manzana {m_sel}{s_sel} - Lote {l_sel}"
            df_resultado = df_resultado[
                (df_resultado["MANZANA"] == str(m_sel))
                & (df_resultado["SECTOR"] == str(s_sel))
                & (df_resultado["LOTE"] == str(l_sel))
            ]
        else:
            criterio_activo = "Base Completa"

    df_resultado = ordenar_padron(df_resultado)

    st.markdown("---")
    st.markdown(f"### Resultados ({criterio_activo})")
    if not df_resultado.empty:
        st.dataframe(df_resultado, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos para esa seleccion")

    st.markdown("---")
    st.markdown("### 📥 Descargar Reportes")
    d_row1_col1, d_row1_col2 = st.columns(2)
    with d_row1_col1:
        st.download_button(
            label="📊 Consulta (Excel)",
            data=exportar_excel(df_resultado),
            file_name="consulta_vecinos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d_row1_col2:
        st.download_button(
            label="📄 Consulta (PDF)",
            data=exportar_pdf(
                df_resultado, f"Consulta Vecinos Calandrias - {criterio_activo}"
            ),
            file_name="consulta_vecinos.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    d_row2_col1, d_row2_col2 = st.columns(2)
    with d_row2_col1:
        st.download_button(
            label="💾 Padrón Completo (Excel)",
            data=exportar_excel(df_base),
            file_name="padron_completo_calandrias.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d_row2_col2:
        st.download_button(
            label="📑 Padrón Completo (PDF)",
            data=exportar_pdf(
                df_base, "Padrón General de Vecinos y Alarmas - Calandrias"
            ),
            file_name="padron_completo_calandrias.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

# =========================================================
# SECCIÓN 2: DATOS ÚTILES
# =========================================================
elif st.session_state.pagina_actual == "ℹ️ Datos Útiles":
    st.markdown(
        '<div class="main-header">ℹ️ Directorio y Datos Útiles</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Información de contacto, emergencias y servicios del barrio.</div>',
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # 1. TELÉFONOS DE EMERGENCIA
    # ---------------------------------------------------------
    st.markdown("### 🚨 Teléfonos de Emergencia")

    df_emergencias = pd.DataFrame()
    if not df_telefonos.empty and "TARJETA" in df_telefonos.columns:
        filtro_tarjeta = df_telefonos["TARJETA"].str.upper().str.contains("EMERGENCIA")
        if "ACTIVO" in df_telefonos.columns:
            filtro_activo = df_telefonos["ACTIVO"].str.upper() != "NO"
            df_emergencias = df_telefonos[filtro_tarjeta & filtro_activo]
        else:
            df_emergencias = df_telefonos[filtro_tarjeta]

    if not df_emergencias.empty:
        filas_html_list = []
        total_filas = len(df_emergencias)
        for idx, (_, row_tel) in enumerate(df_emergencias.iterrows()):
            nombre_tel = row_tel.get("NOMBRE", "Sin Nombre")
            numero_tel = row_tel.get("TELEFONO", "")
            num_clean = "".join(c for c in str(numero_tel) if c.isdigit() or c == '+')
            border_bottom = "border-bottom: 1px solid #E2E8F0;" if idx < total_filas - 1 else ""

            fila_item = (
                f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; {border_bottom} gap: 12px; flex-wrap: wrap;">'
                f'<span style="font-size: 1.05rem; font-weight: 600; color: #1E293B;">{nombre_tel}</span>'
                f'<a href="tel:{num_clean}" style="font-size: 1.1rem; font-weight: 700; color: #1D4ED8; text-decoration: none;">📞 {numero_tel}</a>'
                f'</div>'
            )
            filas_html_list.append(fila_item)

        contenido_card = "".join(filas_html_list)
        tarjeta_completa = (
            '<div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 28px;">'
            + contenido_card
            + '</div>'
        )
        st.markdown(tarjeta_completa, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Sincronizando teléfonos de emergencia desde la hoja 'DIRECTORIO_TELEFONOS'...")

    # ---------------------------------------------------------
    # 2. TELÉFONOS ÚTILES (ORGANIZADOS POR CATEGORÍA ALFABÉTICA)
    # ---------------------------------------------------------
    st.markdown("### 📞 Teléfonos Útiles")

    df_utiles = pd.DataFrame()
    if not df_telefonos.empty and "TARJETA" in df_telefonos.columns:
        filtro_tarjeta_u = df_telefonos["TARJETA"].str.upper().str.contains("UTILES")
        if "ACTIVO" in df_telefonos.columns:
            filtro_activo_u = df_telefonos["ACTIVO"].str.upper() != "NO"
            df_utiles = df_telefonos[filtro_tarjeta_u & filtro_activo_u]
        else:
            df_utiles = df_telefonos[filtro_tarjeta_u]

    if not df_utiles.empty and "CATEGORIA" in df_utiles.columns:
        # Categorías únicas en orden alfabético
        categorias = sorted([c for c in df_utiles["CATEGORIA"].dropna().unique() if str(c).strip() != ""])

        for cat in categorias:
            df_cat = df_utiles[df_utiles["CATEGORIA"] == cat].copy()
            # Orden alfabético por Nombre dentro de la categoría
            if "NOMBRE" in df_cat.columns:
                df_cat = df_cat.sort_values(by="NOMBRE", key=lambda col: col.str.lower())

            with st.expander(f"📁 {cat.upper()}", expanded=False):
                filas_cat_list = []
                total_cat = len(df_cat)
                for idx_c, (_, row_u) in enumerate(df_cat.iterrows()):
                    nom_u = row_u.get("NOMBRE", "Sin Nombre")
                    tel_u = row_u.get("TELEFONO", "")
                    num_clean_u = "".join(c for c in str(tel_u) if c.isdigit() or c == '+')
                    border_b = "border-bottom: 1px solid #E2E8F0;" if idx_c < total_cat - 1 else ""

                    fila_u_html = (
                        f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; {border_b} gap: 12px; flex-wrap: wrap;">'
                        f'<span style="font-size: 1rem; font-weight: 600; color: #1E293B;">{nom_u}</span>'
                        f'<a href="tel:{num_clean_u}" style="font-size: 1.05rem; font-weight: 700; color: #1D4ED8; text-decoration: none;">📞 {tel_u}</a>'
                        f'</div>'
                    )
                    filas_cat_list.append(fila_u_html)

                card_cat_html = (
                    '<div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; margin: 4px 0;">'
                    + "".join(filas_cat_list)
                    + '</div>'
                )
                st.markdown(card_cat_html, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Sincronizando teléfonos útiles desde la hoja 'DIRECTORIO_TELEFONOS'...")

# =========================================================
# SECCIÓN 3: GALERÍA E IMÁGENES
# =========================================================
elif st.session_state.pagina_actual == "🖼️ Galería e Imágenes":
    st.markdown(
        '<div class="main-header">🖼️ Galería y Comunicados</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Planos del barrio, avisos importantes y fotografías.</div>',
        unsafe_allow_html=True,
    )
    if es_admin:
        st.markdown(
            """
        <div style="background-color: #F0FDF4; padding: 14px 18px; border-radius: 10px; border: 2px solid #22C55E; margin-bottom: 18px;">
            <h4 style="margin: 0; color: #15803D;">👨‍💻 Panel de Administración (Solo Visible para Ti)</h4>
            <p style="margin: 4px 0 10px 0; color: #374151; font-size: 0.94rem;">
                Publica comunicados en la galería o guarda la foto del menú lateral arriba de CALANDRIAS.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            st.markdown("##### 📤 Subir Imagen a la Galería")
            archivo_galeria = st.file_uploader(
                "Selecciona plano o comunicado (JPG/PNG):",
                type=["png", "jpg", "jpeg"],
                key="up_galeria_box",
            )
            if archivo_galeria is not None:
                if st.button("➕ Publicar en Galería", type="primary", use_container_width=True):
                    ruta_destino = os.path.join(CARPETA_GALERIA, archivo_galeria.name)
                    with open(ruta_destino, "wb") as f:
                        f.write(archivo_galeria.getvalue())
                    st.success("¡Imagen guardada y publicada permanentemente!")
                    st.rerun()
        with col_up2:
            st.markdown("##### 🖼️ Cambiar Imagen del Menú Lateral")
            archivo_logo = st.file_uploader(
                "Foto arriba de CALANDRIAS (JPG/PNG):",
                type=["png", "jpg", "jpeg"],
                key="up_logo_sidebar_box",
            )
            if archivo_logo is not None:
                if st.button("💾 Guardar Logo en Menú", type="primary", use_container_width=True):
                    with open("logo.png", "wb") as f:
                        f.write(archivo_logo.getvalue())
                    st.success("¡Logo guardado en disco! Ahora persistirá aunque refresques.")
                    st.rerun()
        st.markdown("---")

    st.markdown("### 📸 Galería del Barrio")
    archivos_galeria = sorted(os.listdir(CARPETA_GALERIA), reverse=True)
    if archivos_galeria:
        for img_nom in archivos_galeria:
            ruta_completa = os.path.join(CARPETA_GALERIA, img_nom)
            st.image(
                ruta_completa,
                caption=img_nom,
                use_container_width=True,
            )
            st.markdown("---")
    else:
        st.info("Aún no se han cargado imágenes en la galería para exhibir.")

# =========================================================
# SECCIÓN 4: ALTA DE VECINO (FORMULARIO DIRECTO)
# =========================================================
elif st.session_state.pagina_actual == "📝 Alta de Vecino":
    st.markdown(
        '<div class="main-header">📝 Alta de Vecino</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Registro de lote y números de alarma (si ya existe, se actualizarán los datos).</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.mostrar_dialogo_otro_lote:
        st.success("✅ ¡Datos guardados exitosamente!")
        st.markdown("#### ¿Desea dar de alta otro lote con los mismos contactos?")
        col_si, col_no = st.columns(2)
        with col_si:
            if st.button(
                "👍 SÍ, cargar otro lote", type="primary", use_container_width=True
            ):
                st.session_state.mostrar_dialogo_otro_lote = False
                st.rerun()
        with col_no:
            if st.button("❌ NO, ir a Consultas", use_container_width=True):
                st.session_state.precarga = None
                st.session_state.mostrar_dialogo_otro_lote = False
                st.session_state.pagina_actual = "🔍 Consultas"
                st.rerun()
        st.stop()

    p = st.session_state.precarga or {}
    col_m, col_s, col_l = st.columns(3)
    with col_m:
        manzana = st.selectbox(
            "MANZANA *", [str(i) for i in range(15, 26)], key="alta_manzana"
        )
    with col_s:
        sector = st.selectbox("A / B *", ["A", "B"], key="alta_sector")
    with col_l:
        lote = st.selectbox(
            "LOTE *", [str(i) for i in range(1, 25)], key="alta_lote"
        )

    st.markdown("#### Contacto Principal")
    col_ap, col_nom = st.columns(2)
    with col_ap:
        apellido = st.text_input(
            "APELLIDO *", value=p.get("c1_apellido", ""), key="alta_ap"
        ).strip()
    with col_nom:
        nombre = st.text_input(
            "NOMBRE *", value=p.get("c1_nombre", ""), key="alta_nom"
        ).strip()
    celular = st.text_input(
        "CELULAR *",
        value=p.get("c1_celular", ""),
        placeholder="Ej: 1123456789 (se limpian guiones y espacios)",
        key="alta_cel",
    ).strip()

    st.markdown("##### Números de Alarma (Hasta 4 números por lote)")
    al_c1, al_c2 = st.columns(2)
    with al_c1:
        alarma1 = st.text_input(
            "Alarma 1", value=str(p.get("alarma1", "")), key="alta_al1"
        ).strip()
        alarma3 = st.text_input(
            "Alarma 3", value=str(p.get("alarma3", "")), key="alta_al3"
        ).strip()
    with al_c2:
        alarma2 = st.text_input(
            "Alarma 2", value=str(p.get("alarma2", "")), key="alta_al2"
        ).strip()
        alarma4 = st.text_input(
            "Alarma 4", value=str(p.get("alarma4", "")), key="alta_al4"
        ).strip()

    st.markdown("---")
    otro_contacto = st.selectbox(
        "¿Quiere dar de alta otro contacto para el mismo lote?",
        ["No", "Si"],
        index=1 if p.get("tiene_c2") else 0,
        key="alta_otro_contacto",
    )
    c2_apellido, c2_nombre, c2_celular = "", "", ""
    if otro_contacto == "Si":
        st.markdown("#### Segundo Contacto")
        c2_ap_col, c2_nom_col = st.columns(2)
        with c2_ap_col:
            c2_apellido = st.text_input(
                "APELLIDO (2º Contacto) *", value=p.get("c2_apellido", ""), key="c2_ap"
            ).strip()
        with c2_nom_col:
            c2_nombre = st.text_input(
                "NOMBRE (2º Contacto) *", value=p.get("c2_nombre", ""), key="c2_nom"
            ).strip()
        c2_celular = st.text_input(
            "CELULAR (2º Contacto) *",
            value=p.get("c2_celular", ""),
            placeholder="Ej: 1123456789",
            key="c2_cel",
        ).strip()

    if st.button("💾 Grabar Alta", type="primary", use_container_width=True):
        valido_c1, msg_c1, cel_c1 = validar_celular(celular)
        if not apellido or not nombre:
            st.error("Ingrese Apellido y Nombre del contacto principal.")
        elif not valido_c1:
            st.error(f"Contacto Principal: {msg_c1}")
        else:
            error_c2 = False
            cel_c2 = ""
            if otro_contacto == "Si":
                if not c2_apellido or not c2_nombre:
                    st.error("Ingrese Apellido y Nombre del segundo contacto.")
                    error_c2 = True
                else:
                    valido_c2, msg_c2, cel_c2 = validar_celular(c2_celular)
                    if not valido_c2:
                        st.error(f"Segundo Contacto: {msg_c2}")
                        error_c2 = True
            if not error_c2:
                nuevas_filas = [{
                    "MANZANA": manzana,
                    "SECTOR": sector,
                    "LOTE": lote,
                    "TIPO_CONTACTO": "Principal",
                    "APELLIDO": apellido,
                    "NOMBRE": nombre,
                    "CELULAR": cel_c1,
                    "ALARMA_1": alarma1,
                    "ALARMA_2": alarma2,
                    "ALARMA_3": alarma3,
                    "ALARMA_4": alarma4,
                }]
                if otro_contacto == "Si":
                    nuevas_filas.append({
                        "MANZANA": manzana,
                        "SECTOR": sector,
                        "LOTE": lote,
                        "TIPO_CONTACTO": "Secundario",
                        "APELLIDO": c2_apellido,
                        "NOMBRE": c2_nombre,
                        "CELULAR": cel_c2,
                        "ALARMA_1": "",
                        "ALARMA_2": "",
                        "ALARMA_3": "",
                        "ALARMA_4": "",
                    })
                with st.spinner("Guardando vecino en Google Sheets..."):
                    ok, msg_sheets = agregar_filas_sheets(nuevas_filas)
                if ok:
                    st.success("¡Datos guardados correctamente en Google Sheets!")
                    st.session_state.precarga = {
                        "c1_apellido": apellido,
                        "c1_nombre": nombre,
                        "c1_celular": cel_c1,
                        "alarma1": alarma1,
                        "alarma2": alarma2,
                        "alarma3": alarma3,
                        "alarma4": alarma4,
                        "tiene_c2": (otro_contacto == "Si"),
                        "c2_apellido": c2_apellido,
                        "c2_nombre": c2_nombre,
                        "c2_celular": cel_c2,
                    }
                    st.session_state.mostrar_dialogo_otro_lote = True
                    st.rerun()
                else:
                    st.error(f"Error al grabar en Google Sheets: {msg_sheets}")
