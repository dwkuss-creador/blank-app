import io
import json
import os
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

# Estilos CSS: Bloqueo de oscurecimiento + Adaptabilidad móvil
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
    
    /* Campo de entrada de alarma llamativo */
    div[data-testid="stTextInput"] input {
        border: 2px solid #2563EB !important;
        background-color: #F8FAFC !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        border-radius: 8px !important;
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
    
    # Blindaje contra respuesta en formato diccionario {vecinos: [...], telefonos: [...]}
    if isinstance(data, dict):
        data = data.get("vecinos", [])
        
    if data and len(data) > 1:
        headers = [str(h).strip().upper() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        for col in COLUMNAS_BD:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNAS_BD]
        for col in COLUMNAS_BD:
            df[col] = df[col].apply(normalizar_valor)
        # Si un vecino se da de alta nuevamente, keep='last' toma sus datos actualizados
        df = df.drop_duplicates(
            subset=["MANZANA", "SECTOR", "LOTE", "TIPO_CONTACTO"], keep="last"
        )
        df = ordenar_padron(df)
        return df.fillna("")
    if "db_local" not in st.session_state:
        st.session_state.db_local = pd.DataFrame(columns=COLUMNAS_BD)
    return st.session_state.db_local

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
            st.cache_data.clear()
            return True, "Guardado exitoso."
        return False, f"Error HTTP {resp.status_code} desde Google Script."
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

def guardar_datos_completos(df):
    st.session_state.db_local = df
    api_url = get_api_url()
    if api_url:
        try:
            df_ordenado = ordenar_padron(df)
            matriz = [COLUMNAS_BD] + df_ordenado.astype(str).values.tolist()
            payload = {"action": "update_all", "data": matriz}
            resp = requests.post(api_url, json=payload, timeout=30)
            if resp.status_code == 200:
                st.cache_data.clear()
                return True, "Base sincronizada con éxito."
            return False, f"Error HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
    return True, "Modo local"

# ---------------------------------------------------------
# VALIDACIÓN DE CELULAR
# ---------------------------------------------------------
def validar_celular(celular):
    cel = celular.strip()
    if not cel:
        return False, "El celular no puede estar vacío."
    if " " in cel:
        return False, "Error: El celular no debe contener espacios."
    if "-" in cel:
        return False, "Error: El celular no debe contener guiones."
    if not cel.isdigit():
        return (
            False,
            "Error: El celular solo debe contener números (sin símbolos ni letras).",
        )
    if len(cel) < 8 or len(cel) > 15:
        return False, "Error: El celular debe tener entre 8 y 15 dígitos numéricos."
    return True, ""

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

# Control de administrador por parámetro URL (?admin=si)
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
    # Auto-ocultar menú lateral al cambiar de sección
    if pagina != st.session_state.pagina_actual:
        st.session_state.pagina_actual = pagina
        st.rerun()
    st.markdown("---")
    if get_api_url():
        st.success("🟢 Google Sheets Conectado")
    else:
        st.info("🟡 Modo de prueba")

df_base = cargar_datos()

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
    # Formulario con vaciado automático
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
            
    # Ordenamiento estricto
    df_resultado = ordenar_padron(df_resultado)
    
    st.markdown("---")
    st.markdown(f"### Resultados ({criterio_activo})")
    if not df_resultado.empty:
        st.dataframe(df_resultado, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay datos para esa seleccion")
        
    # Descargas organizadas para celular
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
        '<div class="sub-header">Información de contacto, emergencias y servicios del
