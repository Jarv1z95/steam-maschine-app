import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import concurrent.futures
import requests
import re

# --- 1. KONFIGURATION ---
FIREBASE_URL = "https://geizhalslisten-81b9d-default-rtdb.europe-west1.firebasedatabase.app/steammachine.json"
EDIT_PIN = "1234"  # Hier kannst du deine Wunsch-PIN eintragen

# --- 2. DATENBANK LOGIK ---
def load_data():
    try:
        res = requests.get(FIREBASE_URL)
        if res.status_code == 200 and res.json():
            return res.json()
    except:
        pass
    return {"Konfig_A": [], "Konfig_B": []}

def save_data(data):
    requests.put(FIREBASE_URL, json=data)

# Verhindert, dass die App Daten beim Neuladen vergisst
if "db_data" not in st.session_state:
    st.session_state.db_data = load_data()

data = st.session_state.db_data

# --- 3. WUNSCHLISTEN-IMPORTER ---
def import_wishlist(url):
    if not url or "geizhals" not in url:
        return []
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        html = scraper.get(url, timeout=10).text
        soup = BeautifulSoup(html, 'html.parser')
        
        imported = []
        # Sucht im HTML der Wunschliste nach allen Produktlinks
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Geizhals-Produkte enden immer auf -a[Zahlen].html
            if re.search(r'-a\d+\.html$', href) or re.search(r'/\d+\.html$', href):
                name = a.text.strip()
                # Filtere leere Felder, Werbung oder Testberichte heraus
                if name and len(name) > 5 and name.lower() not in ["bewertung", "bewertungen", "preisverlauf"]:
                    full_link = "https://geizhals.de" + href if href.startswith('/') else href
                    # Vermeide doppelte Einträge
                    if not any(item['Link'] == full_link for item in imported):
                        # Als 'Komponente' wird erstmal 'Import' gesetzt (kannst du danach umbenennen)
                        imported.append({"Komponente": "Import", "Bezeichnung": name, "Link": full_link})
        return imported
    except:
        return []

# --- 4. STEAM DESIGN (CSS) ---
st.set_page_config(page_title="DIY Steam Machine", page_icon="🎮", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #1b2838; color: #c7d5e0; }
    h1, h2, h3 { color: #66c0f4 !important; font-family: sans-serif; }
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {
        background-color: #171a21; padding: 20px; border-radius: 6px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] { color: #a3cc27 !important; font-size: 2.5rem !important; font-weight: bold; }
    .steam-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;}
    .steam-table th { background-color: #101214; color: #66c0f4; text-align: left; padding: 10px; border-bottom: 2px solid #2a475e; }
    .steam-table td { padding: 10px; border-bottom: 1px solid #2a475e; color: #8f98a0; }
    .steam-table a { color: #66c0f4; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# --- 5. PREIS SCRAPER ---
@st.cache_data(ttl=1800)
def fetch_price(url):
    if not isinstance(url, str) or "geizhals" not in url: return 0.0
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        html = scraper.get(url, timeout=8).text
        price_span = BeautifulSoup(html, 'html.parser').find('span', class_='gh_g_price')
        if price_span: return float(price_span.text.replace('€', '').replace('.', '').replace(',', '.').strip())
    except: pass
    return 0.0

def get_all_prices(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(fetch_price, urls))

# --- 6. BENUTZEROBERFLÄCHE ---
st.title("🎮 DIY Steam Machine")
st.markdown("Live-Preisverfolgung über Geizhals.")

with st.sidebar:
    st.header("⚙️ Verwaltung")
    pin_input = st.text_input("PIN eingeben für Bearbeitungsmodus", type="password")
    edit_mode = (pin_input == EDIT_PIN)
    if pin_input and not edit_mode:
        st.error("Falsche PIN")

if edit_mode:
    st.success("Bearbeitungsmodus aktiv. Du kannst Konfigurationen hinzufügen, Wunschlisten importieren oder Daten bearbeiten.")
    
    if st.button("➕ Neue Konfiguration hinzufügen"):
        new_idx = len(data) + 1
        new_key = f"Konfig_{chr(64 + new_idx)}" if new_idx <= 26 else f"Konfig_{new_idx}"
        while new_key in data:
            new_idx += 1
            new_key = f"Konfig_{chr(64 + new_idx)}" if new_idx <= 26 else f"Konfig_{new_idx}"
        data[new_key] = []
        st.rerun()

    if data:
        tabs = st.tabs(list(data.keys()))
        edited_data = {}
        for tab, key in zip(tabs, data.keys()):
            with tab:
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.subheader(key.replace("_", " "))
                with col2:
                    if st.button("🗑️ Löschen", key=f"del_{key}"):
                        del data[key]
                        st.rerun()
                
                # Tabellen Editor
                df = pd.DataFrame(data[key]) if data[key] else pd.DataFrame(columns=["Komponente", "Bezeichnung", "Link"])
                edited_df = st.data_editor(df, num_rows="dynamic", key=f"edit_{key}", use_container_width=True)
                edited_data[key] = edited_df.to_dict('records')
                
                # Der neue Wunschlisten-Import-Bereich
                st.markdown("---")
                st.markdown("**📥 Komplette Wunschliste auslesen & anhängen**")
                wl_col1, wl_col2 = st.columns([0.7, 0.3])
                with wl_col1:
                    wl_link = st.text_input("Geizhals Link", label_visibility="collapsed", placeholder="https://geizhals.de/wishlists/...", key=f"wl_{key}")
                with wl_col2:
                    if st.button("Auslesen", key=f"btn_wl_{key}", use_container_width=True):
                        with st.spinner("Durchsuche Wunschliste..."):
                            new_items = import_wishlist(wl_link)
                            if new_items:
                                # Speichert vorherige manuelle Änderungen im Editor
                                data[key] = edited_df.to_dict('records')
                                # Hängt die neuen Produkte an
                                data[key].extend(new_items)
                                st.session_state.db_data = data
                                st.rerun()
                            else:
                                st.warning("Keine Komponenten gefunden oder Bot-Schutz aktiv.")
        
        st.markdown("---")
        if st.button("💾 Alle Änderungen speichern & Live schalten", type="primary"):
            save_data(edited_data)
            st.session_state.db_data = edited_data
            st.cache_data.clear()
            st.success("Gespeichert! Lösche die PIN links aus dem Feld, um die fertige Seite zu sehen.")
    else:
        st.info("Keine Konfigurationen vorhanden. Klicke auf 'Neue Konfiguration hinzufügen'.")

else:
    # Ansicht für deine Freunde
    if not data:
        st.info("Noch keine Hardware hinterlegt. PIN eingeben, um zu starten.")
    else:
        cols = st.columns(len(data))
        for col, key in zip(cols, data.keys()):
            with col:
                st.header(key.replace("_", " "))
                df = pd.DataFrame(data[key])
                if not df.empty and "Link" in df.columns:
                    urls = df["Link"].tolist()
                    with st.spinner("Lade Preise..."):
                        prices = get_all_prices(urls)
                    
                    df['Preis (€)'] = [f"{p:.2f} €" if p > 0 else "-" for p in prices]
                    df['Link'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Geizhals ↗</a>' if pd.notna(x) and x else "")
                    
                    st.markdown(df.to_html(index=False, escape=False, classes="steam-table"), unsafe_allow_html=True)
                    st.metric(label="Gesamtpreis (Live)", value=f"{sum(prices):.2f} €")
                else:
                    st.info("Noch keine Hardware hinterlegt.")
