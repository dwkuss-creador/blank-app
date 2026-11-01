```python
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

    /* Tarjetas del Directorio Telefónico */
    .emergency-card-banner {
        background-color: #FEF2F2;
        border: 2px solid #F87171;
        border-left: 8px solid #DC2626;
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    .useful-card-banner {
        background-color: #F8FAFC;
        border: 2px solid #94A3B8;
        border-left: 8px solid #334155;
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    .admin-card-banner {
        background-color: #F0FDF4;
        border: 2px solid #4ADE80;
        border-left: 8px solid #16A34A;
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    .phone-item-box {
        background: white;
        border: 1px solid #E2E8F0;
        padding: 12px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
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

COLUMNAS_TELEFONOS = [
    "ID",
    "TARJETA",      # 'EMERGENCIA' o 'UTILES'
    "CATEGORIA",    # 'General', 'Delivery', 'Remises y transportes', 'Servicios de obra', etc.
    "NOMBRE",       # Nombre del servicio, comercio o contacto
    "TELEFONO",     # Número telefónico
    "ACTIVO",       # 'SI' o 'NO'
]

# Directorio por defecto para inicialización si no existe aún en Sheets
TELEFONOS_DEFAULT = [
    {"ID": "1", "TARJETA": "EMERGENCIA", "CATEGORIA": "General", "NOMBRE": "Policía / Comisaría", "TELEFONO": "911", "ACTIVO": "SI"},
    {"ID": "2", "TARJETA": "EMERGENCIA", "CATEGORIA": "General", "NOMBRE": "Bomberos Voluntarios", "TELEFONO": "100", "ACTIVO": "SI"},
    {"ID": "3", "TARJETA": "EMERGENCIA", "CATEGORIA": "General", "NOMBRE": "Emergencias Médicas (SAME)", "TELEFONO": "107", "ACTIVO": "SI"},
    {"ID": "4", "TARJETA": "EMERGENCIA", "CATEGORIA": "General", "NOMBRE": "Guardia y Portería Calandrias", "TELEFONO": "11-0000-0000", "ACTIVO": "SI"},
    {"ID": "5", "TARJETA": "UTILES", "CATEGORIA": "Delivery", "NOMBRE": "Pizzería y Empanadas del Barrio", "TELEFONO": "11-2222-3333", "ACTIVO": "SI"},
    {"ID": "6", "TARJETA": "UTILES", "CATEGORIA": "Remises y transportes", "NOMBRE": "Remís Central de Zona", "TELEFONO": "11-4444-5555", "ACTIVO": "SI"},
    {"ID": "7", "TARJETA": "UTILES", "CATEGORIA": "Servicios de obra", "NOMBRE": "Electricista Matriculado", "TELEFONO": "11-6666-7777", "ACTIVO": "SI"},
]

# ---------------------------------------------------------
# CONEXIÓN DIRECTA CON CACHÉ Y TIMEOUT AMPLIADO
# ---------------------------------------------------------
def get_api_url():
    return st.secrets.get("SHEETS_API_URL", "")

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
    
    # Si la respuesta de Apps Script incluye formato con soporte multi-hoja
    if isinstance(data, dict) and "vecinos" in data:
        matriz = data["vecinos"]
    elif isinstance(data, list):
        matriz = data
    else:
        matriz = None

    if matriz and len(matriz) > 1:
        headers = [str(h).strip().upper() for h in matriz[0]]
        df = pd.DataFrame(matriz[1:], columns=headers)
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

def cargar_telefonos():
    """Carga los teléfonos desde Google Sheets o usa la base local/por defecto."""
    api_url = get_api_url()
    data = obtener_datos_remotos(api_url)
    
    matriz_tel = None
    if isinstance(data, dict) and "telefonos" in data:
        matriz_tel = data["telefonos"]
        
    if matriz_tel and len(matriz_tel) > 1:
        headers = [str(h).strip().upper() for h in matriz_tel[0]]
        df_tel = pd.DataFrame(matriz_tel[1:], columns=headers)
        for col in COLUMNAS_TELEFONOS:
            if col not in df_tel.columns:
                df_tel[col] = ""
        df_tel = df_tel[COLUMNAS_TELEFONOS]
        for col in COLUMNAS_TELEFONOS:
            df_tel[col] = df_tel[col].apply(normalizar_valor)
        return df_tel.fillna("")

    # Si aún no está en Sheets o corre en local, persistimos en st.session_state
    if "db_telefonos" not in st.session_state:
        st.session_state.db_telefonos = pd.DataFrame(TELEFONOS_DEFAULT)
    return st.session_state.db_telefonos

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

def guardar_accion_telefono_sheets(payload_accion):
    """Envía altas o bajas de teléfonos a Google Sheets o las almacena en session_state."""
    api_url = get_api_url()
    if api_url:
        try:
            resp = requests.post(api_url, json=payload_accion, timeout=30)
            if resp.status_code == 200:
                st.cache_data.clear()
                return True, "Operación guardada en Sheets con éxito."
            return False, f"Error HTTP {resp.status_code} desde Apps Script."
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"
    
    # Manejo local si no hay api_url conectada
    df_actual = st.session_state.db_telefonos.copy()
    if payload_accion.get("action") == "add_phone":
        nuevo_item = payload_accion.get("data", {})
        nuevo_df = pd.DataFrame([nuevo_item])
        st.session_state.db_telefonos = pd.concat([df_actual, nuevo_df], ignore_index=True)
    elif payload_accion.get("action") == "deactivate_phone":
        tel_id = str(payload_accion.get("id"))
        st.session_state.db_telefonos.loc[st.session_state.db_telefonos["ID"] == tel_id, "ACTIVO"] = "NO"
    return True, "Actualizado en sesión local."

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
    # Soporte para logo regular o navideño
    logo_encontrado = None
    candidatos_logo = [
        "logo_navidad.png",
        "logo_navidad.jpg",
        "logo.png",
        "logo.jpg",
        "logo.jpeg",
        "calandrias.png",
        "calandrias.jpg",
    ]
    for candidato in candidatos_logo:
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
# SECCIÓN 2: DATOS ÚTILES Y DIRECTORIO TELEFÓNICO
# =========================================================
elif st.session_state.pagina_actual == "ℹ️ Datos Útiles":
    st.markdown(
        '<div class="main-header">ℹ️ Directorio y Teléfonos Útiles</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Contactos de urgencia y servicios de confianza para el barrio.</div>',
        unsafe_allow_html=True,
    )

    df_tel_total = cargar_telefonos()
    df_activos = df_tel_total[df_tel_total["ACTIVO"].astype(str).str.upper() == "SI"]

    # -----------------------------------------------------
    # TARJETA 1: TELÉFONOS DE EMERGENCIA (ANCHO COMPLETO)
    # -----------------------------------------------------
    st.markdown(
        """
        <div class="emergency-card-banner">
            <h3 style="margin: 0; color: #991B1B; font-size: 1.3rem;">🚨 TELÉFONOS DE EMERGENCIA</h3>
            <p style="margin: 4px 0 0 0; color: #7F1D1D; font-size: 0.95rem;">
                Comuníquese inmediatamente tocando el número deseado en caso de urgencia.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_emergencia = df_activos[df_activos["TARJETA"] == "EMERGENCIA"]
    if not df_emergencia.empty:
        # Se distribuyen en 2 columnas en mobile o hasta 4 en desktop ocupando todo el ancho
        num_items = len(df_emergencia)
        cols_count = 4 if num_items >= 4 else (num_items if num_items > 0 else 1)
        cols_em = st.columns(cols_count)
        for idx, (_, row) in enumerate(df_emergencia.iterrows()):
            with cols_em[idx % cols_count]:
                tel_limpio = row["TELEFONO"].replace(" ", "").replace("-", "")
                st.markdown(
                    f"""
                    <div style="background: white; border: 1.5px solid #FCA5A5; padding: 14px 12px; border-radius: 8px; text-align: center; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="font-weight: 700; color: #1F2937; font-size: 1rem; margin-bottom: 6px;">{row['NOMBRE']}</div>
                        <a href="tel:{tel_limpio}" style="display: inline-block; background-color: #DC2626; color: white; padding: 6px 14px; border-radius: 6px; font-weight: bold; text-decoration: none; font-size: 1.05rem;">
                            📞 {row['TELEFONO']}
                        </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No hay teléfonos de emergencia configurados actualmente.")

    st.write("")  # Espaciador vertical

    # -----------------------------------------------------
    # TARJETA 2: TELÉFONOS ÚTILES (CATEGORÍAS DESPLEGABLES)
    # -----------------------------------------------------
    st.markdown(
        """
        <div class="useful-card-banner">
            <h3 style="margin: 0; color: #1E293B; font-size: 1.3rem;">📞 TELÉFONOS ÚTILES</h3>
            <p style="margin: 4px 0 0 0; color: #475569; font-size: 0.95rem;">
                Haga clic en cada categoría para desplegar la lista de proveedores recomendados.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_utiles = df_activos[df_activos["TARJETA"] == "UTILES"]

    # Orden obligatorio de categorías prioritarias
    orden_prioritario = ["Delivery", "Remises y transportes", "Servicios de obra"]
    categorias_reales = list(df_utiles["CATEGORIA"].unique())

    categorias_finales = [c for c in orden_prioritario if c in categorias_reales]
    categorias_finales += [c for c in categorias_reales if c not in orden_prioritario and c != ""]

    # Si aún no hay datos en alguna de las prioritarias, las mostramos como acordeones vacíos o listos
    for c_prioritaria in orden_prioritario:
        if c_prioritaria not in categorias_finales:
            categorias_finales.append(c_prioritaria)

    iconos_cat = {
        "Delivery": "🍕",
        "Remises y transportes": "🚗",
        "Servicios de obra": "🔨",
    }

    for cat in categorias_finales:
        icono = iconos_cat.get(cat, "📁")
        contactos_cat = df_utiles[df_utiles["CATEGORIA"] == cat]
        cantidad = len(contactos_cat)
        
        with st.expander(f"{icono} **{cat.upper()}** ({cantidad})", expanded=(cat == "Delivery")):
            if not contactos_cat.empty:
                for _, item in contactos_cat.iterrows():
                    c_info, c_call = st.columns([3.5, 1.5])
                    with c_info:
                        st.markdown(f"**{item['NOMBRE']}**")
                    with c_call:
                        tel_num = item["TELEFONO"].replace(" ", "").replace("-", "")
                        st.markdown(f"📞 [{item['TELEFONO']}](tel:{tel_num})")
                    st.divider()
            else:
                st.caption("Aún no hay contactos activos registrados en esta categoría.")

    # -----------------------------------------------------
    # MÓDULO DE GESTIÓN ADMINISTRATIVA (?admin=si)
    # -----------------------------------------------------
    if es_admin:
        st.markdown("---")
        st.markdown(
            """
            <div class="admin-card-banner">
                <h4 style="margin: 0; color: #166534;">⚙️ Panel Administrativo: Gestión de Directorio</h4>
                <p style="margin: 4px 0 0 0; color: #374151; font-size: 0.92rem;">
                    Exclusivo Diego / Administrador. Permite dar de alta o baja números sin tocar el código.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_alta_tel, tab_baja_tel = st.tabs(["➕ Dar de Alta Teléfono", "❌ Dar de Baja Teléfono"])

        with tab_alta_tel:
            st.markdown("##### Registrar nuevo contacto o servicio")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                tipo_tarjeta = st.selectbox(
                    "¿A qué tarjeta pertenece?",
                    ["UTILES", "EMERGENCIA"],
                    key="sel_tipo_tarjeta",
                )
            with col_t2:
                if tipo_tarjeta == "UTILES":
                    lista_cat = ["Delivery", "Remises y transportes", "Servicios de obra", "➕ Nueva categoría..."]
                    cat_select = st.selectbox("Categoría:", lista_cat, key="sel_cat_utiles")
                    if cat_select == "➕ Nueva categoría...":
                        cat_final = st.text_input("Escriba la nueva categoría:", key="txt_nueva_cat").strip()
                    else:
                        cat_final = cat_select
                else:
                    cat_final = "General"
                    st.text_input("Categoría:", value="General", disabled=True)

            col_nom, col_num = st.columns(2)
            with col_nom:
                nuevo_nombre = st.text_input("Nombre / Razón Social / Proveedor:", key="nuevo_tel_nom").strip()
            with col_num:
                nuevo_numero = st.text_input("Teléfono (ej: 11-1234-5678):", key="nuevo_tel_num").strip()

            if st.button("💾 Guardar en Directorio", type="primary", use_container_width=True):
                if not nuevo_nombre or not nuevo_numero:
                    st.error("Por favor ingrese tanto el nombre como el teléfono.")
                elif tipo_tarjeta == "UTILES" and not cat_final:
                    st.error("Por favor especifique la categoría.")
                else:
                    nuevo_id = str(len(df_tel_total) + 1)
                    payload_nuevo = {
                        "action": "add_phone",
                        "data": {
                            "ID": nuevo_id,
                            "TARJETA": tipo_tarjeta,
                            "CATEGORIA": cat_final,
                            "NOMBRE": nuevo_nombre,
                            "TELEFONO": nuevo_numero,
                            "ACTIVO": "SI",
                        },
                    }
                    ok, msg = guardar_accion_telefono_sheets(payload_nuevo)
                    if ok:
                        st.success(f"¡'{nuevo_nombre}' agregado exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {msg}")

        with tab_baja_tel:
            st.markdown("##### Desactivar contactos existentes")
            contactos_para_baja = df_activos.copy()
            if not contactos_para_baja.empty:
                opciones_baja = contactos_para_baja["ID"].tolist()
                id_seleccionado = st.selectbox(
                    "Seleccione el contacto a dar de baja:",
                    opciones_baja,
                    format_func=lambda x: f"[{contactos_para_baja.loc[contactos_para_baja['ID']==x, 'TARJETA'].values[0]}] - {contactos_para_baja.loc[contactos_para_baja['ID']==x, 'NOMBRE'].values[0]} ({contactos_para_baja.loc[contactos_para_baja['ID']==x, 'TELEFONO'].values[0]}) - Cat: {contactos_para_baja.loc[contactos_para_baja['ID']==x, 'CATEGORIA'].values[0]}",
                )
                if st.button("🗑️ Confirmar Baja", type="secondary", use_container_width=True):
                    payload_baja = {
                        "action": "deactivate_phone",
                        "id": id_seleccionado,
                    }
                    ok, msg = guardar_accion_telefono_sheets(payload_baja)
                    if ok:
                        st.warning(f"Contacto ID {id_seleccionado} dado de baja exitosamente.")
                        st.rerun()
                    else:
                        st.error(f"Error al dar de baja: {msg}")
            else:
                st.info("No hay contactos activos disponibles para dar de baja.")

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

    # TÍTULO: GALERÍA DEL BARRIO
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
            "APELLIDO *", value=p.get("c1_apellido", "")
        ).strip()
    with col_nom:
        nombre = st.text_input("NOMBRE *", value=p.get("c1_nombre", "")).strip()

    celular = st.text_input(
        "CELULAR *",
        value=p.get("c1_celular", ""),
        placeholder="Sin guiones ni espacios",
    ).strip()

    st.markdown("##### Números de Alarma (Hasta 4 números por lote)")
    al_c1, al_c2 = st.columns(2)
    with al_c1:
        alarma1 = st.text_input(
            "Alarma 1", value=str(p.get("alarma1", ""))
        ).strip()
        alarma3 = st.text_input(
            "Alarma 3", value=str(p.get("alarma3", ""))
        ).strip()
    with al_c2:
        alarma2 = st.text_input(
            "Alarma 2", value=str(p.get("alarma2", ""))
        ).strip()
        alarma4 = st.text_input(
            "Alarma 4", value=str(p.get("alarma4", ""))
        ).strip()

    st.markdown("---")
    otro_contacto = st.selectbox(
        "¿Quiere dar de alta otro contacto para el mismo lote?",
        ["No", "Si"],
        index=1 if p.get("tiene_c2") else 0,
    )

    c2_apellido, c2_nombre, c2_celular = "", "", ""
    if otro_contacto == "Si":
        st.markdown("#### Segundo Contacto")
        c2_ap_col, c2_nom_col = st.columns(2)
        with c2_ap_col:
            c2_apellido = st.text_input(
                "APELLIDO (2º Contacto) *", value=p.get("c2_apellido", "")
            ).strip()
        with c2_nom_col:
            c2_nombre = st.text_input(
                "NOMBRE (2º Contacto) *", value=p.get("c2_nombre", "")
            ).strip()
        c2_celular = st.text_input(
            "CELULAR (2º Contacto) *",
            value=p.get("c2_celular", ""),
            placeholder="Sin guiones ni espacios",
            key="c2_cel",
        ).strip()

    if st.button("💾 Grabar Alta", type="primary", use_container_width=True):
        valido_c1, msg_c1 = validar_celular(celular)
        if not apellido or not nombre:
            st.error("Ingrese Apellido y Nombre del contacto principal.")
        elif not valido_c1:
            st.error(f"Contacto Principal: {msg_c1}")
        else:
            error_c2 = False
            if otro_contacto == "Si":
                if not c2_apellido or not c2_nombre:
                    st.error("Ingrese Apellido y Nombre del segundo contacto.")
                    error_c2 = True
                else:
                    valido_c2, msg_c2 = validar_celular(c2_celular)
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
                    "CELULAR": celular,
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
                        "CELULAR": c2_celular,
                        "ALARMA_1": "",
                        "ALARMA_2": "",
                        "ALARMA_3": "",
                        "ALARMA_4": "",
                    })
                ok, msg_sheets = agregar_filas_sheets(nuevas_filas)
                if ok:
                    st.success("¡Datos guardados correctamente en Google Sheets!")
                    st.session_state.precarga = {
                        "c1_apellido": apellido,
                        "c1_nombre": nombre,
                        "c1_celular": celular,
                        "alarma1": alarma1,
                        "alarma2": alarma2,
                        "alarma3": alarma3,
                        "alarma4": alarma4,
                        "tiene_c2": (otro_contacto == "Si"),
                        "c2_apellido": c2_apellido,
                        "c2_nombre": c2_nombre,
                        "c2_celular": c2_celular,
                    }
                    st.session_state.mostrar_dialogo_otro_lote = True
                    st.rerun()
                else:
                    st.error(f"Error al grabar en Google Sheets: {msg_sheets}")
```
