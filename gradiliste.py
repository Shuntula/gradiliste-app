import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- INICIJALIZACIJA STANJA ---
if 'uredjivanje_cene' not in st.session_state:
    st.session_state.uredjivanje_cene = False

# --- STILIZACIJA (Poboljšan dizajn) ---
st.markdown("""
    <style>
    @keyframes blinking {
        0% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        50% { background-color: #58d68d; box-shadow: 0 0 20px #58d68d; }
        100% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
    }
    @keyframes subtle-green {
        0% { background-color: #1e7e34; opacity: 1; }
        50% { background-color: #28a745; opacity: 0.8; }
        100% { background-color: #1e7e34; opacity: 1; }
    }
    .trepcuce-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        color: white !important; animation: blinking 1.5s infinite;
        border: none !important; border-radius: 15px !important; width: 100% !important;
    }
    .blago-trepcuce-zeleno > div > button {
        height: 100px !important; font-size: 22px !important; font-weight: bold !important;
        color: white !important; animation: subtle-green 3s infinite;
        border: none !important; border-radius: 15px !important; width: 100% !important;
        pointer-events: none !important;
    }
    
    /* STILIZOVANO SIVO DUGME (STATUS NISTE PRIJAVLJENI) */
    .onemoguceno-dugme > div > button {
        height: 100px !important;
        background-color: #262730 !important; /* Tamna boja pozadine ekrana */
        color: #555 !important; /* Tamno siva slova */
        border: 1px solid #444 !important;
        border-radius: 15px !important;
        width: 100% !important;
        pointer-events: none !important;
        font-weight: bold !important;
        opacity: 0.8;
    }

    .odjava-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        background-color: #dc3545 !important; color: white !important;
        border-radius: 15px !important; width: 100% !important;
    }
    .label-radnik { font-size: 16px; color: #BBB; }
    .ime-radnika { font-size: 28px; font-weight: bold; color: #FFF; }
    .admin-naslov { font-size: 20px; font-weight: bold; margin-bottom: 15px; }
    .trosak-box { font-size: 24px; font-weight: bold; color: #FF4B4B; padding: 5px 10px; border: 2px solid #FF4B4B; border-radius: 10px; display: inline-block; }
    .trosak-mesec-box { font-size: 24px; font-weight: bold; color: #FFA500; padding: 5px 10px; border: 2px solid #FFA500; border-radius: 10px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

# --- POVEZIVANJE ---
@st.cache_resource
def povezi_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10)
def ucitaj_sve_podatke():
    client = povezi_google()
    sh = client.open("Baza Gradiliste")
    df_l = pd.DataFrame(sh.worksheet("log").get_all_records())
    df_k = pd
