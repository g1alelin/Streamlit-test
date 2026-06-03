import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json
import hashlib
import os
import re
import requests
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# KONFIGURATION & SÖKVÄGSINSTÄLLNINGAR
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Närvaro & Registrering BI", layout="wide")

# Fil för att spara användardata (skapas automatiskt i appens mapp)
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

# Rollordning: 1:a kontot → Analytiker, 2:a → Rektor, 3:e → Samordnare
ROLE_ORDER = ["Analytiker (Full behörighet)", "Rektor (Annedalsskolan)", "Samordnare (Centrum)"]


# ─────────────────────────────────────────────────────────────────────────────
# AUTENTISERINGSFUNKTIONER
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hashar ett lösenord med SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users() -> dict:
    """Laddar användardatabasen från JSON-fil."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict):
    """Sparar användardatabasen till JSON-fil."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def register_user(email: str, password: str, name: str) -> tuple[bool, str]:
    """
    Registrerar en ny användare.
    Returnerar (True, roll) vid lyckat, (False, felmeddelande) vid misslyckande.
    """
    email = email.strip().lower()
    users = load_users()

    if email in users:
        return False, "Den e-postadressen är redan registrerad."

    if len(users) >= 3:
        return False, "Systemet tillåter max 3 konton. Kontakta administratören."

    if len(password) < 6:
        return False, "Lösenordet måste vara minst 6 tecken."

    # Tilldela roll baserat på registreringsordning
    role_index = len(users)  # 0 → Analytiker, 1 → Rektor, 2 → Samordnare
    assigned_role = ROLE_ORDER[role_index]

    users[email] = {
        "name": name.strip(),
        "password_hash": hash_password(password),
        "role": assigned_role,
        "registered_at": datetime.now().isoformat(),
        "registration_order": role_index + 1
    }
    save_users(users)
    return True, assigned_role


def login_user(email: str, password: str) -> tuple[bool, str, dict]:
    """
    Loggar in en användare.
    Returnerar (True, roll, användardata) vid lyckat, (False, felmeddelande, {}) vid misslyckande.
    """
    email = email.strip().lower()
    users = load_users()

    if email not in users:
        return False, "Ingen användare med den e-postadressen hittades.", {}

    user = users[email]
    if user["password_hash"] != hash_password(password):
        return False, "Felaktigt lösenord.", {}

    return True, user["role"], user


def get_registered_count() -> int:
    """Returnerar antal registrerade konton."""
    return len(load_users())


# ─────────────────────────────────────────────────────────────────────────────
# INLOGGNINGSSIDA (CSS + UI)
# ─────────────────────────────────────────────────────────────────────────────

def render_auth_page():
    """Renderar inloggnings-/registreringsgränssnittet."""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

        [data-testid="stHeader"]       { display: none !important; }
        [data-testid="stSidebar"]      { display: none !important; }
        [data-testid="stToolbar"]      { display: none !important; }
        [data-testid="stDecoration"]   { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }

        /* Mörkblå bakgrund på hela sidan */
        .stApp {
            background: linear-gradient(135deg, #0f1923 0%, #1c2d37 50%, #0d2133 100%) !important;
        }

        /* Block-container: ta bort sidopadding, lägg till vertikalt centrering via padding-top */
        .block-container {
            padding-top: 6vh !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        /* Det vita kortet — appliceras på mittkolumnens container */
        [data-testid="stVerticalBlock"] .auth-card-inner {
            background: #ffffff;
            border-radius: 12px;
            padding: 36px 40px 32px 40px;
            box-shadow: 0 24px 80px rgba(0,0,0,0.4);
        }

        /* Gör mittkolumnen till ett vitt kort */
        div[data-testid="column"]:nth-child(2) > div[data-testid="stVerticalBlock"] {
            background: #ffffff;
            border-radius: 12px;
            padding: 36px 40px 32px 40px !important;
            box-shadow: 0 24px 80px rgba(0,0,0,0.4);
        }

        /* Typografi & komponenter */
        .auth-logo {
            font-family: 'Playfair Display', serif;
            font-size: 26px;
            color: #0d2133;
            margin: 0 0 4px 0;
            letter-spacing: -0.5px;
        }
        .auth-logo span { color: #005c53; }
        .auth-subtitle {
            font-size: 13px;
            color: #64748b;
            margin: 0 0 24px 0;
        }
        .role-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 16px;
        }
        .role-badge.analytiker { background: #dcfce7; color: #166534; }
        .role-badge.rektor     { background: #dbeafe; color: #1e40af; }
        .role-badge.samordnare { background: #fef9c3; color: #854d0e; }
        .slots-info {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 16px;
            font-size: 12px;
            color: #64748b;
        }
        .slots-info .slot-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 3px 0;
        }
        .slot-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
        .slot-dot.taken     { background: #94a3b8; }
        .slot-dot.available { background: #22c55e; }
        </style>
    """, unsafe_allow_html=True)

    registered_count = get_registered_count()
    next_role = ROLE_ORDER[registered_count] if registered_count < 3 else None
    role_names = {
        "Analytiker (Full behörighet)": ("analytiker", "🔬 Analytiker — Full tillgång"),
        "Rektor (Annedalsskolan)":       ("rektor",     "🏫 Rektor — Annedalsskolan"),
        "Samordnare (Centrum)":          ("samordnare", "📍 Samordnare — Centrum"),
    }

    if "auth_tab" not in st.session_state:
        st.session_state.auth_tab = "login"

    # ── Tre kolumner: tom | kort | tom  (1 : 1.6 : 1) ──
    _, col_card, _ = st.columns([1, 1.6, 1])

    with col_card:
        # Logo & rubrik
        st.markdown('''
            <p class="auth-logo">Närvaro<span>BI</span></p>
            <p class="auth-subtitle">Göteborgs Stad · Närvaro & Registreringssystem</p>
        ''', unsafe_allow_html=True)

        # Tab-knappar
        col_tab1, col_tab2 = st.columns(2)
        with col_tab1:
            if st.button("🔑  Logga in", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "login" else "secondary"):
                st.session_state.auth_tab = "login"
                st.rerun()
        with col_tab2:
            if st.button("✨  Skapa konto", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "register" else "secondary"):
                st.session_state.auth_tab = "register"
                st.rerun()

        st.markdown("<hr style='margin: 14px 0 20px 0; border:0; border-top:1px solid #e2e8f0;'>",
                    unsafe_allow_html=True)

        # ── LOGGA IN (inuti col_card) ──
        if st.session_state.auth_tab == "login":
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("E-postadress", placeholder="din@email.se")
                password = st.text_input("Lösenord", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Logga in →", use_container_width=True, type="primary")

                if submitted:
                    if not email or not password:
                        st.error("Fyll i e-post och lösenord.")
                    else:
                        ok, result, user_data = login_user(email, password)
                        if ok:
                            st.session_state.authenticated = True
                            st.session_state.current_user_email = email
                            st.session_state.current_user_name = user_data["name"]
                            st.session_state.current_user_role = result
                            st.rerun()
                        else:
                            st.error(result)

        # ── REGISTRERA (inuti col_card) ──
        else:
            if registered_count >= 3:
                st.warning("⚠️ Alla tre roller är redan tilldelade. Kontakta administratören.")
            else:
                css_class, label = role_names[next_role]
                st.markdown(f'''
                    <p style="font-size:12px; color:#64748b; margin-bottom:6px; font-weight:500;">
                        Nästa konto tilldelas rollen:
                    </p>
                    <div class="role-badge {css_class}">{label}</div>
                ''', unsafe_allow_html=True)

                slot_html = '<div class="slots-info">'
                for i, role in enumerate(ROLE_ORDER):
                    taken = i < registered_count
                    dot_class = "taken" if taken else "available"
                    status = "Registrerad" if taken else ("← Du" if i == registered_count else "Ledig")
                    _, rl = role_names[role]
                    slot_html += f'<div class="slot-row"><div class="slot-dot {dot_class}"></div><span>{rl} — {status}</span></div>'
                slot_html += '</div>'
                st.markdown(slot_html, unsafe_allow_html=True)

                with st.form("register_form", clear_on_submit=False):
                    name = st.text_input("Ditt namn", placeholder="Anna Andersson")
                    email = st.text_input("E-postadress", placeholder="din@email.se")
                    password = st.text_input("Välj lösenord", type="password", placeholder="Minst 6 tecken")
                    password2 = st.text_input("Bekräfta lösenord", type="password", placeholder="Upprepa lösenordet")
                    submitted = st.form_submit_button("Skapa konto →", use_container_width=True, type="primary")

                    if submitted:
                        if not all([name, email, password, password2]):
                            st.error("Fyll i alla fält.")
                        elif password != password2:
                            st.error("Lösenorden stämmer inte överens.")
                        else:
                            ok, result = register_user(email, password, name)
                            if ok:
                                st.success(f"✅ Konto skapat! Din roll: **{result}**. Logga in nu.")
                                st.session_state.auth_tab = "login"
                                st.rerun()
                            else:
                                st.error(result)


# ─────────────────────────────────────────────────────────────────────────────
# KONTROLLERA INLOGGNINGSSTATUS
# ─────────────────────────────────────────────────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    render_auth_page()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# FRÅN HÄR: INLOGGAD APPLIKATION
# ─────────────────────────────────────────────────────────────────────────────

# Hämta inloggad roll (ersätter simuleringen)
anvandare = st.session_state.current_user_role
current_name = st.session_state.current_user_name
current_email = st.session_state.current_user_email


# ─────────────────────────────────────────────────────────────────────────────
# STYLING (QLIK SENSE-TEMA)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    [data-testid="stHeader"] { display: none !important; }
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
        margin-top: 0px !important;
    }
    .top-navbar {
        background: #1c2d37;
        padding: 8px 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 16px;
        border-radius: 4px;
    }
    .top-navbar-left {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
        color: #94a3b8;
    }
    .top-navbar-left strong { color: #ffffff; }
    .top-navbar-right {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
        color: #94a3b8;
    }
    .role-chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.4px;
    }
    .role-analytiker { background: #dcfce7; color: #166534; }
    .role-rektor     { background: #dbeafe; color: #1e40af; }
    .role-samordnare { background: #fef9c3; color: #854d0e; }
    .qlik-header {
        font-family: "Segoe UI", Helvetica, Arial, sans-serif;
        color: #1e1e1e;
        font-size: 22px;
        font-weight: 400;
        margin-top: 0px;
        margin-bottom: 15px;
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 5px;
    }
    .filter-label {
        font-size: 13px;
        color: #555555;
        font-weight: bold;
        margin-bottom: 2px;
        margin-top: 5px;
    }
    .kpi-box {
        background-color: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 3px;
        padding: 10px;
        text-align: left;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    .kpi-title { color: #595959; margin: 0; font-size: 12px; font-weight: normal; }
    .kpi-value-orange { font-size: 30px; font-weight: bold; color: #b84a39; margin: 0; }
    .kpi-value-dark   { font-size: 30px; font-weight: bold; color: #2c3e50; margin: 0; }
    .kpi-value-red    { font-size: 30px; font-weight: bold; color: #cc3333; margin: 0; }
    .filter-pill {
        background-color: #005c53;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        display: inline-block;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .placeholder-box {
        background-color: #f1f2f6;
        border: 1px dashed #ced6e0;
        padding: 30px;
        text-align: center;
        color: #57606f;
        font-size: 13px;
        border-radius: 4px;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TOPPMENY: INLOGGAD ANVÄNDARE + LOGGA UT
# ─────────────────────────────────────────────────────────────────────────────

def get_role_chip(role: str) -> str:
    if "Analytiker" in role:
        return f'<span class="role-chip role-analytiker">🔬 Analytiker</span>'
    elif "Rektor" in role:
        return f'<span class="role-chip role-rektor">🏫 Rektor</span>'
    elif "Samordnare" in role:
        return f'<span class="role-chip role-samordnare">📍 Samordnare</span>'
    return f'<span class="role-chip">{role}</span>'


nav_left, nav_right = st.columns([4, 1])
with nav_left:
    st.markdown(
        f'<div style="padding: 8px 0;">'
        f'<span style="font-family: Segoe UI; font-size: 13px; color: #555;">'
        f'Inloggad som <strong>{current_name}</strong> ({current_email})'
        f'</span>&nbsp;&nbsp;'
        f'{get_role_chip(anvandare)}'
        f'</div>',
        unsafe_allow_html=True
    )
with nav_right:
    if st.button("🚪 Logga ut", use_container_width=True):
        for key in ["authenticated", "current_user_email", "current_user_name",
                    "current_user_role", "clicked_month", "clicked_kon", "clicked_arvskurs"]:
            st.session_state.pop(key, None)
        st.rerun()

st.markdown("<hr style='margin: 0 0 10px 0; border: 0; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MÅNADSMAPPNINGAR
# ─────────────────────────────────────────────────────────────────────────────
MONTH_MAP = {
    8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec",
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Maj", 6: "Jun"
}
REV_MONTH_MAP = {v: k for k, v in MONTH_MAP.items()}


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE FÖR KLICK-FILTER
# ─────────────────────────────────────────────────────────────────────────────
if 'clicked_month' not in st.session_state:    st.session_state.clicked_month = None
if 'clicked_kon' not in st.session_state:      st.session_state.clicked_kon = None
if 'clicked_arvskurs' not in st.session_state: st.session_state.clicked_arvskurs = None


# ─────────────────────────────────────────────────────────────────────────────
# DATALADDNING
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def load_real_bi_data():
    csv_path = r"df_närvaro(Sheet 1).csv"
    shp_path = r"zip://Stadsområde_shp.zip"

    df = pd.read_csv(csv_path, sep=';', on_bad_lines='skip')
    df.columns = df.columns.str.strip()

    rename_map = {}
    for col in df.columns:
        c_low = col.lower()
        if 'enhets' in c_low:                          rename_map[col] = 'Enhetsnamn'
        elif 'total' in c_low and 'sche' in c_low:    rename_map[col] = 'Total_schemalagd_tid'
        elif 'närvarande' in c_low:                    rename_map[col] = 'Närvarande'
        elif 'ogiltig' in c_low:                       rename_map[col] = 'Ogiltig_frånvaro'
        elif 'giltig' in c_low:                        rename_map[col] = 'Giltig_frånvaro'
        elif 'ej' in c_low and 'registr' in c_low:    rename_map[col] = 'Ej_registrerat'
        elif 'månad' in c_low:                         rename_map[col] = 'Månad'
        elif 'årskurs' in c_low:                       rename_map[col] = 'Årskurs'
        elif 'skolform' in c_low:                      rename_map[col] = 'Skolform'
        elif 'kön' in c_low:                           rename_map[col] = 'Kön'

    df = df.rename(columns=rename_map)
    df = df.loc[:, ~df.columns.duplicated()].copy()

    target_cols = ['Total_schemalagd_tid', 'Närvarande', 'Giltig_frånvaro', 'Ogiltig_frånvaro', 'Ej_registrerat']
    for c in target_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.').str.strip(), errors='coerce')
        else:
            df[c] = 0.0
        df[c] = df[c].fillna(0.0)

    gdf_shp = None
    try:
        gdf_shp = gpd.read_file(shp_path)
        if gdf_shp.crs != "EPSG:4326":
            gdf_shp = gdf_shp.to_crs(epsg=4326)
        stadsdel_col = None
        for col in gdf_shp.columns:
            if col.lower() in ['namn', 'name', 'stadsomr', 'stadsområde', 'stadsdel', 'lnamn']:
                stadsdel_col = col
                break
        if stadsdel_col:
            gdf_shp = gdf_shp.rename(columns={stadsdel_col: 'Stadsområde'})
        else:
            gdf_shp['Stadsområde'] = "Område " + gdf_shp.index.astype(str)
    except Exception as e:
        st.sidebar.warning(f"Kunde inte läsa shapefil: {e}")

    if 'Enhetsnamn' in df.columns:
        def get_real_coordinates(school_name):
            name = str(school_name).strip().lower()
            if 'annedal' in name:   return 57.6901, 11.9612
            if 'haga' in name:      return 57.6978, 11.9543
            if 'backa' in name:     return 57.7412, 11.9764
            if 'torslanda' in name: return 57.7215, 11.7780
            if 'angered' in name:   return 57.7915, 12.0460
            seed_val = sum(ord(char) * (i + 1) for i, char in enumerate(name))
            lat = 57.64 + ((seed_val * 17) % 100) * 0.0015
            lon = 11.86 + ((seed_val * 31) % 120) * 0.0018
            return lat, lon

        coords = df['Enhetsnamn'].apply(get_real_coordinates)
        df['Latitude']  = [c[0] for c in coords]
        df['Longitude'] = [c[1] for c in coords]

        if gdf_shp is not None and not gdf_shp.empty:
            schools_geo = gpd.GeoDataFrame(
                df[['Enhetsnamn', 'Latitude', 'Longitude']].drop_duplicates(),
                geometry=gpd.points_from_xy(
                    df.drop_duplicates('Enhetsnamn').Longitude,
                    df.drop_duplicates('Enhetsnamn').Latitude
                ),
                crs="EPSG:4326"
            )
            sj = gpd.sjoin(schools_geo, gdf_shp[['Stadsområde', 'geometry']], how='left', predicate='within')
            area_map = dict(zip(sj['Enhetsnamn'], sj['Stadsområde'].fillna('Centrum')))
            df['Stadsområde'] = df['Enhetsnamn'].map(area_map)
        else:
            df['Stadsområde'] = 'Centrum'
    else:
        df['Latitude'] = 57.708; df['Longitude'] = 11.974; df['Stadsområde'] = 'Centrum'

    return df, gdf_shp


df_raw_att, gdf_shapefil = load_real_bi_data()
df_qlik = df_raw_att.copy()


# ─────────────────────────────────────────────────────────────────────────────
# ROW-LEVEL SECURITY baserad på inloggad roll
# ─────────────────────────────────────────────────────────────────────────────
allowed_tabs = []

if anvandare == "Analytiker (Full behörighet)":
    allowed_tabs = ["Ofullständiga Registreringar", "Översikt - Närvaro", "Karta (Geografisk vy)", "🤖 AI-Assistent"]

elif anvandare == "Rektor (Annedalsskolan)":
    allowed_tabs = ["Ofullständiga Registreringar", "Översikt - Närvaro", "🤖 AI-Assistent"]
    skolor_match = [x for x in df_qlik['Enhetsnamn'].dropna().unique() if 'annedal' in x.lower()]
    skola_id = skolor_match[0] if skolor_match else df_qlik['Enhetsnamn'].iloc[0]
    df_qlik = df_qlik[df_qlik['Enhetsnamn'] == skola_id]

elif anvandare == "Samordnare (Centrum)":
    allowed_tabs = ["Översikt - Närvaro", "Karta (Geografisk vy)", "🤖 AI-Assistent"]
    df_qlik = df_qlik[df_qlik['Stadsområde'] == "Centrum"]


# ─────────────────────────────────────────────────────────────────────────────
# SKAPA FLIKAR DYNAMISKT
# ─────────────────────────────────────────────────────────────────────────────
tabs = st.tabs(allowed_tabs)
tab2, tab3, tab_map, tab_ai = None, None, None, None
for i, flik_namn in enumerate(allowed_tabs):
    if flik_namn == "Ofullständiga Registreringar": tab2 = tabs[i]
    elif flik_namn == "Översikt - Närvaro":         tab3 = tabs[i]
    elif flik_namn == "Karta (Geografisk vy)":      tab_map = tabs[i]
    elif flik_namn == "🤖 AI-Assistent":             tab_ai = tabs[i]


# ─────────────────────────────────────────────────────────────────────────────
# DELAD FILTERFUNKTION
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar_filters(df_current, unique_key_suffix):
    is_overview_flag = True

    # Stadsområde
    st.markdown('<p class="filter-label">Stadsområde</p>', unsafe_allow_html=True)
    if anvandare == "Samordnare (Centrum)":
        st.selectbox("", ["Centrum"], key=f"sf1_{unique_key_suffix}",
                     label_visibility="collapsed", disabled=True)
    else:
        stads_opts = ["Alla områden"] + sorted([str(x) for x in df_raw_att['Stadsområde'].dropna().unique()])
        v_stads = st.selectbox("", stads_opts, key=f"sf1_{unique_key_suffix}", label_visibility="collapsed")
        if v_stads != "Alla områden":
            df_current = df_current[df_current['Stadsområde'] == v_stads]

    # Skolhus
    st.markdown('<p class="filter-label">Skolhus</p>', unsafe_allow_html=True)
    if "Rektor" in anvandare:
        aktuell_skola = df_current['Enhetsnamn'].unique()[0] if not df_current.empty else "Annedalsskolan"
        st.selectbox("", [aktuell_skola], key=f"sf2_{unique_key_suffix}",
                     label_visibility="collapsed", disabled=True)
        is_overview_flag = False
    else:
        skolhus_lista = sorted([str(x) for x in df_current['Enhetsnamn'].unique()])
        v_skolhus = st.selectbox("", ["--- Visa översikt (Inget val) ---"] + skolhus_lista,
                                 key=f"sf2_{unique_key_suffix}", label_visibility="collapsed")
        is_overview_flag = (v_skolhus == "--- Visa översikt (Inget val) ---")
        if not is_overview_flag:
            df_current = df_current[df_current['Enhetsnamn'] == v_skolhus]

    # Skolform
    st.markdown('<p class="filter-label">Skolform</p>', unsafe_allow_html=True)
    form_opts = ["Alla skolformer"] + sorted([str(x) for x in df_raw_att['Skolform'].dropna().unique()])
    v_skolform = st.selectbox("", form_opts, key=f"sf3_{unique_key_suffix}", label_visibility="collapsed")
    if v_skolform != "Alla skolformer":
        df_current = df_current[df_current['Skolform'] == v_skolform]

    # Kön
    st.markdown('<p class="filter-label">Kön</p>', unsafe_allow_html=True)
    kon_opts = ["Samtliga"] + sorted([str(x) for x in df_raw_att['Kön'].dropna().unique()])
    v_kon = st.selectbox("", kon_opts, key=f"sf4_{unique_key_suffix}", label_visibility="collapsed")
    if v_kon != "Samtliga":
        df_current = df_current[df_current['Kön'] == v_kon]

    # Månad
    st.markdown('<p class="filter-label">Månad (Filter)</p>', unsafe_allow_html=True)
    sorted_months = sorted(df_raw_att['Månad'].dropna().unique())
    month_opts = ["Alla månader"] + [MONTH_MAP[m] for m in sorted_months if m in MONTH_MAP]
    v_manad = st.selectbox("", month_opts, key=f"sf5_{unique_key_suffix}", label_visibility="collapsed")
    if v_manad != "Alla månader":
        df_current = df_current[df_current['Månad'] == REV_MONTH_MAP[v_manad]]

    # Klick-filter från diagram
    if st.session_state.clicked_month:
        df_current = df_current[df_current['Månad'] == REV_MONTH_MAP.get(st.session_state.clicked_month, 0)]
    if st.session_state.clicked_kon:
        df_current = df_current[df_current['Kön'] == st.session_state.clicked_kon]
    if st.session_state.clicked_arvskurs:
        df_current = df_current[df_current['Årskurs'].astype(int).astype(str) == str(st.session_state.clicked_arvskurs)]

    return df_current, is_overview_flag


# ─────────────────────────────────────────────────────────────────────────────
# GEMENSAM FUNKTION FÖR STACKED BARS
# ─────────────────────────────────────────────────────────────────────────────
def create_stacked_bar(df_grouped, x_col, height_val=200):
    totals = (df_grouped['Närvarande'] + df_grouped['Giltig_frånvaro'] + df_grouped['Ogiltig_frånvaro']).replace(0, 1)
    p_när = df_grouped['Närvarande'] / totals * 100
    p_gil = df_grouped['Giltig_frånvaro'] / totals * 100
    p_ogi = df_grouped['Ogiltig_frånvaro'] / totals * 100

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_grouped[x_col], y=p_när, name='Närvaro',
                         marker_color='#3a4d5c',
                         text=[f"{v:.1f}%" if v > 5 else "" for v in p_när], textposition='auto'))
    fig.add_trace(go.Bar(x=df_grouped[x_col], y=p_gil, name='Giltig frånvaro',
                         marker_color='#ffcc00',
                         text=[f"{v:.1f}%" if v > 3 else "" for v in p_gil], textposition='auto'))
    fig.add_trace(go.Bar(x=df_grouped[x_col], y=p_ogi, name='Ogiltig frånvaro',
                         marker_color='#e53e3e',
                         text=[f"{v:.1f}%" if v > 0.5 else "" for v in p_ogi], textposition='auto'))

    fig.update_layout(barmode='stack', height=height_val,
                      margin=dict(l=10, r=10, t=10, b=10),
                      showlegend=False,
                      yaxis=dict(range=[0, 110], ticksuffix="%"))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: OFULLSTÄNDIGA REGISTRERINGAR
# ─────────────────────────────────────────────────────────────────────────────
if tab2:
    with tab2:
        st.markdown('<p class="qlik-header">Ofullständiga Registreringar</p>', unsafe_allow_html=True)
        vy_typ = st.radio("Välj visualiseringstyp:",
                          options=["📊 Standard (Diagram)", "🧮 Pivot-tabell (Flexibel vy)"],
                          horizontal=True, key="v2")

        col_l2, col_r2 = st.columns([1, 4])
        with col_l2:
            df_tab2, is_overview2 = render_sidebar_filters(df_qlik, "tab2")

        with col_r2:
            if not df_tab2.empty:
                t_sche = float(df_tab2['Total_schemalagd_tid'].sum())
                t_ej   = float(df_tab2['Ej_registrerat'].sum())
                pct_ej = f"{((t_ej / t_sche) * 100):.1f}%" if t_sche > 0 else "0.0%"

                kpi_col1, _ = st.columns([1, 3])
                with kpi_col1:
                    st.markdown(
                        f'<div class="kpi-box">'
                        f'<p class="kpi-title">Totala Ofullständiga Reg...</p>'
                        f'<p class="kpi-value-red">{pct_ej}</p>'
                        f'</div>', unsafe_allow_html=True)

                if vy_typ == "📊 Standard (Diagram)":
                    df_m = df_tab2.groupby('Månad').sum(numeric_only=True).reset_index()
                    df_m['Procent']     = (df_m['Ej_registrerat'] / df_m['Total_schemalagd_tid'].replace(0, 1)) * 100
                    df_m['Månadsnamn']  = df_m['Månad'].map(MONTH_MAP)
                    df_m = df_m.dropna(subset=['Månadsnamn']).sort_values('Månad')

                    fig_m = go.Figure(data=[go.Bar(
                        x=df_m['Månadsnamn'], y=df_m['Procent'],
                        text=[f"{v:.1f}%" if v > 0 else "" for v in df_m['Procent']],
                        textposition='auto', marker_color='#005c53'
                    )])
                    fig_m.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10),
                                        yaxis=dict(ticksuffix="%"))
                    st.plotly_chart(fig_m, use_container_width=True)

                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if is_overview2:
                            st.markdown('<div class="placeholder-box">Välj ett skolhus i menyn för att generera klassrapport</div>',
                                        unsafe_allow_html=True)
                        else:
                            classes = ["1A", "1B", "2A", "2B", "3A", "3B"]
                            fig_c = go.Figure(data=[go.Bar(x=classes, y=[5.2, 4.8, 6.1, 5.9, 7.2, 4.1],
                                                           marker_color='#008a55')])
                            fig_c.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10))
                            st.plotly_chart(fig_c, use_container_width=True)
                    with col_b2:
                        df_g = df_tab2.groupby('Årskurs').sum(numeric_only=True).reset_index()
                        df_g['Procent']     = (df_g['Ej_registrerat'] / df_g['Total_schemalagd_tid'].replace(0, 1)) * 100
                        df_g['Årskurs_str'] = df_g['Årskurs'].astype(int).astype(str)
                        fig_g = go.Figure(data=[go.Bar(
                            x=df_g['Årskurs_str'], y=df_g['Procent'],
                            text=[f"{v:.1f}%" for v in df_g['Procent']],
                            textposition='auto', marker_color='#008a55'
                        )])
                        fig_g.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10))
                        st.plotly_chart(fig_g, use_container_width=True)
                else:
                    pivot_rad = st.selectbox("Välj rad-dimension:",
                                             options=["Enhetsnamn", "Stadsområde", "Årskurs", "Skolform"],
                                             key="p_r")
                    df_pivot = df_tab2.groupby(pivot_rad).sum(numeric_only=True).reset_index()
                    df_pivot['Ofullständiga (%)'] = ((df_pivot['Ej_registrerat'] /
                                                      df_pivot['Total_schemalagd_tid'].replace(0, 1)) * 100).round(1)
                    st.dataframe(df_pivot[[pivot_rad, 'Total_schemalagd_tid', 'Ej_registrerat', 'Ofullständiga (%)']],
                                 use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: ÖVERSIKT - NÄRVARO
# ─────────────────────────────────────────────────────────────────────────────
if tab3:
    with tab3:
        st.markdown('<p class="qlik-header">Översikt - Närvaro/Frånvaro</p>', unsafe_allow_html=True)

        if st.session_state.clicked_month or st.session_state.clicked_kon or st.session_state.clicked_arvskurs:
            pill_html = "<b>Aktiva val i diagram:</b> "
            if st.session_state.clicked_month:
                pill_html += f"<span class='filter-pill'>Månad: {st.session_state.clicked_month}</span>"
            if st.session_state.clicked_kon:
                pill_html += f"<span class='filter-pill'>Kön: {st.session_state.clicked_kon}</span>"
            if st.session_state.clicked_arvskurs:
                pill_html += f"<span class='filter-pill'>Årskurs: {st.session_state.clicked_arvskurs}</span>"
            st.markdown(pill_html, unsafe_allow_html=True)
            if st.button("Rensa alla klick-filter", type="primary"):
                st.session_state.clicked_month    = None
                st.session_state.clicked_kon      = None
                st.session_state.clicked_arvskurs = None
                st.rerun()

        col_l3, col_r3 = st.columns([1, 4])
        with col_l3:
            df_tab3, is_overview3 = render_sidebar_filters(df_qlik, "tab3_new")

        with col_r3:
            if not df_tab3.empty:
                t_sche3 = float(df_tab3['Total_schemalagd_tid'].sum())
                if t_sche3 > 0:
                    pct_närvaro = float(df_tab3['Närvarande'].sum() / t_sche3 * 100)
                    pct_giltig  = float(df_tab3['Giltig_frånvaro'].sum() / t_sche3 * 100)
                    pct_ogiltig = float(df_tab3['Ogiltig_frånvaro'].sum() / t_sche3 * 100)
                else:
                    pct_närvaro = pct_giltig = pct_ogiltig = 0.0

                top_row_left, top_row_right = st.columns([1, 3])
                with top_row_left:
                    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Total Närvaro %</p><p class="kpi-value-orange">{pct_närvaro:.1f}%</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Giltig Frånvaro %</p><p class="kpi-value-dark">{pct_giltig:.1f}%</p></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Ogiltig Frånvaro %</p><p class="kpi-value-red">{pct_ogiltig:.1f}%</p></div>', unsafe_allow_html=True)

                with top_row_right:
                    df_m3 = df_tab3.groupby('Månad').sum(numeric_only=True).reset_index()
                    df_m3['Månadsnamn'] = df_m3['Månad'].map(MONTH_MAP)
                    df_m3 = df_m3.dropna(subset=['Månadsnamn']).sort_values('Månad')

                    fig_m = create_stacked_bar(df_m3, 'Månadsnamn', height_val=210)
                    select_m = st.plotly_chart(fig_m, use_container_width=True,
                                               on_select="rerun", key="click_month_chart")
                    if select_m and select_m.get("selection", {}).get("points"):
                        clicked_val = select_m["selection"]["points"][0]["x"]
                        if st.session_state.clicked_month != clicked_val:
                            st.session_state.clicked_month = clicked_val
                            st.rerun()

                st.markdown("<hr style='margin: 10px 0; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

                bottom_row_left, bottom_row_right = st.columns([2, 3])
                with bottom_row_left:
                    st.markdown("<p style='font-size:12px; font-weight:bold; margin-bottom:2px; color:#555;'>Uppdelat per Kön</p>", unsafe_allow_html=True)
                    df_k3 = df_tab3.groupby('Kön').sum(numeric_only=True).reset_index()
                    if not df_k3.empty:
                        fig_k = create_stacked_bar(df_k3, 'Kön', height_val=210)
                        select_k = st.plotly_chart(fig_k, use_container_width=True,
                                                   on_select="rerun", key="click_kon_chart")
                        if select_k and select_k.get("selection", {}).get("points"):
                            clicked_val = select_k["selection"]["points"][0]["x"]
                            if st.session_state.clicked_kon != clicked_val:
                                st.session_state.clicked_kon = clicked_val
                                st.rerun()
                    else:
                        st.info("Ingen könsuppdelad data tillgänglig.")

                with bottom_row_right:
                    st.markdown("<p style='font-size:12px; font-weight:bold; margin-bottom:2px; color:#555;'>Uppdelat per Årskurs</p>", unsafe_allow_html=True)
                    df_a3 = df_tab3.groupby('Årskurs').sum(numeric_only=True).reset_index()
                    if not df_a3.empty:
                        df_a3['Årskurs_str'] = df_a3['Årskurs'].astype(int).astype(str)
                        df_a3 = df_a3.sort_values('Årskurs')
                        fig_a = create_stacked_bar(df_a3, 'Årskurs_str', height_val=210)
                        select_a = st.plotly_chart(fig_a, use_container_width=True,
                                                   on_select="rerun", key="click_arv_chart")
                        if select_a and select_a.get("selection", {}).get("points"):
                            clicked_val = select_a["selection"]["points"][0]["x"]
                            if st.session_state.clicked_arvskurs != clicked_val:
                                st.session_state.clicked_arvskurs = clicked_val
                                st.rerun()
                    else:
                        st.info("Ingen årskursdata tillgänglig.")
            else:
                st.warning("Ingen data hittades för valda filter.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: KARTA (GEOGRAFISK FÖRDELNING)
# ─────────────────────────────────────────────────────────────────────────────

if tab_map:
    with tab_map:

        st.markdown(
            '<p class="qlik-header">Geografisk Fördelning (Stadsområden & Skolhus)</p>',
            unsafe_allow_html=True
        )

        col_lmap, col_rmap = st.columns([1, 4])

        # ======================================================
        # FILTERPANEL
        # ======================================================

        with col_lmap:
            df_map, _ = render_sidebar_filters(
                df_qlik,
                "tab_map"
            )

        # ======================================================
        # KARTA + METABASE
        # ======================================================

        with col_rmap:

            if not df_map.empty:

                # ==================================================
                # METABASE DASHBOARD
                # ==================================================
                st.subheader("Närvarostatistik från Metabase")

                metabase_url = "http://metabase-609ip-gsf-analyslager.apps.k8sp.gbgpaas.se/public/dashboard/c53a6382-2d8d-43cd-9984-7ee349614f56"

                # Skapa en standard iFrame-ruta i appen
                st.components.v1.iframe(metabase_url, height=800, scrolling=True)
                st.divider()

                # ==================================================
                # FOLIUM KARTA
                # ==================================================

                m = folium.Map(
                    location=[57.708, 11.974],
                    zoom_start=11,
                    tiles="OpenStreetMap"
                )

                # ==================================================
                # STADSOMRÅDEN
                # ==================================================

                if (
                    gdf_shapefil is not None
                    and not gdf_shapefil.empty
                ):

                    unique_areas = sorted(
                        list(
                            gdf_shapefil[
                                "Stadsområde"
                            ].unique()
                        )
                    )

                    colors_palette = [
                        "#f5b7b1",
                        "#aed6f1",
                        "#f9e79f",
                        "#a9dfbf",
                        "#d2b4de",
                        "#f5cba7",
                        "#e8daef"
                    ]

                    area_color_map = {

                        area:
                        colors_palette[
                            i % len(colors_palette)
                        ]

                        for i, area in enumerate(
                            unique_areas
                        )
                    }

                    folium.GeoJson(

                        gdf_shapefil,

                        style_function=lambda x: {

                            "fillColor":
                            area_color_map.get(
                                x["properties"][
                                    "Stadsområde"
                                ],
                                "#3a4d5c"
                            ),

                            "color":
                            "#2c3e50",

                            "weight":
                            1.5,

                            "fillOpacity":
                            0.35
                        },

                        tooltip=folium.GeoJsonTooltip(
                            fields=["Stadsområde"],
                            aliases=["Stadsområde:"]
                        )

                    ).add_to(m)

                # ==================================================
                # SKOLOR
                # ==================================================

                df_schools = (

                    df_map

                    .groupby(
                        [
                            "Enhetsnamn",
                            "Latitude",
                            "Longitude"
                        ]
                    )

                    .sum(
                        numeric_only=True
                    )

                    .reset_index()

                )

                for _, row in df_schools.iterrows():

                    total = (

                        row["Närvarande"]

                        + row["Giltig_frånvaro"]

                        + row["Ogiltig_frånvaro"]

                    )

                    pct_n = (

                        row["Närvarande"] / total * 100

                        if total > 0

                        else 0

                    )

                    pct_g = (

                        row["Giltig_frånvaro"] / total * 100

                        if total > 0

                        else 0

                    )

                    pct_o = (

                        row["Ogiltig_frånvaro"] / total * 100

                        if total > 0

                        else 0

                    )

                    tooltip_html = f"""
                    <div style='font-family:Arial;font-size:12px;width:230px;'>

                        <h4 style='margin-bottom:5px;'>
                            {row['Enhetsnamn']}
                        </h4>

                        <table style='width:100%;'>

                            <tr>
                                <td>Närvaro</td>
                                <td style='text-align:right;color:green;'>
                                    {pct_n:.1f}%
                                </td>
                            </tr>

                            <tr>
                                <td>Giltig frånvaro</td>
                                <td style='text-align:right;'>
                                    {pct_g:.1f}%
                                </td>
                            </tr>

                            <tr>
                                <td>Ogiltig frånvaro</td>
                                <td style='text-align:right;color:red;'>
                                    {pct_o:.1f}%
                                </td>
                            </tr>

                            <tr>
                                <td>Ogiltiga timmar</td>
                                <td style='text-align:right;'>
                                    {int(row['Ogiltig_frånvaro'])}
                                </td>
                            </tr>

                            <tr>
                                <td>Ej registrerat</td>
                                <td style='text-align:right;'>
                                    {int(row['Ej_registrerat'])}
                                </td>
                            </tr>

                        </table>

                    </div>
                    """

                    marker_color = (

                        "#008a55"

                        if pct_n > 90

                        else "#ffcc00"

                        if pct_n > 80

                        else "#e53e3e"

                    )

                    folium.CircleMarker(

                        location=[
                            row["Latitude"],
                            row["Longitude"]
                        ],

                        radius=9,

                        tooltip=folium.Tooltip(
                            tooltip_html,
                            sticky=True
                        ),

                        color="#1c2d37",

                        weight=1.5,

                        fill=True,

                        fill_color=marker_color,

                        fill_opacity=0.85

                    ).add_to(m)

                # ==================================================
                # VISA KARTA
                # ==================================================

                st_folium(
                    m,
                    width="100%",
                    height=650,
                    returned_objects=[]
                )

            else:

                st.warning(
                    "Ingen geografisk data tillgänglig för valda filter."
                )

# ─────────────────────────────────────────────────────────────────────────────
# 🤖 AI-ASSISTENT (METABOT-LIKNANDE)
# ─────────────────────────────────────────────────────────────────────────────

def build_data_context(df: pd.DataFrame, role: str) -> str:
    """
    Bygger en komprimerad textsammanfattning av datan för LLM-kontexten.
    Skickar ALDRIG rådata — endast aggregerade statistikvärden.
    """
    lines = [f"## Datakontext för roll: {role}"]
    lines.append(f"Antal rader i filtrerad dataset: {len(df)}")
    lines.append(f"Tidsperiod (månader): {sorted(df['Månad'].dropna().unique().tolist())}")

    num_cols = ['Total_schemalagd_tid', 'Närvarande', 'Giltig_frånvaro', 'Ogiltig_frånvaro', 'Ej_registrerat']

    # Totaler
    totals = {c: float(df[c].sum()) for c in num_cols if c in df.columns}
    tot_sche = totals.get('Total_schemalagd_tid', 1) or 1
    lines.append("\n### Totala summor (timmar)")
    for k, v in totals.items():
        lines.append(f"- {k}: {v:,.0f}")
    lines.append(f"\n### Nyckeltal (% av schemalagd tid)")
    lines.append(f"- Närvaro: {totals.get('Närvarande',0)/tot_sche*100:.1f}%")
    lines.append(f"- Giltig frånvaro: {totals.get('Giltig_frånvaro',0)/tot_sche*100:.1f}%")
    lines.append(f"- Ogiltig frånvaro: {totals.get('Ogiltig_frånvaro',0)/tot_sche*100:.1f}%")
    lines.append(f"- Ofullständiga registreringar: {totals.get('Ej_registrerat',0)/tot_sche*100:.1f}%")

    # Per månad
    if 'Månad' in df.columns:
        MONTH_NAMES = {8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec",1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Maj",6:"Jun"}
        dm = df.groupby('Månad')[num_cols].sum().reset_index()
        lines.append("\n### Aggregerat per månad")
        for _, row in dm.iterrows():
            ts = float(row.get('Total_schemalagd_tid', 1)) or 1
            mname = MONTH_NAMES.get(int(row['Månad']), str(int(row['Månad'])))
            lines.append(
                f"- {mname}: Närvaro {row.get('Närvarande',0)/ts*100:.1f}%, "
                f"Ogiltig {row.get('Ogiltig_frånvaro',0)/ts*100:.1f}%, "
                f"Ej reg {row.get('Ej_registrerat',0)/ts*100:.1f}%"
            )

    # Per skola (max 20)
    if 'Enhetsnamn' in df.columns:
        ds = df.groupby('Enhetsnamn')[num_cols].sum().reset_index()
        ds['pct_när'] = ds.get('Närvarande', 0) / (ds.get('Total_schemalagd_tid', 1).replace(0,1)) * 100
        ds['pct_ogi'] = ds.get('Ogiltig_frånvaro', 0) / (ds.get('Total_schemalagd_tid', 1).replace(0,1)) * 100
        lines.append(f"\n### Per skola (topp efter ogiltig frånvaro, max 15 visas)")
        for _, row in ds.nlargest(15, 'pct_ogi').iterrows():
            lines.append(f"- {row['Enhetsnamn']}: Närvaro {row['pct_när']:.1f}%, Ogiltig {row['pct_ogi']:.1f}%")

    # Per kön
    if 'Kön' in df.columns:
        dk = df.groupby('Kön')[num_cols].sum().reset_index()
        lines.append("\n### Per kön")
        for _, row in dk.iterrows():
            ts = float(row.get('Total_schemalagd_tid', 1)) or 1
            lines.append(
                f"- {row['Kön']}: Närvaro {row.get('Närvarande',0)/ts*100:.1f}%, "
                f"Ogiltig {row.get('Ogiltig_frånvaro',0)/ts*100:.1f}%"
            )

    # Per årskurs
    if 'Årskurs' in df.columns:
        da = df.groupby('Årskurs')[num_cols].sum().reset_index().sort_values('Årskurs')
        lines.append("\n### Per årskurs")
        for _, row in da.iterrows():
            ts = float(row.get('Total_schemalagd_tid', 1)) or 1
            lines.append(
                f"- Årskurs {int(row['Årskurs'])}: Närvaro {row.get('Närvarande',0)/ts*100:.1f}%, "
                f"Ogiltig {row.get('Ogiltig_frånvaro',0)/ts*100:.1f}%"
            )

    return "\n".join(lines)


def safe_execute_plotly(code: str, df: pd.DataFrame) -> go.Figure | None:
    """
    Kör LLM-genererad Plotly-kod i en isolerad namnrymd.
    Tillåter endast go., px. och pandas-operationer på aggregerad data.
    """
    # Säkerhetsfilter: blockera farliga anrop
    blocked = ["import ", "open(", "os.", "sys.", "subprocess", "eval(", "exec(", "__"]
    for b in blocked:
        if b in code:
            return None

    # Bygg aggregerade dataframes som koden kan använda
    MONTH_NAMES = {8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec",1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"Maj",6:"Jun"}
    num_cols = ['Total_schemalagd_tid', 'Närvarande', 'Giltig_frånvaro', 'Ogiltig_frånvaro', 'Ej_registrerat']

    df_manad = df.groupby('Månad')[num_cols].sum().reset_index()
    df_manad['Månadsnamn'] = df_manad['Månad'].map(MONTH_NAMES)
    df_manad = df_manad.dropna(subset=['Månadsnamn']).sort_values('Månad')

    df_skola = df.groupby('Enhetsnamn')[num_cols].sum().reset_index() if 'Enhetsnamn' in df.columns else pd.DataFrame()
    df_kon   = df.groupby('Kön')[num_cols].sum().reset_index() if 'Kön' in df.columns else pd.DataFrame()
    df_arsk  = df.groupby('Årskurs')[num_cols].sum().reset_index().sort_values('Årskurs') if 'Årskurs' in df.columns else pd.DataFrame()
    if not df_arsk.empty:
        df_arsk['Årskurs_str'] = df_arsk['Årskurs'].astype(int).astype(str)

    namespace = {
        "go": go, "px": px, "pd": pd,
        "df_manad": df_manad, "df_skola": df_skola,
        "df_kon": df_kon, "df_arsk": df_arsk,
        "fig": None
    }
    try:
        exec(code, namespace)  # noqa: S102
        return namespace.get("fig")
    except Exception as e:
        st.error(f"Fel vid diagramgenerering: {e}")
        return None


def check_ollama_connection(base_url: str) -> tuple[bool, list[str]]:
    """
    Kontrollerar om Ollama körs lokalt och returnerar tillgängliga modeller.
    Ingen data skickas — enbart ett ping mot localhost.
    """
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
        return False, []
    except Exception:
        return False, []


def call_ollama(history, data_ctx, url, model):
    import json
    import re

    system_message = {
        "role": "system",
        "content": (
            f"DATAKONTEXT:\n{data_ctx}\n\n"
            "Uppgift: Du är en BI-assistent som analyserar skolnärvaro. Svara alltid på svenska.\n"
            "KRAV: Du MÅSTE svara med ett strikt JSON-objekt. Skriv ingen text utanför JSON-objektet.\n\n"
            "JSON-STRUKTUREN SKA SE UT EXAKT SÅ HÄR:\n"
            "{\n"
            "  \"explanation\": \"Din analys och svar på användarens fråga skrivs här.\",\n"
            "  \"chart_code\": \"\"\n"
            "}\n\n"
            "REGLER FÖR DIAGRAMKOD ('chart_code'):\n"
            "1. Om användaren ber om ett diagram, skriv ren Plotly-kod här (t.ex: fig = px.bar(df, x='Årskurs', y='Närvarande')).\n"
            "2. DU FÅR ALDRIG skriva 'df = ...' eller ladda in data. Variabeln 'df' finns redan!\n"
            "3. Skapa bara diagrammet och spara det i variabeln 'fig'.\n"
            "4. Om användaren INTE ber om ett diagram, lämna fältet tomt (\"\").\n"
        )
    }

    messages = [system_message] + history
    try:
        response = requests.post(
            f"{url}/api/chat",
            json={"model": model, "messages": messages, "stream": False, "format": "json"},
            timeout=30
        )
        if response.status_code == 200:
            raw_content = response.json()['message']['content'].strip()
            try:
                return json.loads(raw_content)
            except json.JSONDecodeError:
                explanation_match = re.search(r'"explanation"\s*:\s*"(.*?)"', raw_content, re.DOTALL)
                chart_match = re.search(r'"chart_code"\s*:\s*"(.*?)"', raw_content, re.DOTALL)
                
                explanation = explanation_match.group(1) if explanation_match else "Kunde inte tolka analysen."
                chart_code = chart_match.group(1) if chart_match else ""
                
                try:
                    explanation = explanation.encode().decode('unicode_escape', errors='ignore')
                    chart_code = chart_code.encode().decode('unicode_escape', errors='ignore')
                except Exception:
                    pass
                
                return {"explanation": explanation, "chart_code": chart_code}
    except Exception:
        pass
    return {"explanation": "Kunde inte generera ett giltigt svar från den lokala modellen.", "chart_code": ""}


if tab_ai:
    with tab_ai:
        st.markdown('<p class="qlik-header">🤖 AI-Assistent</p>', unsafe_allow_html=True)

        st.markdown("""
        <style>
        .chat-wrapper  { display:flex; flex-direction:column; gap:12px; margin-bottom:16px; }
        .chat-bubble   { max-width:84%; padding:12px 16px; border-radius:12px; font-size:14px;
                         line-height:1.6; font-family:'Segoe UI',sans-serif; }
        .user-bubble   { background:#005c53; color:#fff; align-self:flex-end;
                         border-bottom-right-radius:3px; margin-left:auto; }
        .ai-bubble     { background:#f1f5f9; color:#1e293b; align-self:flex-start;
                         border-bottom-left-radius:3px; border:1px solid #e2e8f0; }
        .ai-label      { font-size:11px; font-weight:700; color:#64748b;
                         text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
        .gdpr-badge    { display:inline-flex; align-items:center; gap:6px; background:#dcfce7;
                         color:#166534; border:1px solid #bbf7d0; border-radius:6px;
                         padding:5px 10px; font-size:11px; font-weight:700; margin-bottom:12px; }
        .setup-box     { background:#fffbeb; border:1px solid #fcd34d; border-radius:8px;
                         padding:16px; font-size:13px; color:#78350f; margin-bottom:12px; }
        .setup-box code { background:#fef3c7; padding:2px 6px; border-radius:3px;
                          font-family:monospace; font-size:12px; }
        </style>
        """, unsafe_allow_html=True)

        # ── Ollama-inställningar (sidebar-liknande kolumn) ──
        col_chat, col_info = st.columns([3, 1])

        with col_info:
            # GDPR-badge
            st.markdown("""
            <div class="gdpr-badge">🔒 GDPR-säker — körs lokalt</div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style='background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px;
                        padding:14px; font-size:12px; color:#166534; margin-bottom:12px;'>
            <strong>Varför detta är GDPR-säkert:</strong><br><br>
            ✅ Modellen körs på <em>din servers hårdvara</em><br>
            ✅ Ingen data lämnar organisationens nätverk<br>
            ✅ Ingen tredjepartsöverföring till USA/utanför EU<br>
            ✅ Inget DPA eller SCCs behövs<br>
            ✅ Ingen loggning hos extern leverantör<br>
            ✅ Möter kraven i <strong>Art. 25 & 32 GDPR</strong><br>
            &nbsp;&nbsp;&nbsp;&nbsp;(inbyggd dataskydd & lämpliga tekniska åtgärder)
            </div>
            """, unsafe_allow_html=True)

            with st.expander("⚙️ Anslutningsinställningar", expanded=False):
                ollama_url = st.text_input(
                    "Ollama-adress",
                    value=st.session_state.get("ollama_url", "http://localhost:11434"),
                    help="Standard: http://localhost:11434. Byt till er servers IP vid central driftsättning."
                )
                st.session_state.ollama_url = ollama_url

            # Kontrollera anslutning och visa modeller
            is_connected, available_models = check_ollama_connection(
                st.session_state.get("ollama_url", "http://localhost:11434")
            )

            if is_connected:
                st.success(f"✅ Ollama ansluten ({len(available_models)} modeller)")
                recommended = ["llama3.2", "llama3", "mistral", "mixtral", "llama3.1"]
                sorted_models = sorted(
                    available_models,
                    key=lambda m: next((i for i, r in enumerate(recommended) if r in m), 99)
                )
                if sorted_models:
                    selected_model = st.selectbox(
                        "Modell",
                        sorted_models,
                        help="Llama 3.2 eller Mistral rekommenderas för svenska texter."
                    )
                else:
                    st.warning("Inga modeller installerade. Kör: `ollama pull llama3.2`")
                    selected_model = "llama3.2"
            else:
                st.error("❌ Ollama ej ansluten")
                st.markdown("""
                <div class="setup-box">
                <strong>Så startar du Ollama:</strong><br><br>
                1. Ladda ner: <code>ollama.com</code><br>
                2. Installera modell:<br>
                <code>ollama pull llama3.2</code><br>
                3. Starta server:<br>
                <code>ollama serve</code><br><br>
                Ändra adressen ovan om Ollama körs på en annan server i nätverket.
                </div>
                """, unsafe_allow_html=True)
                selected_model = "llama3.2"

            st.markdown("---")
            role_scope = {
                "Analytiker (Full behörighet)": "All data, alla skolor",
                "Rektor (Annedalsskolan)":       "Endast Annedalsskolan",
                "Samordnare (Centrum)":          "Endast Centrum"
            }
            st.caption(f"📊 Din datascope: {role_scope.get(anvandare, anvandare)}")

            st.markdown("**Förslag på frågor:**")
            suggestions = [
                "Vilken månad har högst ogiltig frånvaro?",
                "Visa närvaro per månad som stapeldiagram",
                "Jämför närvaro mellan pojkar och flickor",
                "Visa ogiltig frånvaro per årskurs",
                "Vilka skolor har störst registreringsproblem?",
                "Ge mig en sammanfattning av läget",
            ]
            for s in suggestions:
                if st.button(s, key=f"sug_{s[:20]}", use_container_width=True):
                    st.session_state.ai_pending_input = s
                    st.rerun()

        with col_chat:
            if "ai_messages" not in st.session_state:
                st.session_state.ai_messages = []
            if "ai_llm_history" not in st.session_state:
                st.session_state.ai_llm_history = []

            _, c2 = st.columns([4, 1])
            with c2:
                if st.button("🗑 Rensa", use_container_width=True):
                    st.session_state.ai_messages = []
                    st.session_state.ai_llm_history = []
                    st.rerun()

            # Välkomstmeddelande om tom historik
            if not st.session_state.ai_messages:
                st.markdown("""
                <div class="chat-bubble ai-bubble" style="max-width:100%">
                <div class="ai-label">🤖 AI-Assistent</div>
                Hej! Jag är din lokala AI-assistent för närvarodata. Jag körs helt på er server
                — ingen information lämnar organisationens nätverk.<br><br>
                Ställ en fråga om datan eller välj ett förslag till höger, så analyserar jag det åt dig.
                </div>
                """, unsafe_allow_html=True)

            # Chatthistorik
            chat_html = '<div class="chat-wrapper">'
            # Rendering av chatthistorik samt live-exekvering av diagram
            for msg in st.session_state.ai_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
                    if msg.get("chart_code") and msg["chart_code"].strip():
                        try:
                            # Tydliggör 'df' för Python-motorn
                            local_vars = {
                                "pd": pd, 
                                "px": px, 
                                "go": go, 
                                "st": st,
                                "df": df_qlik  # Här säger vi åt koden att df är din dashboard-data
                            }
                            # Vi skickar in local_vars två gånger (som globals och locals) 
                            # för att förhindra NameError: 'df' is not defined
                            exec(msg["chart_code"], local_vars, local_vars)
                            
                            # Rita diagrammet
                            if "fig" in local_vars:
                                st.plotly_chart(local_vars["fig"], use_container_width=True)
                        except Exception as chart_error:
                            st.error(f"Kunde inte rita diagrammet på grund av ett kodfel.")
                            with st.expander("Visa den AI-genererade koden"):
                                st.code(msg["chart_code"], language="python")
                                st.caption(f"Tekniskt felmeddelande: {chart_error}")
            chat_html += '</div>'
            st.markdown(chat_html, unsafe_allow_html=True)

            # Visa diagram om senaste svar har chart_code
            if st.session_state.ai_messages:
                last = st.session_state.ai_messages[-1]
                if last["role"] == "assistant" and last.get("chart_code"):
                    fig = safe_execute_plotly(last["chart_code"], df_qlik)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

            # Förslag-klick
            pending = st.session_state.pop("ai_pending_input", None)

            with st.form("ai_chat_form", clear_on_submit=True):
                user_input = st.text_input(
                    "Din fråga",
                    value=pending or "",
                    placeholder="T.ex. 'Visa närvaro per månad' eller 'Vilka skolor har hög ogiltig frånvaro?'",
                    label_visibility="collapsed"
                )
                send = st.form_submit_button(
                    "Skicka →", use_container_width=True, type="primary",
                    disabled=not is_connected
                )

            if not is_connected:
                st.info("Starta Ollama för att aktivera AI-assistenten (se instruktioner till höger).")

            if send and user_input.strip() and is_connected:
                st.session_state.ai_messages.append({"role": "user", "content": user_input.strip()})
                st.session_state.ai_llm_history.append({"role": "user", "content": user_input.strip()})

                with st.spinner(f"Analyserar data lokalt med {selected_model}..."):
                    data_ctx = build_data_context(df_qlik, anvandare)
                    try:
                        result = call_ollama(
                            st.session_state.ai_llm_history,
                            data_ctx,
                            st.session_state.get("ollama_url", "http://localhost:11434"),
                            selected_model
                        )
                    except requests.exceptions.Timeout:
                        result = {"type": "text", "explanation": "⏱ Timeout — modellen tog för lång tid. Försök med en mindre modell eller öka serverns resurser."}
                    except Exception as e:
                        result = {"type": "text", "explanation": f"Fel: {e}"}

                explanation = result.get("explanation", "Kunde inte tolka svaret.")
                chart_code  = result.get("chart_code", "")

                st.session_state.ai_messages.append({
                    "role": "assistant",
                    "content": explanation,
                    "chart_code": chart_code
                })
                st.session_state.ai_llm_history.append({
                    "role": "assistant",
                    "content": explanation + ("\n[Diagram genererat]" if chart_code else "")
                })
                st.rerun()