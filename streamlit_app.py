import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# 1. RENDERIZADO: VISTA VECINOS (DIRECTORIO Y TELÉFONOS ÚTILES)
# -----------------------------------------------------------------------------
def render_directorio_telefonico(df_telefonos: pd.DataFrame):
    """
    df_telefonos debe contener las columnas:
    ['id', 'tarjeta', 'categoria', 'nombre', 'telefono', 'activo']
    """
    # Filtrar solo los números activos
    if df_telefonos.empty:
        st.info("No hay teléfonos cargados en el directorio actualmente.")
        return

    df_activos = df_telefonos[df_telefonos['activo'].astype(str).str.upper() == 'SI']

    # --- TARJETA 1: TELÉFONOS DE EMERGENCIA (Ancho Completo) ---
    st.markdown("""
        <div style="background-color: #fee2e2; border-left: 6px solid #dc2626; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="color: #991b1b; margin: 0; font-size: 1.25rem;">🚨 TELÉFONOS DE EMERGENCIA</h3>
        </div>
    """, unsafe_allow_html=True)

    df_emergencia = df_activos[df_activos['tarjeta'] == 'EMERGENCIA']
    
    if not df_emergencia.empty:
        # Mostramos en columnas horizontales para aprovechar todo el ancho
        cols = st.columns(len(df_emergencia) if len(df_emergencia) <= 4 else 3)
        for idx, (_, row) in enumerate(df_emergencia.iterrows()):
            with cols[idx % len(cols)]:
                st.markdown(f"""
                    <div style="background: white; border: 1px solid #fca5a5; padding: 12px; border-radius: 6px; text-align: center; margin-bottom: 10px;">
                        <strong style="color: #1f2937; font-size: 1rem;">{row['nombre']}</strong><br>
                        <a href="tel:{row['telefono']}" style="color: #dc2626; font-size: 1.15rem; font-weight: bold; text-decoration: none;">📞 {row['telefono']}</a>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.write("No hay teléfonos de emergencia registrados.")

    st.write("") # Espaciador

    # --- TARJETA 2: TELÉFONOS ÚTILES (Categorías Desplegables) ---
    st.markdown("""
        <div style="background-color: #f3f4f6; border-left: 6px solid #4b5563; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
            <h3 style="color: #1f2937; margin: 0; font-size: 1.25rem;">📞 TELÉFONOS ÚTILES</h3>
        </div>
    """, unsafe_allow_html=True)

    df_utiles = df_activos[df_activos['tarjeta'] == 'UTILES']

    # Orden predefinido de categorías solicitadas
    orden_categorias = ["Delivery", "Remises y transportes", "Servicios de obra"]
    categorias_presentes = list(df_utiles['categoria'].unique())
    
    # Combinar asegurando que las prioritarias queden primeras
    categorias_ordenadas = [c for c in orden_categorias if c in categorias_presentes]
    categorias_ordenadas += [c for c in categorias_presentes if c not in orden_categorias]

    if categorias_ordenadas:
        for cat in categorias_ordenadas:
            contactos_cat = df_utiles[df_utiles['categoria'] == cat]
            with st.expander(f"📁 {cat.upper()} ({len(contactos_cat)})", expanded=False):
                for _, item in contactos_cat.iterrows():
                    c_nombre, c_tel = st.columns([3, 2])
                    with c_nombre:
                        st.markdown(f"**{item['nombre']}**")
                    with c_tel:
                        st.markdown(f"[{item['telefono']}](tel:{item['telefono']})")
                    st.divider()
    else:
        st.write("No hay teléfonos útiles cargados.")


# -----------------------------------------------------------------------------
# 2. PANEL DE ADMINISTRADOR (?admin=si): ALTAS Y BAJAS
# -----------------------------------------------------------------------------
def admin_gestion_telefonos(df_telefonos: pd.DataFrame, api_url: str):
    st.markdown("### ⚙️ Administración de Directorio y Teléfonos")

    tab_alta, tab_baja = st.tabs(["➕ Dar de Alta", "❌ Dar de Baja"])

    with tab_alta:
        st.subheader("Nuevo Contacto")
        tarjeta_sel = st.selectbox("Seleccione la Tarjeta destino:", ["EMERGENCIA", "UTILES"])
        
        categoria_sel = "General"
        if tarjeta_sel == "UTILES":
            opciones_cat = ["Delivery", "Remises y transportes", "Servicios de obra", "➕ Nueva categoría..."]
            cat_choice = st.selectbox("Categoría:", opciones_cat)
            if cat_choice == "➕ Nueva categoría...":
                categoria_sel = st.text_input("Ingrese el nombre de la nueva categoría:")
            else:
                categoria_sel = cat_choice

        nombre = st.text_input("Nombre / Proveedor / Servicio:")
        telefono = st.text_input("Teléfono (ej: 11-1234-5678):")

        if st.button("Guardar en Google Sheets", type="primary"):
            if nombre and telefono:
                nuevo_registro = {
                    "action": "add_phone",
                    "tarjeta": tarjeta_sel,
                    "categoria": categoria_sel,
                    "nombre": nombre,
                    "telefono": telefono,
                    "activo": "SI"
                }
                # Aquí envías el payload por POST a tu SHEETS_API_URL
                # response = requests.post(api_url, json=nuevo_registro)
                st.success(f"Contacto '{nombre}' agregado exitosamente.")
                st.rerun()
            else:
                st.error("Por favor complete nombre y teléfono.")

    with tab_baja:
        st.subheader("Desactivar Contactos Existentes")
        activos = df_telefonos[df_telefonos['activo'].astype(str).str.upper() == 'SI']
        
        if not activos.empty:
            contacto_a_bajar = st.selectbox(
                "Seleccione el contacto que desea dar de baja:",
                activos['id'].tolist(),
                format_func=lambda x: f"[{activos.loc[activos['id']==x, 'tarjeta'].values[0]}] {activos.loc[activos['id']==x, 'nombre'].values[0]} ({activos.loc[activos['id']==x, 'telefono'].values[0]})"
            )
            
            if st.button("Confirmar Baja", type="secondary"):
                baja_payload = {
                    "action": "deactivate_phone",
                    "id": contacto_a_bajar
                }
                # requests.post(api_url, json=baja_payload)
                st.warning(f"Contacto ID {contacto_a_bajar} dado de baja.")
                st.rerun()
        else:
            st.info("No hay contactos activos para dar de baja.")
