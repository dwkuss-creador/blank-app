import io
import re
from fpdf import FPDF
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="APP VECINOS CALANDRIAS",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# ESTILOS CSS PERSONALIZADOS
# ---------------------------------------------------------
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #4B5563;
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        border-radius: 8px;
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
# CONEXIÓN CON GOOGLE SHEETS & GESTIÓN DE DATOS
# ---------------------------------------------------------
def obtener_conexion():
  try:
    return st.connection("gsheets", type=GSheetsConnection)
  except Exception:
    return None


def cargar_datos():
  conn = obtener_conexion()
  if conn:
    try:
      df = conn.read(worksheet="Vecinos", ttl=0)
      if df is not None and not df.empty:
        # Asegurar tipos de columnas
        df["MANZANA"] = df["MANZANA"].astype(str)
        df["SECTOR"] = df["SECTOR"].astype(str)
        df["LOTE"] = df["LOTE"].astype(str)
        return df.fillna("")
    except Exception as e:
      st.warning(f"Aviso de sincronización con Google Sheets: {e}")

  # Fallback en memoria si aún no configuró Google Sheets en los Secrets de Streamlit
  if "db_local" not in st.session_state:
    st.session_state.db_local = pd.DataFrame(columns=COLUMNAS_BD)
  return st.session_state.db_local


def guardar_datos(df):
  conn = obtener_conexion()
  if conn:
    try:
      conn.update(worksheet="Vecinos", data=df)
      st.session_state.db_local = df
      return True
    except Exception as e:
      st.error(f"Error al escribir en Google Sheets: {e}")
  # Guardado local temporal en sesión si no hay Sheets conectado
  st.session_state.db_local = df
  return True


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
        "Error: El celular solo debe contener números (sin símbolos ni"
        " letras).",
    )
  if len(cel) < 8 or len(cel) > 15:
    return False, "Error: El celular debe tener entre 8 y 15 dígitos numéricos."
  return True, ""


# ---------------------------------------------------------
# GENERADORES DE REPORTES (EXCEL Y PDF)
# ---------------------------------------------------------
def exportar_excel(df):
  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Vecinos")
  return output.getvalue()


def exportar_pdf(df, titulo="Reporte Vecinos - Calandrias"):
  pdf = FPDF(orientation="L", unit="mm", format="A4")
  pdf.add_page()
  pdf.set_font("Helvetica", "B", 14)
  pdf.cell(0, 10, titulo, ln=True, align="C")
  pdf.ln(4)

  # Cabeceras de tabla
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
  for _, row in df.iterrows():
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
# ESTADO DE NAVEGACIÓN Y PRECARGA DE DATOS
# ---------------------------------------------------------
if "pagina_actual" not in st.session_state:
  st.session_state.pagina_actual = "🔍 Consultas"

if "precarga" not in st.session_state:
  st.session_state.precarga = None

if "mostrar_dialogo_otro_lote" not in st.session_state:
  st.session_state.mostrar_dialogo_otro_lote = False

# ---------------------------------------------------------
# BARRA LATERAL (NAVEGACIÓN)
# ---------------------------------------------------------
with st.sidebar:
  st.image("https://img.icons8.com/fluency/96/neighborhood.png", width=70)
  st.title("APP CALANDRIAS")
  st.caption("Gestión Vecinal y Alarmas")

  opciones_menu = [
      "🔍 Consultas",
      "📝 Alta / Modificación",
      "ℹ️ Datos Útiles",
      "🖼️ Galería e Imágenes",
  ]

  pagina = st.radio(
      "Navegación:",
      opciones_menu,
      index=opciones_menu.index(st.session_state.pagina_actual),
  )
  st.session_state.pagina_actual = pagina
  st.markdown("---")
  st.info("💡 Desarrollado para uso autónomo e independiente de los vecinos.")

# Carga de la base de datos desde Sheets o Memoria Local
df_base = cargar_datos()

# =========================================================
# HOJA 1: CONSULTAS
# =========================================================
if st.session_state.pagina_actual == "🔍 Consultas":
  st.markdown(
      '<div class="main-header">🔍 Consulta de Base de Datos</div>',
      unsafe_allow_html=True,
  )
  st.markdown(
      '<div class="sub-header">Busca vecinos registrados por Manzana, Lote o'
      " Número de Alarma.</div>",
      unsafe_allow_html=True,
  )

  c1, c2, c3 = st.columns(3)
  with c1:
    filtro_manzana = st.checkbox("Buscar por Manzana", value=True)
  with c2:
    filtro_lote = st.checkbox("Buscar por Lote")
  with c3:
    filtro_alarma = st.checkbox("Buscar por Número de Alarma")

  df_resultado = df_base.copy()

  # 1. Filtro por Manzana
  if filtro_manzana and not filtro_lote and not filtro_alarma:
    col_m, col_s = st.columns(2)
    with col_m:
      m_sel = st.selectbox("Seleccione Manzana:", [str(i) for i in range(15, 26)])
    with col_s:
      s_sel = st.selectbox("Seleccione Sector (A/B):", ["A", "B"])

    df_resultado = df_resultado[
        (df_resultado["MANZANA"] == m_sel) & (df_resultado["SECTOR"] == s_sel)
    ]

  # 2. Filtro por Lote
  elif filtro_lote:
    col_m, col_s, col_l = st.columns(3)
    with col_m:
      m_sel = st.selectbox("Manzana:", [str(i) for i in range(15, 26)])
    with col_s:
      s_sel = st.selectbox("Sector:", ["A", "B"])
    with col_l:
      l_sel = st.selectbox("Lote:", [str(i) for i in range(1, 25)])

    df_resultado = df_resultado[
        (df_resultado["MANZANA"] == m_sel)
        & (df_resultado["SECTOR"] == s_sel)
        & (df_resultado["LOTE"] == l_sel)
    ]

  # 3. Filtro por Alarma
  elif filtro_alarma:
    alarma_buscada = st.text_input(
        "Ingrese el Número de Alarma:", placeholder="Ej: 104"
    ).strip()
    if alarma_buscada:
      condicion = (
          (df_resultado["ALARMA_1"] == alarma_buscada)
          | (df_resultado["ALARMA_2"] == alarma_buscada)
          | (df_resultado["ALARMA_3"] == alarma_buscada)
          | (df_resultado["ALARMA_4"] == alarma_buscada)
      )
      df_resultado = df_resultado[condicion]

  # Mostrar resultados
  st.markdown("### Resultados encontrados")
  if not df_resultado.empty:
    st.dataframe(df_resultado, use_container_width=True, hide_index=True)
  else:
    st.warning("No se encontraron registros que coincidan con la búsqueda.")

  st.markdown("---")
  st.markdown("### 📥 Descarga de Información")
  d1, d2, d3, d4 = st.columns(4)

  with d1:
    st.download_button(
        label="📊 Descargar Consulta (Excel)",
        data=exportar_excel(df_resultado),
        file_name="consulta_vecinos.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  with d2:
    st.download_button(
        label="📄 Descargar Consulta (PDF)",
        data=exportar_pdf(df_resultado, "Consulta de Vecinos - Calandrias"),
        file_name="consulta_vecinos.pdf",
        mime="application/pdf",
    )
  with d3:
    st.download_button(
        label="💾 Descargar Toda la Base (Excel)",
        data=exportar_excel(df_base),
        file_name="base_completa_vecinos.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  with d4:
    st.download_button(
        label="📑 Descargar Toda la Base (PDF)",
        data=exportar_pdf(df_base, "Base Completa Vecinos - Calandrias"),
        file_name="base_completa_vecinos.pdf",
        mime="application/pdf",
    )

# =========================================================
# HOJA 2: ALTA / MODIFICACIÓN
# =========================================================
elif st.session_state.pagina_actual == "📝 Alta / Modificación":
  st.markdown(
      '<div class="main-header">📝 Registro y Modificación de Datos</div>',
      unsafe_allow_html=True,
  )

  # Ventana emergente posterior a la grabación de lote
  if st.session_state.mostrar_dialogo_otro_lote:
    st.success("✅ ¡Datos guardados exitosamente!")
    st.markdown("#### ¿Desea dar de alta otro lote con los mismos contactos?")
    col_si, col_no = st.columns(2)
    with col_si:
      if st.button("👍 SÍ, cargar otro lote con los mismos datos"):
        st.session_state.mostrar_dialogo_otro_lote = False
        st.rerun()
    with col_no:
      if st.button("❌ NO, ir a Consultas"):
        st.session_state.precarga = None
        st.session_state.mostrar_dialogo_otro_lote = False
        st.session_state.pagina_actual = "🔍 Consultas"
        st.rerun()
    st.stop()

  modo = st.radio(
      "Seleccione una acción:",
      ["Alta de vecino", "Modificación de datos"],
      horizontal=True,
  )

  # --- MODO ALTA ---
  if modo == "Alta de vecino":
    st.subheader("Formulario de Alta")

    # Valores precargados si viene de dar de alta otro lote
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
    a1, a2, a3, a4 = st.columns(4)
    with a1:
      alarma1 = st.text_input("Alarma 1", value=p.get("alarma1", "")).strip()
    with a2:
      alarma2 = st.text_input("Alarma 2", value=p.get("alarma2", "")).strip()
    with a3:
      alarma3 = st.text_input("Alarma 3", value=p.get("alarma3", "")).strip()
    with a4:
      alarma4 = st.text_input("Alarma 4", value=p.get("alarma4", "")).strip()

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
            "APELLIDO (Segundo Contacto) *", value=p.get("c2_apellido", "")
        ).strip()
      with c2_nom_col:
        c2_nombre = st.text_input(
            "NOMBRE (Segundo Contacto) *", value=p.get("c2_nombre", "")
        ).strip()
      c2_celular = st.text_input(
          "CELULAR (Segundo Contacto) *",
          value=p.get("c2_celular", ""),
          placeholder="Sin guiones ni espacios",
          key="c2_cel",
      ).strip()

    if st.button("💾 Grabar Alta", type="primary", use_container_width=True):
      # Validaciones
      valido_c1, msg_c1 = validar_celular(celular)
      if not apellido or not nombre:
        st.error("Por favor, ingrese Apellido y Nombre del contacto principal.")
      elif not valido_c1:
        st.error(f"Contacto Principal: {msg_c1}")
      else:
        error_c2 = False
        if otro_contacto == "Si":
          if not c2_apellido or not c2_nombre:
            st.error("Por favor, ingrese Apellido y Nombre del segundo contacto.")
            error_c2 = True
          else:
            valido_c2, msg_c2 = validar_celular(c2_celular)
            if not valido_c2:
              st.error(f"Segundo Contacto: {msg_c2}")
              error_c2 = True

        if not error_c2:
          # Construcción de las nuevas filas a anexar
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

          df_actualizado = pd.concat(
              [df_base, pd.DataFrame(nuevas_filas)], ignore_index=True
          )
          guardar_datos(df_actualizado)

          # Guardar datos en precarga por si desea registrar otro lote
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

  # --- MODO MODIFICACIÓN ---
  else:
    st.subheader("Modificación de Datos Existentes")
    col_m, col_s, col_l = st.columns(3)
    with col_m:
      m_mod = st.selectbox(
          "Seleccione Manzana:",
          [str(i) for i in range(15, 26)],
          key="mod_manzana",
      )
    with col_s:
      s_mod = st.selectbox("Seleccione Sector:", ["A", "B"], key="mod_sector")
    with col_l:
      l_mod = st.selectbox(
          "Seleccione Lote:", [str(i) for i in range(1, 25)], key="mod_lote"
      )

    coincidencias = df_base[
        (df_base["MANZANA"] == m_mod)
        & (df_base["SECTOR"] == s_mod)
        & (df_base["LOTE"] == l_mod)
    ]

    if coincidencias.empty:
      st.warning(
          f"No se encontró ningún registro para Manzana {m_mod} Sector {s_mod}"
          f" Lote {l_mod}."
      )
    else:
      st.info(f"Se encontraron {len(coincidencias)} contacto(s) para este lote.")
      filas_editadas = []

      for idx, row in coincidencias.iterrows():
        tipo = row.get("TIPO_CONTACTO", "Contacto")
        st.markdown(f"#### Editando {tipo}: {row.get('APELLIDO', '')}")

        c_ap, c_nom, c_cel = st.columns(3)
        with c_ap:
          nuevo_ap = st.text_input(
              f"Apellido ({tipo})", value=row.get("APELLIDO", ""), key=f"ap_{idx}"
          )
        with c_nom:
          nuevo_nom = st.text_input(
              f"Nombre ({tipo})", value=row.get("NOMBRE", ""), key=f"nom_{idx}"
          )
        with c_cel:
          nuevo_cel = st.text_input(
              f"Celular ({tipo})",
              value=row.get("CELULAR", ""),
              key=f"cel_{idx}",
          )

        a1, a2, a3, a4 = row.get("ALARMA_1", ""), "", "", ""
        if tipo == "Principal":
          st.caption("Alarmas del Lote")
          al1_c, al2_c, al3_c, al4_c = st.columns(4)
          with al1_c:
            a1 = st.text_input(
                "Alarma 1", value=row.get("ALARMA_1", ""), key=f"al1_{idx}"
            )
          with al2_c:
            a2 = st.text_input(
                "Alarma 2", value=row.get("ALARMA_2", ""), key=f"al2_{idx}"
            )
          with al3_c:
            a3 = st.text_input(
                "Alarma 3", value=row.get("ALARMA_3", ""), key=f"al3_{idx}"
            )
          with al4_c:
            a4 = st.text_input(
                "Alarma 4", value=row.get("ALARMA_4", ""), key=f"al4_{idx}"
            )

        filas_editadas.append({
            "INDEX": idx,
            "MANZANA": m_mod,
            "SECTOR": s_mod,
            "LOTE": l_mod,
            "TIPO_CONTACTO": tipo,
            "APELLIDO": nuevo_ap,
            "NOMBRE": nuevo_nom,
            "CELULAR": nuevo_cel,
            "ALARMA_1": a1,
            "ALARMA_2": a2,
            "ALARMA_3": a3,
            "ALARMA_4": a4,
        })

      if st.button("💾 Guardar Modificaciones", type="primary"):
        # Validar celulares antes de guardar
        error = False
        for f in filas_editadas:
          valido, msg = validar_celular(f["CELULAR"])
          if not valido:
            st.error(f"Error en {f['TIPO_CONTACTO']}: {msg}")
            error = True
            break

        if not error:
          df_modificado = df_base.copy()
          for f in filas_editadas:
            idx = f["INDEX"]
            for col in COLUMNAS_BD:
              df_modificado.at[idx, col] = f[col]

          guardar_datos(df_modificado)
          st.success("¡Datos actualizados con éxito!")
          st.rerun()

# =========================================================
# HOJA 3: DATOS ÚTILES
# =========================================================
elif st.session_state.pagina_actual == "ℹ️ Datos Útiles":
  st.markdown(
      '<div class="main-header">ℹ️ Directorio y Datos Útiles</div>',
      unsafe_allow_html=True,
  )
  st.markdown(
      '<div class="sub-header">Información de contacto, emergencias y servicios'
      " del barrio.</div>",
      unsafe_allow_html=True,
  )

  col1, col2 = st.columns(2)
  with col1:
    st.markdown("### 🚨 Teléfonos de Emergencia")
    st.info("""
        * **Guardia / Portería Calandrias:** (A completar)
        * **Policía / Comisaría:** 911 / (A completar)
        * **Bomberos:** 100 / (A completar)
        * **Emergencias Médicas / Ambulancia:** 107
        """)

  with col2:
    st.markdown("### 🏢 Administración y Servicios")
    st.info("""
        * **Administración del Barrio:** (A completar)
        * **Mantenimiento General:** (A completar)
        * **Recolección de Residuos:** Días y horarios a definir
        * **Comisión Vecinal:** (A completar)
        """)

# =========================================================
# HOJA 4: GALERÍA E IMÁGENES
# =========================================================
elif st.session_state.pagina_actual == "🖼️ Galería e Imágenes":
  st.markdown(
      '<div class="main-header">🖼️ Galería y Comunicados</div>',
      unsafe_allow_html=True,
  )
  st.markdown(
      '<div class="sub-header">Planos del barrio, avisos importantes y'
      " fotografías.</div>",
      unsafe_allow_html=True,
  )

  st.write("Sube imágenes o comunicados para visualizarlos aquí:")
  archivo_img = st.file_uploader(
      "Subir una imagen o aviso (JPG / PNG):", type=["png", "jpg", "jpeg"]
  )
  if archivo_img:
    st.image(archivo_img, caption="Imagen cargada", use_column_width=True)
  else:
    st.info(
        "Aún no se han cargado imágenes para exhibir. Puedes usar el botón de"
        " arriba para previsualizar planos o avisos."
    )
