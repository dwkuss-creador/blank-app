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
    como la respuesta plana anterior [[...], [...]] para garantizar total compatibilidad.
    """
    try:
        res = requests.get(API_URL, timeout=12)
        res.raise_for_status()
        payload = res.json()
        
        raw_vecinos = []
        raw_telefonos = []
        
        # 1. Si es un diccionario con la nueva estructura
        if isinstance(payload, dict):
            raw_vecinos = payload.get("vecinos", [])
            raw_telefonos = payload.get("telefonos", [])
        # 2. Si es una lista directa tradicional
        elif isinstance(payload, list):
            raw_vecinos = payload
            raw_telefonos = []
            
        return raw_vecinos, raw_telefonos
    except Exception as e:
        st.error(f"⚠️ Error al conectar con el servidor: {e}")
        return [], []

def procesar_vecinos(raw_vecinos):
    """Limpia, normaliza y ordena el padrón de vecinos."""
    if not raw_vecinos or len(raw_vecinos) < 2:
        return pd.DataFrame()
        
    headers = [str(c).strip().upper() for c in raw_vecinos[0]]
    df = pd.DataFrame(raw_vecinos[1:], columns=
