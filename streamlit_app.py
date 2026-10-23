import io
import json
from fpdf import FPDF
import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="APP VECINOS CALANDRIAS",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header { font-size: 2.1rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { color: #4B5563; font-size: 1.05rem; margin-bottom: 1.2rem; }
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
# CONEXIÓN DIRECTA CON GOOGLE SHEETS (VÍA GOOGLE APPS SCRIPT)
# ---------------------------------------------------------
def get_api_url():
  return st.secrets.get("SHEETS_API_URL", "")


def cargar_datos():
  api_url = get_api_url()
  if api_url:
    try:
      resp = requests.get(api_url, timeout=10)
      if resp.status_code == 200:
        data = resp.json()
        if len(data) > 1:
          headers = [str(h).strip().upper() for h in data[0]]
          df = pd.DataFrame(data[1:], columns=headers)
          for col in COLUMNAS_BD:
            if col not in df.columns:
              df[col] = ""
          df = df[COLUMNAS_BD]
          df["MANZANA"] = df["MANZANA"].astype(str)
          df["SECTOR"] = df["SECTOR"].astype(str)
          df["LOTE"] = df["LOTE"].astype(str)
          return df.fillna("")
    except Exception:
      pass

  if "db_local" not in st.session_state:
    st.session_state.db_local = pd.DataFrame(columns=COLUMNAS_BD)
  return st.session_state.db_local


def guardar_datos(df):
  st.session_state.db_local = df
  api_url = get_api_url()
  if api_url:
    try:
      # Convertir DataFrame a lista de listas (incluyendo cabecera)
      matriz = [COLUMNAS_BD] + df.astype(str).values.tolist()
      payload = {"action": "update_all", "data": matriz}
      requests.post(api_url, json=payload, timeout=10)
      return True
    except Exception:
      pass
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
# EXPORTACIÓN
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
# NAVEGACIÓN Y ESTADO
# ---------------------------------------------------------
if "pagina_actual" not in st.session_state:
  st.session_state.pagina_actual = "🔍 Consultas"

if "precarga" not in st.session_state:
  st.session_state.precarga = None

if "mostrar_dialogo_otro_lote" not in st.session_state:
  st.session_state.mostrar_dialogo_otro_lote = False

with st.sidebar:
  st.image("https://img.icons8.com/fluency/96/neighborhood.png", width=70)
  st.title("APP CALANDRIAS")
  st.caption("Padrón Vecinal y Alarmas")

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
  if get_api_url():
    st.success("🟢 Conectado con Google Sheets")
  else:
    st.info("🟡 Modo local de prueba")

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
      '<div class="sub-header">Búsqueda rápida por Alarma (prioridad) o por'
      " Manzana / Lote.</div>",
      unsafe_allow_html=True,
  )

  st.markdown(
      """
    <div style="background-color: #EFF6FF; padding: 15px; border-radius: 8px; border-left: 6px solid #3B82F6; margin-bottom: 20px;">
        <h4 style="margin: 0; color: #1E40AF;">🚨 Búsqueda Prioritaria por Número de Alarma</h4>
        <p style="margin: 5px 0 0 0; color: #4B5563; font-size: 0.95rem;">Ingrese el número de alarma disparada para ubicar inmediatamente al vecino responsable.</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

  col_al1, col_al2 = st.columns(2)
  with col_al1:
    alarma_input = st.text_input(
        "Número de Alarma:",
        placeholder="Ingrese el número de alarma y presione Enter (ej: 104)",
        label_visibility="collapsed",
    ).strip()
  with col_al2:
    buscar_alarma_btn = st.button(
        "🔍 Buscar Alarma", type="primary", use_container_width=True
    )

  df_resultado = df_base.copy()
  criterio_activo = ""

  if alarma_input:
    criterio_activo = f"Alarma: {alarma_input}"
    condicion = (
        (df_resultado["ALARMA_1"] == alarma_input)
        | (df_resultado["ALARMA_2"] == alarma_input)
        | (df_resultado["ALARMA_3"] == alarma_input)
        | (df_resultado["ALARMA_4"] == alarma_input)
    )
    df_resultado = df_resultado[condicion]

  else:
    st.markdown("---")
    st.markdown("#### 📍 Búsqueda por Ubicación (Manzana o Lote)")

    col_tipo, col_filtros = st.columns(2)
    with col_tipo:
      tipo_ubicacion = st.radio(
          "Seleccione criterio:",
          ["Mostrar Todos", "Por Manzana", "Por Lote Específico"],
      )

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
            (df_resultado["MANZANA"] == m_sel)
            & (df_resultado["SECTOR"] == s_sel)
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
            (df_resultado["MANZANA"] == m_sel)
            & (df_resultado["SECTOR"] == s_sel)
            & (df_resultado["LOTE"] == l_sel)
        ]
      else:
        criterio_activo = "Base Completa"

  st.markdown("---")
  st.markdown(f"### Resultados ({criterio_activo})")
  if not df_resultado.empty:
    st.dataframe(df_resultado, use_container_width=True, hide_index=True)
  else:
    st.warning("No se encontraron registros para la búsqueda ingresada.")

  st.markdown("---")
  st.markdown("### 📥 Descargar Reportes")
  d1, d2, d3, d4 = st.columns(4)
  with d1:
    st.download_button(
        label="📊 Consulta Actual (Excel)",
        data=exportar_excel(df_resultado),
        file_name="consulta_vecinos.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )
  with d2:
    st.download_button(
        label="📄 Consulta Actual (PDF)",
        data=exportar_pdf(
            df_resultado, f"Consulta Vecinos Calandrias - {criterio_activo}"
        ),
        file_name="consulta_vecinos.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
  with d3:
    st.download_button(
        label="💾 Padrón Completo (Excel)",
        data=exportar_excel(df_base),
        file_name="padron_completo_calandrias.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )
  with d4:
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
# HOJA 2: ALTA / MODIFICACIÓN
# =========================================================
elif st.session_state.pagina_actual == "📝 Alta / Modificación":
  st.markdown(
      '<div class="main-header">📝 Registro y Modificación de Datos</div>',
      unsafe_allow_html=True,
  )

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

  if modo == "Alta de vecino":
    st.subheader("Formulario de Alta")
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
      alarma1 = st.text_input(
          "Alarma 1", value=str(p.get("alarma1", ""))
      ).strip()
    with a2:
      alarma2 = st.text_input(
          "Alarma 2", value=str(p.get("alarma2", ""))
      ).strip()
    with a3:
      alarma3 = st.text_input(
          "Alarma 3", value=str(p.get("alarma3", ""))
      ).strip()
    with a4:
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
                "Alarma 1", value=str(row.get("ALARMA_1", "")), key=f"al1_{idx}"
            )
          with al2_c:
            a2 = st.text_input(
                "Alarma 2", value=str(row.get("ALARMA_2", "")), key=f"al2_{idx}"
            )
          with al3_c:
            a3 = st.text_input(
                "Alarma 3", value=str(row.get("ALARMA_3", "")), key=f"al3_{idx}"
            )
          with al4_c:
            a4 = st.text_input(
                "Alarma 4", value=str(row.get("ALARMA_4", "")), key=f"al4_{idx}"
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
    st.info("Aún no se han cargado imágenes para exhibir.")
