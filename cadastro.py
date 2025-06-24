import subprocess
import os
import base64
import datetime
import sqlite3
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from fpdf import FPDF
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
import pyperclip
import io
import re
import requests
from datetime import datetime as dt
import ast
import calendar
import plotly.express as px
from PIL import Image
import numpy as np
from folium import CustomIcon
from streamlit.components.v1 import html
import hashlib # Import for password hashing
import bcrypt

# --- User Authentication Functions ---
DATABASE_FILE = 'users.db'

def init_users_db():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT,
            last_login TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_admin_user():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username=?", ('admin',))
    if not c.fetchone():  # Se o usuário admin não existir
        hashed_password = hash_password('MNR1750JR01')
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ('admin', hashed_password, 'admin'))
        conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT password, role FROM users WHERE username=?", (username,))
    result = c.fetchone()
    if result:
        stored_password, role = result
        if verify_password(password, stored_password):
            # Atualiza o último acesso
            last_login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("UPDATE users SET last_login=? WHERE username=?", (last_login_time, username))
            conn.commit()
            conn.close()
            return role
    conn.close()
    return None


def get_last_login(username):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT last_login FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


def hash_password(password):
    # Certifique-se de que a senha está em bytes antes de aplicar o hash
    if isinstance(password, str):
        password = password.encode('utf-8')
    # Gera um salt aleatório e aplica o hash à senha
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password, salt)
    return hashed_password

def verify_password(provided_password, stored_password):
    # Certifique-se de que a senha fornecida está em bytes
    if isinstance(provided_password, str):
        provided_password = provided_password.encode('utf-8')
    # stored_password já deve estar em bytes, então não precisamos codificá-lo novamente
    return bcrypt.checkpw(provided_password, stored_password)

def add_user(username, password):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    try:
        hashed_password = hash_password(password)
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (username, hashed_password, 'user'))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # User already exists
    finally:
        conn.close()

def verify_user(username, password):
    # Connect to the SQLite database
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    # Execute a query to fetch the stored password and role for the given username
    c.execute("SELECT password, role FROM users WHERE username=?", (username,))
    result = c.fetchone()

    # Close the database connection
    conn.close()

    # If a result is found, verify the password
    if result:
        stored_password, role = result
        if verify_password(password, stored_password):
            # Debugging message (typically used in Streamlit)
            print(f"Usuário {username} autenticado com papel: {role}")
            return role

    # Debugging message if authentication fails
    print(f"Falha na autenticação para usuário: {username}")
    return None

# Configuração da página
st.set_page_config(
    page_title="Sistema de Cadastro de Ocorrências Policiais Militares",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def carregar_militares():
    try:
        with open('militares.txt', 'r', encoding='utf-8') as file:
            militares = [line.strip() for line in file if line.strip()]
        return militares
    except FileNotFoundError:
        st.error("Arquivo militares.txt não encontrado. Usando lista padrão.")
        return [
            "Cabo Silva",
            "Sargento Oliveira",
            "Soldado Pereira",
            "Tenente Costa",
            "Cabo Ferreira",
            "Sargento Rodrigues",
            "Soldado Santos",
            "Tenente Lima"
        ]

def display_logout_button():
    # Usando um container para posicionar o botão no topo direito
    st.markdown(
        """
        <style>
        .logout-container {
            position: fixed;
            top: 10px;
            left: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Container para o botão de logout
    logout_container = st.container()

    with logout_container:
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            st.rerun()

def salvar_dados_em_excel(dados):
    try:
        file_path = 'ocorrencias.xlsx'

        # Carregar os dados existentes
        existing_data = pd.read_excel(file_path, sheet_name=None) if os.path.exists(file_path) else {}

        # Adicionar os novos dados à aba principal
        new_data = pd.DataFrame([dados])
        if 'Sheet1' in existing_data:
            updated_data = pd.concat([existing_data['Sheet1'], new_data], ignore_index=True)
        else:
            updated_data = new_data

        # Criar ou atualizar a aba "Coordenadas"
        coordenadas_data = []
        if 'Coordenadas' in existing_data:
            coordenadas_data = existing_data['Coordenadas'].values.tolist()

        # Adicionar as novas coordenadas e tipos de ocorrência
        latitude, longitude = dados['localizacao'].split(',')
        tipos_ocorrencia = {
            'armas_apreendidas': 'Armas Apreendidas',
            'drogas_apreendidas': 'Drogas Apreendidas',
            'presos_apreendidos': 'Presos Apreendidos',
            'mandados_prisao': 'Mandados de Prisão',
            'veiculos_recuperados': 'Veículos Recuperados'
        }

        for campo, tipo in tipos_ocorrencia.items():
            if dados[campo] == 'SIM':
                coordenadas_data.append([f"{latitude}, {longitude}, {tipo}"])

        # Criar um DataFrame para a aba "Coordenadas"
        coordenadas_df = pd.DataFrame(coordenadas_data, columns=['Coordenadas'])

        # Salvar os dados no arquivo Excel
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            updated_data.to_excel(writer, sheet_name='Sheet1', index=False)
            coordenadas_df.to_excel(writer, sheet_name='Coordenadas', index=False, header=False)

        st.success("Dados salvos na planilha com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar os dados na planilha: {e}")


def criar_pdf(dados):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_left_margin(10)
    pdf.set_right_margin(10)
    pdf.set_top_margin(10)

    y_position = 15

    page_width = 190
    logo_width = 30
    logo_height = 20
    margin_between = (page_width - 3 * logo_width) / 4

    additional_left_margin = 30
    total_width = 3 * logo_width + 2 * margin_between
    start_x = (page_width - total_width) / 2 + additional_left_margin

    x1 = margin_between
    x2 = x1 + logo_width + margin_between
    x3 = x2 + logo_width + margin_between

    try:
        pdf.image("logo_pmpb.png", x=x1, y=y_position, w=logo_width, h=logo_height)
        pdf.image("logo_ft.png", x=x2, y=y_position, w=logo_width, h=logo_height)
        pdf.image("logo_5bpm.png", x=x3, y=y_position, w=logo_width, h=logo_height)
    except Exception as e:
        print(f"Erro ao adicionar logos: {e}")

    pdf.ln(30)

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="RELATÓRIO DE OCORRÊNCIA POLICIAL MILITAR", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="ID da Ocorrência:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=str(dados['id']), ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Data:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['data'], ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Hora:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['hora'], ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Localização:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['localizacao'], ln=True)

    if 'link_maps' in dados and dados['link_maps']:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(50, 10, txt="Link do Google Maps:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(140, 10, txt=dados['link_maps'], ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Companhia:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['cia'], ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Batalhão:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['batalhao'], ln=True)

    componentes_endereco = []

    endereco_linha = ""
    if 'logradouro' in dados and dados['logradouro']:
        endereco_linha = dados['logradouro']
        if 'numero' in dados and dados['numero']:
            endereco_linha += ", " + dados['numero']

    if endereco_linha:
        componentes_endereco.append(("Logradouro:", endereco_linha))

    if 'bairro' in dados and dados['bairro']:
        componentes_endereco.append(("Bairro:", dados['bairro']))

    cidade_estado = ""
    if 'cidade' in dados and dados['cidade']:
        cidade_estado = dados['cidade']
        if 'estado' in dados and dados['estado']:
            cidade_estado += " - " + dados['estado']

    if cidade_estado:
        componentes_endereco.append(("Cidade/Estado:", cidade_estado))

    if 'cep' in dados and dados['cep']:
        componentes_endereco.append(("CEP:", dados['cep']))

    for componente in componentes_endereco:
        label, valor = componente
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(50, 10, txt=label, ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(140, 10, txt=valor, ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="EQUIPE", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Motorista:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['motorista'], ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, txt="Comandante:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(140, 10, txt=dados['comandante'], ln=True)

    if dados['patrulheiro1']:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(50, 10, txt="Patrulheiro 1:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(140, 10, txt=dados['patrulheiro1'], ln=True)

    if dados['patrulheiro2']:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(50, 10, txt="Patrulheiro 2:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(140, 10, txt=dados['patrulheiro2'], ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="ARMAS E MUNIÇÕES", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Armas apreendidas:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['armas_apreendidas'], ln=True)

    if dados['armas_apreendidas'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Quantidade de armas:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(120, 10, txt=str(dados['qtd_armas']), ln=True)

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Tipos de armas:", ln=True)
        pdf.set_font("Arial", size=12)

        for tipo, qtd in dados['tipos_armas'].items():
            if qtd > 0:
                pdf.cell(70, 10, txt=f"- {tipo}: {qtd}", ln=True, align='L')

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Munições apreendidas:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['municoes_apreendidas'], ln=True)

    if dados['municoes_apreendidas'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Tipos de munições:", ln=True)
        pdf.set_font("Arial", size=12)

        for tipo, qtd in dados['tipos_municoes'].items():
            if qtd > 0:
                pdf.cell(70, 10, txt=f"- {tipo}: {qtd}", ln=True, align='L')

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="DROGAS", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Drogas apreendidas:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['drogas_apreendidas'], ln=True)

    if dados['drogas_apreendidas'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Tipos de drogas:", ln=True)
        pdf.set_font("Arial", size=12)

        for tipo, qtd in dados['tipos_drogas'].items():
            if qtd > 0:
                pdf.cell(70, 10, txt=f"- {tipo}: {qtd}", ln=True, align='L')

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="PRESOS E MANDADOS", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Presos ou apreendidos:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['presos_apreendidos'], ln=True)

    if dados['presos_apreendidos'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Quantidade de presos:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(120, 10, txt=str(dados['qtd_presos']), ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Mandados de prisão:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['mandados_prisao'], ln=True)

    if dados['mandados_prisao'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Quantidade de mandados:", ln=False)
        pdf.set_font("Arial", size=12)
        pdf.cell(120, 10, txt=str(dados['qtd_mandados']), ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="VEÍCULOS RECUPERADOS", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, txt="Veículos recuperados:", ln=False)
    pdf.set_font("Arial", size=12)
    pdf.cell(120, 10, txt=dados['veiculos_recuperados'], ln=True)

    if dados['veiculos_recuperados'] == "SIM":
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(70, 10, txt="Tipos de veículos:", ln=True)
        pdf.set_font("Arial", size=12)

        for tipo, qtd in dados['tipos_veiculos'].items():
            if qtd > 0:
                pdf.cell(70, 10, txt=f"- {tipo}: {qtd}", ln=True, align='L')

    return pdf.output(dest='S').encode('latin-1')

def get_image_as_base64(file_path):
    try:
        with open(file_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        print(f"Erro ao carregar imagem {file_path}: {e}")
        return ""

def exibir_logos():
    st.markdown("""
        <style>
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: auto;
            margin: 0 auto;
            flex-wrap: wrap;
        }
        .logo-image {
            max-width: 100px;
            max-height: 100px;
            object-fit: contain;
            width: auto;
            height: auto;
            margin: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    try:
        col1.markdown('<div class="logo-container"><img src="data:image/png;base64,{}" class="logo-image"></div>'.format(
            get_image_as_base64("logo_pmpb.png")
        ), unsafe_allow_html=True)

        col2.markdown('<div class="logo-container"><img src="data:image/png;base64,{}" class="logo-image"></div>'.format(
            get_image_as_base64("logo_ft.png")
        ), unsafe_allow_html=True)

        col3.markdown('<div class="logo-container"><img src="data:image/png;base64,{}" class="logo-image"></div>'.format(
            get_image_as_base64("logo_5bpm.png")
        ), unsafe_allow_html=True)
    except:
        col1.markdown(
            '<div class="logo-container"><h3 style="text-align: center;">Logo PMPB</h3></div>', unsafe_allow_html=True)
        col2.markdown(
            '<div class="logo-container"><h3 style="text-align: center;">Logo 5º BPM</h3></div>', unsafe_allow_html=True)
        col3.markdown(
            '<div class="logo-container"><h3 style="text-align: center;">Logo Força Tática</h3></div>', unsafe_allow_html=True)

def expandir_url(url_curta):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(
            url_curta, headers=headers, allow_redirects=True, timeout=5)
        return response.url
    except Exception as e:
        print(f"Não foi possível expandir a URL: {e}")
        return url_curta

def extrair_coordenadas_e_endereco_do_link(link):
    try:
        if not link:
            return None

        coordenadas = None
        url_expandida = link
        if "goo.gl" in link or "maps.app" in link:
            url_expandida = expandir_url(link)

        padroes_link = [
            r'@(-?\d+\.\d+),(-?\d+\.\d+)',
            r'q=(-?\d+\.\d+),(-?\d+\.\d+)',
            r'(-?\d+\.\d+)[,+]+(-?\d+\.\d+)'
        ]

        for padrao in padroes_link:
            match = re.search(padrao, url_expandida)
            if match:
                lat, lon = match.groups()
                try:
                    lat_float = float(lat)
                    lon_float = float(lon)
                    if -90 <= lat_float <= 90 and -180 <= lon_float <= 180:
                        coordenadas = (lat_float, lon_float)
                        break
                except:
                    continue

        if not coordenadas:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(
                    url_expandida, headers=headers, timeout=10)

                if response.status_code == 200:
                    html = response.text
                    padroes = [
                        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
                        r'"(-?\d+\.\d+),(-?\d+\.\d+)',
                        r'"latitude":(-?\d+\.\d+).*?"longitude":(-?\d+\.\d+)',
                        r'LatLng\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)',
                        r'center=(-?\d+\.\d+)%2C(-?\d+\.\d+)'
                    ]

                    for padrao in padroes:
                        match = re.search(padrao, html)
                        if match:
                            lat, lon = match.groups()
                            try:
                                lat_float = float(lat)
                                lon_float = float(lon)
                                if -90 <= lat_float <= 90 and -180 <= lon_float <= 180:
                                    coordenadas = (lat_float, lon_float)
                                    break
                            except:
                                continue

                    if not coordenadas:
                        coordenadas_pattern = r'[-+]?\d+\.\d+,\s*[-+]?\d+\.\d+'
                        matches = re.findall(coordenadas_pattern, html)

                        for coord_pair in matches:
                            parts = coord_pair.split(',')
                            if len(parts) == 2:
                                lat = parts[0].strip()
                                lng = parts[1].strip()

                                try:
                                    lat_float = float(lat)
                                    lng_float = float(lng)

                                    if -90 <= lat_float <= 90 and -180 <= lng_float <= 180:
                                        coordenadas = (lat_float, lng_float)
                                        break
                                except:
                                    continue
            except Exception as e:
                print(f"Erro ao processar página: {e}")

        if coordenadas:
            endereco = obter_endereco_detalhado_por_geocodificacao(
                coordenadas[0], coordenadas[1])
            if endereco:
                return (*coordenadas, endereco)
            else:
                return coordenadas

        return None
    except Exception as e:
        print(f"Erro ao extrair coordenadas e endereço: {e}")
        return None

def obter_endereco_detalhado_por_geocodificacao(latitude, longitude):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=18&addressdetails=1"
        headers = {
            'User-Agent': 'SystemaCadastroOcorrencias/1.0',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            data = response.json()
            endereco_detalhado = {
                'logradouro': None,
                'numero': None,
                'bairro': None,
                'cidade': None,
                'estado': None,
                'cep': None,
                'pais': None,
                'endereco_completo': None
            }

            if 'display_name' in data:
                endereco_detalhado['endereco_completo'] = data['display_name']

            if 'address' in data:
                addr = data['address']

                if 'road' in addr:
                    endereco_detalhado['logradouro'] = addr['road']
                elif 'pedestrian' in addr:
                    endereco_detalhado['logradouro'] = addr['pedestrian']
                elif 'footway' in addr:
                    endereco_detalhado['logradouro'] = addr['footway']
                elif 'path' in addr:
                    endereco_detalhado['logradouro'] = addr['path']

                if 'house_number' in addr:
                    endereco_detalhado['numero'] = addr['house_number']

                if 'suburb' in addr:
                    endereco_detalhado['bairro'] = addr['suburb']
                elif 'neighbourhood' in addr:
                    endereco_detalhado['bairro'] = addr['neighbourhood']
                elif 'quarter' in addr:
                    endereco_detalhado['bairro'] = addr['quarter']

                if 'city' in addr:
                    endereco_detalhado['cidade'] = addr['city']
                elif 'town' in addr:
                    endereco_detalhado['cidade'] = addr['town']
                elif 'village' in addr:
                    endereco_detalhado['cidade'] = addr['village']
                elif 'municipality' in addr:
                    endereco_detalhado['cidade'] = addr['municipality']

                if 'state' in addr:
                    endereco_detalhado['estado'] = addr['state']

                if 'postcode' in addr:
                    endereco_detalhado['cep'] = addr['postcode']

                if 'country' in addr:
                    endereco_detalhado['pais'] = addr['country']

                if not endereco_detalhado['endereco_completo']:
                    partes = []

                    if endereco_detalhado['logradouro']:
                        logradouro = endereco_detalhado['logradouro']
                        if endereco_detalhado['numero']:
                            logradouro += ", " + endereco_detalhado['numero']
                        partes.append(logradouro)

                    if endereco_detalhado['bairro']:
                        partes.append(endereco_detalhado['bairro'])

                    if endereco_detalhado['cidade']:
                        cidade = endereco_detalhado['cidade']
                        if endereco_detalhado['estado']:
                            cidade += " - " + endereco_detalhado['estado']
                        partes.append(cidade)

                    if endereco_detalhado['cep']:
                        partes.append("CEP: " + endereco_detalhado['cep'])

                    if endereco_detalhado['pais']:
                        partes.append(endereco_detalhado['pais'])

                    if partes:
                        endereco_detalhado['endereco_completo'] = ", ".join(
                            partes)

            return endereco_detalhado

        return None
    except Exception as e:
        print(f"Erro ao obter endereço detalhado por geocodificação: {e}")
        return None

def obter_coordenadas_da_area_transferencia():
    try:
        texto = pyperclip.paste()
        padrao = r'(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
        match = re.search(padrao, texto)

        if match:
            lat, lon = match.groups()
            try:
                lat_float = float(lat)
                lon_float = float(lon)
                if -90 <= lat_float <= 90 and -180 <= lon_float <= 180:
                    return lat_float, lon_float
            except:
                pass

        return None
    except:
        return None

def obter_coordenadas():
    try:
        texto = pyperclip.paste()

        if "maps.google" in texto or "maps.app.goo.gl" in texto or "google.com/maps" in texto:
            resultado = extrair_coordenadas_e_endereco_do_link(texto)
            if resultado:
                lat, lon = resultado
                return f"{lat},{lon}"

        if texto.count(',') == 1 and texto.count('(') <= 1 and texto.count(')') <= 1:
            texto = texto.replace('(', '').replace(')', '')
            lat, lon = map(float, texto.split(','))
            return f"{lat},{lon}"

        return ""
    except:
        return ""

def processar_extracao_coordenadas(link_maps=None):
    link = link_maps if link_maps else st.session_state.link_maps

    if link:
        resultado = extrair_coordenadas_e_endereco_do_link(link)

        if resultado:
            if len(resultado) == 3:
                lat, lon, detalhes_endereco = resultado
                st.session_state.latitude = str(lat)
                st.session_state.longitude = str(lon)
                st.session_state.dados_ocorrencia['localizacao'] = f"{lat},{lon}"
                st.session_state.dados_ocorrencia['link_maps'] = link

                if 'detalhes_endereco' not in st.session_state:
                    st.session_state.detalhes_endereco = {}
                st.session_state.detalhes_endereco = detalhes_endereco

                if 'logradouro' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['logradouro'] = ""
                if 'numero' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['numero'] = ""
                if 'bairro' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['bairro'] = ""
                if 'cidade' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['cidade'] = ""
                if 'estado' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['estado'] = ""
                if 'cep' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['cep'] = ""
                if 'endereco_completo' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['endereco_completo'] = ""

                st.session_state.dados_ocorrencia['logradouro'] = detalhes_endereco.get(
                    'logradouro', "")
                st.session_state.dados_ocorrencia['numero'] = detalhes_endereco.get(
                    'numero', "")
                st.session_state.dados_ocorrencia['bairro'] = detalhes_endereco.get(
                    'bairro', "")
                st.session_state.dados_ocorrencia['cidade'] = detalhes_endereco.get(
                    'cidade', "")
                st.session_state.dados_ocorrencia['estado'] = detalhes_endereco.get(
                    'estado', "")
                st.session_state.dados_ocorrencia['cep'] = detalhes_endereco.get(
                    'cep', "")
                st.session_state.dados_ocorrencia['endereco_completo'] = detalhes_endereco.get(
                    'endereco_completo', "")

                mensagem = f"Coordenadas extraídas com sucesso: {lat}, {lon}"
                if detalhes_endereco.get('endereco_completo'):
                    mensagem += f"\nEndereço: {detalhes_endereco['endereco_completo']}"

                st.success(mensagem)
                return True
            else:
                lat, lon = resultado
                st.session_state.latitude = str(lat)
                st.session_state.longitude = str(lon)
                st.session_state.dados_ocorrencia['localizacao'] = f"{lat},{lon}"
                st.session_state.dados_ocorrencia['link_maps'] = link
                st.success(
                    f"Coordenadas extraídas com sucesso: {lat}, {lon}\nNão foi possível obter detalhes do endereço.")
                return True
        else:
            return False
    else:
        st.error("Insira um link do Google Maps primeiro.")
        return False

def buscar_dados_na_planilha(id_ocorrencia=None, data=None, batalhao=None):
    try:
        file_path = 'ocorrencias.xlsx'
        data = pd.read_excel(file_path)

        conditions = []
        if id_ocorrencia:
            conditions.append(data['id'] == int(id_ocorrencia))
        if data:
            conditions.append(data['data'] == data)
        if batalhao:
            conditions.append(data['batalhao'] == batalhao)

        if conditions:
            filtered_data = data[conditions[0]]
            for condition in conditions[1:]:
                filtered_data = filtered_data[condition]
        else:
            filtered_data = data

        return filtered_data.to_dict('records')
    except Exception as e:
        st.error(f"Erro ao buscar dados na planilha: {e}")
        return []
    
def main_app():
    exibir_logos()
    st.markdown(
        f"""
        <h1 style='text-align: center;'>Sistema de Cadastro de Ocorrências Policiais Militares</h1>
                """,
        unsafe_allow_html=True
    )
    
        # Exibir o botão de logout no topo
    display_logout_button()

    role = st.session_state.get('role', 'user')

    if role == 'admin':

        tab1, tab2, tab3 = st.tabs(["Formulário", "Mapas", "Estatísticas"])
    else:
        tab2, tab3 = st.tabs(["Mapas", "Estatísticas"])

    if role == 'admin':
        
        with tab1:
            # Buscar o último ID da planilha
            file_path = 'ocorrencias.xlsx'
            existing_data = pd.read_excel(file_path) if os.path.exists(file_path) else pd.DataFrame()
            ultimo_id_bd = existing_data['id'].max() if not existing_data.empty else 0

            if 'dados_ocorrencia' not in st.session_state:
                st.session_state.dados_ocorrencia = {
                    'id': ultimo_id_bd + 1,
                    'data': '',
                    'hora': '',
                    'localizacao': '',
                    'link_maps': '',
                    'cia': '',
                    'batalhao': '',
                    'motorista': '',
                    'comandante': '',
                    'patrulheiro1': '',
                    'patrulheiro2': '',
                    'armas_apreendidas': 'NÃO',
                    'qtd_armas': 0,
                    'tipos_armas': {
                        'REVÓLVER': 0,
                        'PISTOLA': 0,
                        'ESPINGARDA': 0,
                        'RIFLE': 0,
                        'FUZIL': 0,
                        'METRALHADORA': 0,
                        'ARTESANAL': 0
                    },
                    'municoes_apreendidas': 'NÃO',
                    'tipos_municoes': {
                        '12': 0, '20': 0, '22': 0, '26': 0, '28': 0, '32': 0, '36': 0,
                        '38': 0, '357': 0, '.380': 0, '9mm': 0, '.40': 0, '44': 0,
                        '.45': 0, '5,56': 0, '7.62': 0, 'OUTROS': 0
                    },
                    'drogas_apreendidas': 'NÃO',
                    'tipos_drogas': {
                        'MACONHA': 0, 'COCAÍNA': 0, 'CRACK': 0, 'HAXIXE': 0, 'SKANK': 0,
                        'EXCTASY': 0, 'LSD': 0, 'LOLÓ': 0, 'ARTANE': 0, 'OUTROS': 0
                    },
                    'presos_apreendidos': 'NÃO',
                    'qtd_presos': 0,
                    'mandados_prisao': 'NÃO',
                    'qtd_mandados': 0,
                    'veiculos_recuperados': 'NÃO',
                    'tipos_veiculos': {
                        'CARRO': 0, 'MOTO': 0, 'CAMINHÃO': 0, 'ÔNIBUS': 0, 'BICICLETA': 0, 'OUTROS': 0
                    },
                    'logradouro': '',
                    'numero': '',
                    'bairro': '',
                    'cidade': '',
                    'estado': '',
                    'cep': '',
                    'endereco_completo': ''
                }

            if 'ultimo_id' not in st.session_state:
                st.session_state.ultimo_id = ultimo_id_bd + 1

            militares = carregar_militares()

            st.header("Informações Básicas da Ocorrência")

            st.text_input("ID da Ocorrência", value=st.session_state.dados_ocorrencia['id'], disabled=True)

            col1, col2 = st.columns(2)

            with col1:
                st.session_state.dados_ocorrencia['data'] = st.date_input(
                    "Data",
                    datetime.datetime.now().date(),
                    format="DD/MM/YYYY"
                ).strftime("%d/%m/%Y")

                st.session_state.dados_ocorrencia['cia'] = st.selectbox(
                    "Companhia",
                    ["FT", "1ª CIA", "2ª CIA", "3ª CIA", "4ª CIA", "5ª CIA"]
                )

            with col2:
                hora_input = st.time_input("Hora", value=None)
                if hora_input:
                    st.session_state.dados_ocorrencia['hora'] = hora_input.strftime("%H:%M")
                else:
                    st.session_state.dados_ocorrencia['hora'] = ""

                st.session_state.dados_ocorrencia['batalhao'] = st.selectbox(
                    "Batalhão",
                    ["1º BPM", "2º BPM", "3º BPM", "4º BPM", "5º BPM", "6º BPM", "7º BPM"]
                )

            st.subheader("Localização")

            link_col, lat_col, lon_col, btn_col = st.columns([3, 1, 1, 1])

            if 'link_maps' not in st.session_state:
                st.session_state.link_maps = ""
            if 'latitude' not in st.session_state:
                st.session_state.latitude = ""
            if 'longitude' not in st.session_state:
                st.session_state.longitude = ""

            with link_col:
                st.session_state.link_maps = st.text_input(
                    "Link do Google Maps",
                    st.session_state.link_maps
                )

            with lat_col:
                st.session_state.latitude = st.text_input(
                    "Latitude",
                    st.session_state.latitude
                )

            with lon_col:
                st.session_state.longitude = st.text_input(
                    "Longitude",
                    st.session_state.longitude
                )

            with btn_col:
                extractBtn = st.button("Extrair Coordenadas")
                if extractBtn:
                    sucesso = processar_extracao_coordenadas()
                    if sucesso:
                        st.rerun()

            with st.expander("Detalhes do Endereço", expanded=True):
                endereco_col1, endereco_col2 = st.columns(2)

            with endereco_col1:
                if 'logradouro' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['logradouro'] = ""
                st.session_state.dados_ocorrencia['logradouro'] = st.text_input(
                    "Logradouro",
                    st.session_state.dados_ocorrencia['logradouro']
                )

                if 'numero' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['numero'] = ""
                st.session_state.dados_ocorrencia['numero'] = st.text_input(
                    "Número",
                    st.session_state.dados_ocorrencia['numero']
                )

                if 'bairro' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['bairro'] = ""
                st.session_state.dados_ocorrencia['bairro'] = st.text_input(
                    "Bairro",
                    st.session_state.dados_ocorrencia['bairro']
                )

            with endereco_col2:
                if 'cidade' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['cidade'] = ""
                st.session_state.dados_ocorrencia['cidade'] = st.text_input(
                    "Cidade",
                    st.session_state.dados_ocorrencia['cidade']
                )

                if 'estado' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['estado'] = ""
                st.session_state.dados_ocorrencia['estado'] = st.text_input(
                    "Estado",
                    st.session_state.dados_ocorrencia['estado']
                )

                if 'cep' not in st.session_state.dados_ocorrencia:
                    st.session_state.dados_ocorrencia['cep'] = ""
                st.session_state.dados_ocorrencia['cep'] = st.text_input(
                    "CEP",
                    st.session_state.dados_ocorrencia['cep']
                )

            def atualizar_localizacao_dos_campos():
                if (
                    st.session_state.latitude and
                    st.session_state.longitude and
                    st.session_state.latitude != "" and
                    st.session_state.longitude != ""
                ):
                    try:
                        lat = float(st.session_state.latitude)
                        lon = float(st.session_state.longitude)

                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            st.session_state.dados_ocorrencia['localizacao'] = f"{lat},{lon}"
                    except ValueError:
                        pass

            atualizar_localizacao_dos_campos()

            st.header("Informações da Equipe")

            st.session_state.dados_ocorrencia['motorista'] = st.selectbox(
                "Motorista",
                militares,
                index=militares.index(st.session_state.dados_ocorrencia['motorista']) if st.session_state.dados_ocorrencia['motorista'] in militares else 0
            )

            st.session_state.dados_ocorrencia['comandante'] = st.selectbox(
                "Comandante",
                militares,
                index=militares.index(st.session_state.dados_ocorrencia['comandante']) if st.session_state.dados_ocorrencia['comandante'] in militares else 0
            )

            patrulheiro1_options = [""] + militares
            patrulheiro1_index = patrulheiro1_options.index(st.session_state.dados_ocorrencia['patrulheiro1']) if st.session_state.dados_ocorrencia['patrulheiro1'] in patrulheiro1_options else 0
            st.session_state.dados_ocorrencia['patrulheiro1'] = st.selectbox(
                "Patrulheiro 1 (opcional)",
                patrulheiro1_options,
                index=patrulheiro1_index
            )

            patrulheiro2_options = [""] + militares
            patrulheiro2_index = patrulheiro2_options.index(st.session_state.dados_ocorrencia['patrulheiro2']) if st.session_state.dados_ocorrencia['patrulheiro2'] in patrulheiro2_options else 0
            st.session_state.dados_ocorrencia['patrulheiro2'] = st.selectbox(
                "Patrulheiro 2 (opcional)",
                patrulheiro2_options,
                index=patrulheiro2_index
            )

            st.header("Armas e Munições Apreendidas")

            col1, col2 = st.columns(2)

            with col1:
                st.session_state.dados_ocorrencia['armas_apreendidas'] = st.selectbox(
                    "Armas apreendidas",
                    ["NÃO", "SIM"],
                    index=1 if st.session_state.dados_ocorrencia['armas_apreendidas'] == "SIM" else 0
                )

            if st.session_state.dados_ocorrencia['armas_apreendidas'] == "SIM":
                with col2:
                    st.session_state.dados_ocorrencia['qtd_armas'] = st.number_input(
                        "Quantidade total de armas",
                        min_value=0,
                        value=st.session_state.dados_ocorrencia['qtd_armas']
                    )

                st.subheader("Tipos de Armas")

                tipos_col1, tipos_col2 = st.columns(2)

                tipos_armas = list(st.session_state.dados_ocorrencia['tipos_armas'].keys())

                metade = len(tipos_armas) // 2

                with tipos_col1:
                    for tipo in tipos_armas[:metade]:
                        st.session_state.dados_ocorrencia['tipos_armas'][tipo] = st.number_input(
                            f"{tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_armas'][tipo]
                        )

                with tipos_col2:
                    for tipo in tipos_armas[metade:]:
                        st.session_state.dados_ocorrencia['tipos_armas'][tipo] = st.number_input(
                            f"{tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_armas'][tipo]
                        )

            st.markdown("---")
            st.session_state.dados_ocorrencia['municoes_apreendidas'] = st.selectbox(
                "Munições apreendidas",
                ["NÃO", "SIM"],
                index=1 if st.session_state.dados_ocorrencia['municoes_apreendidas'] == "SIM" else 0
            )

            if st.session_state.dados_ocorrencia['municoes_apreendidas'] == "SIM":
                st.subheader("Tipos de Munições")

                mun_col1, mun_col2, mun_col3 = st.columns(3)

                tipos_municoes = list(st.session_state.dados_ocorrencia['tipos_municoes'].keys())

                tercio = len(tipos_municoes) // 3

                with mun_col1:
                    for tipo in tipos_municoes[:tercio]:
                        st.session_state.dados_ocorrencia['tipos_municoes'][tipo] = st.number_input(
                            f"Munição {tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_municoes'][tipo]
                        )

                with mun_col2:
                    for tipo in tipos_municoes[tercio:2*tercio]:
                        st.session_state.dados_ocorrencia['tipos_municoes'][tipo] = st.number_input(
                            f"Munição {tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_municoes'][tipo]
                        )

                with mun_col3:
                    for tipo in tipos_municoes[2*tercio:]:
                        st.session_state.dados_ocorrencia['tipos_municoes'][tipo] = st.number_input(
                            f"Munição {tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_municoes'][tipo]
                        )

            st.header("Drogas Apreendidas")

            st.session_state.dados_ocorrencia['drogas_apreendidas'] = st.selectbox(
                "Drogas apreendidas",
                ["NÃO", "SIM"],
                index=1 if st.session_state.dados_ocorrencia['drogas_apreendidas'] == "SIM" else 0
            )

            if st.session_state.dados_ocorrencia['drogas_apreendidas'] == "SIM":
                st.subheader("Tipos e Quantidades de Drogas")

                drogas_col1, drogas_col2 = st.columns(2)

                tipos_drogas = list(st.session_state.dados_ocorrencia['tipos_drogas'].keys())

                metade = len(tipos_drogas) // 2

                with drogas_col1:
                    for tipo in tipos_drogas[:metade]:
                        st.session_state.dados_ocorrencia['tipos_drogas'][tipo] = st.number_input(
                            f"{tipo} (gramas)",
                            min_value=0.0,
                            value=float(st.session_state.dados_ocorrencia['tipos_drogas'][tipo]),
                            format="%.3f",
                            step=0.001
                        )

                with drogas_col2:
                    for tipo in tipos_drogas[metade:]:
                        st.session_state.dados_ocorrencia['tipos_drogas'][tipo] = st.number_input(
                            f"{tipo} (unidades)",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_drogas'][tipo]
                        )

            st.header("Presos e Veículos Recuperados")

            col1, col2 = st.columns(2)

            with col1:
                st.session_state.dados_ocorrencia['presos_apreendidos'] = st.selectbox(
                    "Presos ou apreendidos",
                    ["NÃO", "SIM"],
                    index=1 if st.session_state.dados_ocorrencia['presos_apreendidos'] == "SIM" else 0
                )

            if st.session_state.dados_ocorrencia['presos_apreendidos'] == "SIM":
                with col2:
                    st.session_state.dados_ocorrencia['qtd_presos'] = st.number_input(
                        "Quantidade de presos",
                        min_value=0,
                        value=st.session_state.dados_ocorrencia['qtd_presos']
                    )

            mand_col1, mand_col2 = st.columns(2)

            with mand_col1:
                st.session_state.dados_ocorrencia['mandados_prisao'] = st.selectbox(
                    "Mandados de prisão",
                    ["NÃO", "SIM"],
                    index=1 if st.session_state.dados_ocorrencia['mandados_prisao'] == "SIM" else 0
                )

            if st.session_state.dados_ocorrencia['mandados_prisao'] == "SIM":
                with mand_col2:
                    st.session_state.dados_ocorrencia['qtd_mandados'] = st.number_input(
                        "Quantidade de mandados",
                        min_value=0,
                        value=st.session_state.dados_ocorrencia['qtd_mandados']
                    )

            st.markdown("---")
            st.session_state.dados_ocorrencia['veiculos_recuperados'] = st.selectbox(
                "Veículos recuperados",
                ["NÃO", "SIM"],
                index=1 if st.session_state.dados_ocorrencia['veiculos_recuperados'] == "SIM" else 0
            )

            if st.session_state.dados_ocorrencia['veiculos_recuperados'] == "SIM":
                st.subheader("Tipos e Quantidades de Veículos")

                veic_col1, veic_col2 = st.columns(2)

                tipos_veiculos = list(st.session_state.dados_ocorrencia['tipos_veiculos'].keys())

                metade = len(tipos_veiculos) // 2

                with veic_col1:
                    for tipo in tipos_veiculos[:metade]:
                        st.session_state.dados_ocorrencia['tipos_veiculos'][tipo] = st.number_input(
                            f"{tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_veiculos'][tipo]
                        )

                with veic_col2:
                    for tipo in tipos_veiculos[metade:]:
                        st.session_state.dados_ocorrencia['tipos_veiculos'][tipo] = st.number_input(
                            f"{tipo}",
                            min_value=0,
                            value=st.session_state.dados_ocorrencia['tipos_veiculos'][tipo]
                        )

            st.header("Finalizar e Salvar Ocorrência")

            if st.button("Salvar Dados"):
                salvar_dados_em_excel(st.session_state.dados_ocorrencia)

            if st.button("Gerar Relatório em PDF"):
                if st.session_state.dados_ocorrencia['data'] and st.session_state.dados_ocorrencia['hora']:
                    pdf_bytes = criar_pdf(st.session_state.dados_ocorrencia)
                    data_formatada = st.session_state.dados_ocorrencia['data'].replace('/', '-')
                    nome_arquivo = f"Ocorrencia_{data_formatada}_{st.session_state.dados_ocorrencia['hora'].replace(':', '-')}.pdf"

                    st.download_button(
                        label="Baixar Relatório PDF",
                        data=pdf_bytes,
                        file_name=nome_arquivo,
                        mime="application/pdf"
                    )

                    st.success("Relatório gerado com sucesso!")

                    st.subheader("Resumo da Ocorrência")
                    st.write(f"**ID da Ocorrência:** {st.session_state.dados_ocorrencia['id']}")
                    st.write(f"**Data e Hora:** {st.session_state.dados_ocorrencia['data']} às {st.session_state.dados_ocorrencia['hora']}")
                    st.write(f"**Local:** {st.session_state.dados_ocorrencia['localizacao']}")
                    st.write(f"**Companhia/Batalhão:** {st.session_state.dados_ocorrencia['cia']} / {st.session_state.dados_ocorrencia['batalhao']}")

                    stats_col1, stats_col2, stats_col3 = st.columns(3)

                    with stats_col1:
                        if st.session_state.dados_ocorrencia['armas_apreendidas'] == "SIM":
                            st.metric("Armas Apreendidas", st.session_state.dados_ocorrencia['qtd_armas'])

                        if st.session_state.dados_ocorrencia['drogas_apreendidas'] == "SIM":
                            total_drogas = sum(st.session_state.dados_ocorrencia['tipos_drogas'].values())
                            st.metric("Drogas Apreendidas (g/un)", total_drogas)

                    with stats_col2:
                        if st.session_state.dados_ocorrencia['presos_apreendidos'] == "SIM":
                            st.metric("Presos/Apreendidos", st.session_state.dados_ocorrencia['qtd_presos'])

                        if st.session_state.dados_ocorrencia['mandados_prisao'] == "SIM":
                            st.metric("Mandados Cumpridos", st.session_state.dados_ocorrencia['qtd_mandados'])

                    with stats_col3:
                        if st.session_state.dados_ocorrencia['veiculos_recuperados'] == "SIM":
                            total_veiculos = sum(st.session_state.dados_ocorrencia['tipos_veiculos'].values())
                            st.metric("Veículos Recuperados", total_veiculos)

                        total_municoes = sum(st.session_state.dados_ocorrencia['tipos_municoes'].values())
                        if total_municoes > 0:
                            st.metric("Munições Apreendidas", total_municoes)
                else:
                    st.error("Preencha pelo menos a data e hora da ocorrência!")

            if st.button("Limpar Formulário"):
                for key in st.session_state.dados_ocorrencia:
                    if isinstance(st.session_state.dados_ocorrencia[key], dict):
                        for subkey in st.session_state.dados_ocorrencia[key]:
                            st.session_state.dados_ocorrencia[key][subkey] = 0
                    elif isinstance(st.session_state.dados_ocorrencia[key], int):
                        st.session_state.dados_ocorrencia[key] = 0
                    elif key in ['armas_apreendidas', 'municoes_apreendidas', 'drogas_apreendidas', 'presos_apreendidos', 'mandados_prisao', 'veiculos_recuperados']:
                        st.session_state.dados_ocorrencia[key] = 'NÃO'
                    elif key in ['patrulheiro1', 'patrulheiro2']:
                        st.session_state.dados_ocorrencia[key] = ''
                    elif key == 'data':
                        st.session_state.dados_ocorrencia[key] = datetime.datetime.now().strftime("%d/%m/%Y")
                    elif key == 'hora':
                        st.session_state.dados_ocorrencia[key] = datetime.datetime.now().strftime("%H:%M")

                st.session_state.ultimo_id += 1
                st.session_state.dados_ocorrencia['id'] = st.session_state.ultimo_id

                st.success("Formulário limpo com sucesso!")
                st.rerun()

            st.header("Buscar Ocorrências")

            id_ocorrencia = st.text_input("ID da Ocorrência (opcional)")
            data = st.text_input("Data (opcional)")
            batalhao = st.selectbox("Batalhão (opcional)", [""] + ["1º BPM", "2º BPM", "3º BPM", "4º BPM", "5º BPM", "6º BPM", "7º BPM"])

            if st.button("Buscar"):
                resultados = buscar_dados_na_planilha(id_ocorrencia if id_ocorrencia else None, data if data else None, batalhao if batalhao else None)
                if resultados:
                    st.subheader("Resultados da Busca")

                    for resultado in resultados:
                        for key, value in resultado.items():
                            st.write(f"{key}: {value}")
                        st.write("---")
                else:
                    st.warning("Nenhuma ocorrência encontrada.")
       
    with tab2:
        if role == 'admin' or role == 'user':
            st.header("Mapas por Tipo de Ocorrência")

            file_path = 'ocorrencias.xlsx'
            data = pd.read_excel(file_path, sheet_name='Coordenadas', header=None)

            if data.empty or data.shape[1] == 0:
                st.error("A aba 'Coordenadas' está vazia ou não contém dados.")
            else:
                data.columns = ['Coordenadas']

                def extract_coordinates(coord_str):
                    parts = coord_str.strip().split()
                    if len(parts) >= 3:
                        lat = float(parts[0].replace(',', ''))
                        lon = float(parts[1].replace(',', ''))
                        tipo = ' '.join(parts[2:])
                        return pd.Series({'Latitude': lat, 'Longitude': lon, 'Tipo': tipo})
                    else:
                        return pd.Series({'Latitude': None, 'Longitude': None, 'Tipo': None})

                data[['Latitude', 'Longitude', 'Tipo']] = data['Coordenadas'].apply(extract_coordinates)
                data = data.dropna(subset=['Latitude', 'Longitude'])

                # Obtém o diretório atual do script
                diretorio_atual = os.path.dirname(os.path.abspath(__file__))

                # Constrói o caminho para a pasta de ícones
                icon_folder = os.path.join(diretorio_atual, "ICONES")
                icon_map = {
                    "armas apreendidas": os.path.join(icon_folder, "Armas Apreendidas.png"),
                    "drogas apreendidas": os.path.join(icon_folder, "Drogas Apreendidas.png"),
                    "mandados de prisão": os.path.join(icon_folder, "Mandados de Prisão.png"),
                    "presos apreendidos": os.path.join(icon_folder, "Presos Apreendidos.png"),
                    "veículos recuperados": os.path.join(icon_folder, "Veículos Recuperados.png")
                }

                data['Tipo_Normalizado'] = data['Tipo'].str.strip().str.lower()
                occurrence_types = data['Tipo'].unique()

                for occurrence_type in occurrence_types:
                    st.subheader(f"Mapa para {occurrence_type}")
                    tipo_norm = occurrence_type.strip().lower()
                    filtered_data = data[data['Tipo'] == occurrence_type]

                    if not filtered_data.empty:
                        first_coordinate = filtered_data.iloc[0]
                        m = folium.Map(location=[first_coordinate['Latitude'], first_coordinate['Longitude']], zoom_start=12)

                        for _, row in filtered_data.iterrows():
                            icon_path = icon_map.get(tipo_norm)
                            if icon_path and os.path.exists(icon_path):
                                icon = folium.CustomIcon(icon_image=icon_path, icon_size=(30, 30))
                                folium.Marker(
                                    [row['Latitude'], row['Longitude']],
                                    popup=occurrence_type,
                                    icon=icon
                                ).add_to(m)
                            else:
                                folium.Marker(
                                    [row['Latitude'], row['Longitude']],
                                    popup=f"{occurrence_type} (sem ícone)"
                                ).add_to(m)

                        # Renerizar o mapa como HTML com 100% de largura e altura da tela
                        map_html = m.get_root().render()
                        html(
                            f"""
                            <div style="height:100vh;">
                                {map_html}
                            </div>
                            """,
                            height=700,
                            scrolling=False
                        )
                    else:
                        st.warning(f"Nenhuma coordenada encontrada para {occurrence_type}.")

    with tab3:
        if role == 'admin' or role == 'user':
            st.header("Estatísticas")

            # Carregar os dados da planilha
            file_path = 'ocorrencias.xlsx'
            data = pd.read_excel(file_path)

            # Converter a coluna 'data' para o formato de data
            data['data'] = pd.to_datetime(data['data'], format='%d/%m/%Y', errors='coerce')

            # Obter anos únicos dos dados
            anos = sorted(data['data'].dt.year.unique())

            # Obter o ano atual
            ano_atual = datetime.datetime.now().year

            # Meses do ano
            meses = [
                "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]

            # Colunas de ocorrências
            colunas_ocorrencias = ['armas_apreendidas', 'drogas_apreendidas', 'presos_apreendidos', 'mandados_prisao', 'veiculos_recuperados']

            # Criar abas dentro da aba Estatísticas
            tab_estatisticas = st.tabs([
                "Comparativo Mensal",
                "Total de Ocorrências por Trimestre",
                "Total de Ocorrências por Semestre",
                "Total de Ocorrências no Ano",
                "Tipo de Ocorrência",
                "Produtividade"
            ])

            legend_mapping = {
                'armas_apreendidas': 'Armas Apreendidas',
                'drogas_apreendidas': 'Drogas Apreendidas',
                'presos_apreendidos': 'Presos Apreendidos',
                'mandados_prisao': 'Mandados de Prisão',
                'veiculos_recuperados': 'Veículos Recuperados'
            }

        with tab_estatisticas[0]:
            st.subheader("Comparativo Mensal")

            current_month = datetime.datetime.now().month
            current_year = datetime.datetime.now().year

            meses = [
                "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]

            selected_month = st.selectbox("Selecionar Mês", meses, index=current_month - 1)
            selected_month_num = meses.index(selected_month) + 1

            current_month_data = data[(data['data'].dt.month == selected_month_num) & (data['data'].dt.year == current_year)]
            previous_month_data = data[(data['data'].dt.month == selected_month_num) & (data['data'].dt.year == current_year - 1)]

            current_month_sums = current_month_data[colunas_ocorrencias].apply(lambda x: x.eq('SIM').sum()).to_dict()
            previous_month_sums = previous_month_data[colunas_ocorrencias].apply(lambda x: x.eq('SIM').sum()).to_dict()

            comparison_data = {
                'Tipo de Ocorrência': [legend_mapping.get(col, col) for col in colunas_ocorrencias],
                f'{current_year}': [current_month_sums.get(col, 0) for col in colunas_ocorrencias],
                f'{current_year - 1}': [previous_month_sums.get(col, 0) for col in colunas_ocorrencias],
            }

            comparison_data[f'Variação (%)'] = [
                ((current_month_sums.get(col, 0) - previous_month_sums.get(col, 0)) / previous_month_sums.get(col, 1)) * 100
                if previous_month_sums.get(col, 0) != 0 else 0
                for col in colunas_ocorrencias
            ]

            comparison_df = pd.DataFrame(comparison_data)

            styled_df = comparison_df.style.applymap(
                lambda x: 'color: green' if x > 0 else 'color: red', subset=[f'Variação (%)']
            ).background_gradient(
                subset=[f'{current_year}', f'{current_year - 1}'], cmap='Blues', axis=0
            ).format({
                f'{current_year}': '{:,.0f}',
                f'{current_year - 1}': '{:,.0f}',
                f'Variação (%)': '{:,.1f}%'
            })

            st.write(styled_df)

            fig, ax = plt.subplots(figsize=(7, 4))
            bar_width = 0.3
            index = range(len(colunas_ocorrencias))

            bars1 = ax.bar(index, comparison_df[f'{current_year}'], bar_width, label=f'{current_year}')
            bars2 = ax.bar([i + bar_width for i in index], comparison_df[f'{current_year - 1}'], bar_width, label=f'{current_year - 1}')

            for bar in bars1:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

            for bar in bars2:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

            ax.set_xlabel('Tipo de Ocorrência')
            ax.set_ylabel('Total de Ocorrências')
            ax.set_title(f'Comparativo de Ocorrências - {selected_month}')
            ax.set_xticks([i + bar_width / 2 for i in index])
            ax.set_xticklabels([legend_mapping.get(col, col) for col in colunas_ocorrencias], rotation=45, ha='right')
            ax.set_ylim(0, max(comparison_df[f'{current_year}'].max(), comparison_df[f'{current_year - 1}'].max()) * 1.1)
            ax.legend()
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        with tab_estatisticas[1]:
            st.subheader("Total de Ocorrências por Trimestre")

            current_year = datetime.datetime.now().year
            previous_year = current_year - 1

            trimestres = {
                'Q1': (1, 3),
                'Q2': (4, 6),
                'Q3': (7, 9),
                'Q4': (10, 12)
            }

            data_ano_atual = data[data['data'].dt.year == current_year]
            data_ano_anterior = data[data['data'].dt.year == previous_year]

            trimestres_com_dados = set()
            for trimestre, (mes_inicio, mes_fim) in trimestres.items():
                dados_trimestre_atual = data_ano_atual[(data_ano_atual['data'].dt.month >= mes_inicio) &
                                                    (data_ano_atual['data'].dt.month <= mes_fim)]
                if not dados_trimestre_atual.empty:
                    trimestres_com_dados.add(trimestre)

            dados_trimestrais_atual = {trimestre: {} for trimestre in trimestres_com_dados}
            dados_trimestrais_anterior = {trimestre: {} for trimestre in trimestres_com_dados}

            for trimestre, (mes_inicio, mes_fim) in trimestres.items():
                if trimestre in trimestres_com_dados:
                    for coluna in colunas_ocorrencias:
                        dados_trimestre_atual = data_ano_atual[(data_ano_atual['data'].dt.month >= mes_inicio) &
                                                            (data_ano_atual['data'].dt.month <= mes_fim)]
                        dados_trimestrais_atual[trimestre][coluna] = dados_trimestre_atual[coluna].eq('SIM').sum()

                        dados_trimestre_anterior = data_ano_anterior[(data_ano_anterior['data'].dt.month >= mes_inicio) &
                                                                    (data_ano_anterior['data'].dt.month <= mes_fim)]
                        dados_trimestrais_anterior[trimestre][coluna] = dados_trimestre_anterior[coluna].eq('SIM').sum()

            trimestres_ordenados = ['Q1', 'Q2', 'Q3', 'Q4']

            for trimestre in trimestres_ordenados:
                if trimestre in trimestres_com_dados:
                    st.subheader(f"Trimestre {trimestre}")

                    df_trimestre_atual = pd.DataFrame.from_dict(dados_trimestrais_atual[trimestre], orient='index', columns=[current_year])
                    df_trimestre_anterior = pd.DataFrame.from_dict(dados_trimestrais_anterior[trimestre], orient='index', columns=[previous_year])

                    df_trimestre_atual = df_trimestre_atual.rename(index=legend_mapping)
                    df_trimestre_anterior = df_trimestre_anterior.rename(index=legend_mapping)

                    df_combinado = pd.concat([df_trimestre_atual, df_trimestre_anterior], axis=1)

                    df_combinado['Variação (%)'] = (
                        (df_combinado[current_year] - df_combinado[previous_year]) / df_combinado[previous_year] * 100
                    ).fillna(0)

                    def highlight_variation(val):
                        color = 'green' if val > 0 else 'red'
                        return f'color: {color}'

                    styled_df = df_combinado.style\
                        .applymap(highlight_variation, subset=['Variação (%)'])\
                        .background_gradient(subset=[current_year, previous_year], cmap='Blues')\
                        .format({
                            current_year: '{:,.0f}',
                            previous_year: '{:,.0f}',
                            'Variação (%)': '{:,.2f}%'
                        })

                    col1, col2 = st.columns([1, 2])

                    with col1:
                        st.dataframe(styled_df, width=350)

                    with col2:
                        fig, ax = plt.subplots(figsize=(12, 7))
                        bar_width = 0.35
                        index = range(len(df_combinado))

                        bars1 = ax.bar(index, df_combinado[current_year], bar_width, label=str(current_year))
                        bars2 = ax.bar([i + bar_width for i in index], df_combinado[previous_year], bar_width, label=str(previous_year))

                        for bar in bars1:
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

                        for bar in bars2:
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

                        ax.set_xlabel('Tipo de Ocorrência')
                        ax.set_ylabel('Total de Ocorrências')
                        ax.set_title(f'Ocorrências no {trimestre}')
                        ax.set_xticks([i + bar_width / 2 for i in index])
                        ax.set_xticklabels(df_combinado.index, rotation=45, ha='right')
                        ax.legend()

                        plt.tight_layout()
                        st.pyplot(fig)
                        plt.close(fig)

        with tab_estatisticas[2]:
            st.subheader("Total de Ocorrências por Semestre")

            current_year = datetime.datetime.now().year
            previous_year = current_year - 1

            semesters = {
                'S1': (1, 6),
                'S2': (7, 12)
            }

            data_current_year = data[data['data'].dt.year == current_year]
            data_previous_year = data[data['data'].dt.year == previous_year]

            semesters_with_data = set()
            for semester, (start_month, end_month) in semesters.items():
                current_semester_data = data_current_year[(data_current_year['data'].dt.month >= start_month) &
                                                        (data_current_year['data'].dt.month <= end_month)]
                if not current_semester_data.empty:
                    semesters_with_data.add(semester)

            current_year_semester_data = {semester: {} for semester in semesters_with_data}
            previous_year_semester_data = {semester: {} for semester in semesters_with_data}

            for semester, (start_month, end_month) in semesters.items():
                if semester in semesters_with_data:
                    for column in colunas_ocorrencias:
                        current_semester_data = data_current_year[(data_current_year['data'].dt.month >= start_month) &
                                                                (data_current_year['data'].dt.month <= end_month)]
                        current_year_semester_data[semester][column] = current_semester_data[column].eq('SIM').sum()

                        previous_semester_data = data_previous_year[(data_previous_year['data'].dt.month >= start_month) &
                                                                    (data_previous_year['data'].dt.month <= end_month)]
                        previous_year_semester_data[semester][column] = previous_semester_data[column].eq('SIM').sum()

            for semester in sorted(semesters_with_data):
                st.subheader(f"Semestre {semester}")

                df_current_semester = pd.DataFrame.from_dict(current_year_semester_data[semester], orient='index', columns=[current_year])
                df_previous_semester = pd.DataFrame.from_dict(previous_year_semester_data[semester], orient='index', columns=[previous_year])

                df_current_semester = df_current_semester.rename(index=legend_mapping)
                df_previous_semester = df_previous_semester.rename(index=legend_mapping)

                df_combined = pd.concat([df_current_semester, df_previous_semester], axis=1)

                df_combined['Variação (%)'] = (
                    (df_combined[current_year] - df_combined[previous_year]) / df_combined[previous_year] * 100
                ).fillna(0)

                def highlight_variation(val):
                    if isinstance(val, (int, float)):
                        color = 'green' if val > 0 else 'red'
                        return f'color: {color}'
                    return ''

                styled_df = df_combined.style\
                    .applymap(highlight_variation, subset=['Variação (%)'])\
                    .background_gradient(subset=[current_year, previous_year], cmap='Blues')\
                    .format({
                        current_year: '{:,.0f}',
                        previous_year: '{:,.0f}',
                        'Variação (%)': '{:,.2f}%'
                    })

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.dataframe(styled_df)

                with col2:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    bar_width = 0.35
                    index = range(len(df_combined))

                    bars1 = ax.bar(index, df_combined[current_year], bar_width, label=str(current_year))
                    bars2 = ax.bar([i + bar_width for i in index], df_combined[previous_year], bar_width, label=str(previous_year))

                    for bar in bars1:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

                    for bar in bars2:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

                    ax.set_xlabel('Tipo de Ocorrência')
                    ax.set_ylabel('Total de Ocorrências')
                    ax.set_title(f'Ocorrências no {semester}')
                    ax.set_xticks([i + bar_width / 2 for i in index])
                    ax.set_xticklabels(df_combined.index, rotation=45, ha='right')
                    ax.legend()

                    plt.tight_layout()
                    st.pyplot(fig)
                    plt.close(fig)

        with tab_estatisticas[3]:
            st.subheader("Total de Ocorrências no Ano")

            current_year = datetime.datetime.now().year
            previous_year = current_year - 1

            data_ano_atual = data[data['data'].dt.year == current_year]
            data_ano_anterior = data[data['data'].dt.year == previous_year]

            ocorrencias_ano_atual = data_ano_atual[colunas_ocorrencias].apply(lambda x: x.eq('SIM').sum()).rename(legend_mapping)
            ocorrencias_ano_anterior = data_ano_anterior[colunas_ocorrencias].apply(lambda x: x.eq('SIM').sum()).rename(legend_mapping)

            df_comparacao_anual = pd.DataFrame({
                current_year: ocorrencias_ano_atual,
                previous_year: ocorrencias_ano_anterior
            })

            fig, ax = plt.subplots(figsize=(10, 6))
            bar_width = 0.35
            index = range(len(df_comparacao_anual))

            bars1 = ax.bar(index, df_comparacao_anual[current_year], bar_width, label=str(current_year))
            bars2 = ax.bar([i + bar_width for i in index], df_comparacao_anual[previous_year], bar_width, label=str(previous_year))

            for bar in bars1:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

            for bar in bars2:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

            ax.set_xlabel('Tipo de Ocorrência')
            ax.set_ylabel('Total de Ocorrências')
            ax.set_title('Comparação Anual de Ocorrências')
            ax.set_xticks([i + bar_width / 2 for i in index])
            ax.set_xticklabels(df_comparacao_anual.index, rotation=45, ha='right')
            ax.legend()

            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        with tab_estatisticas[4]:
            st.subheader("Tipo de Ocorrência")

            legend_mapping = {
                'armas_apreendidas': 'Armas Apreendidas',
                'drogas_apreendidas': 'Drogas Apreendidas',
                'presos_apreendidos': 'Presos Apreendidos',
                'mandados_prisao': 'Mandados de Prisão',
                'veiculos_recuperados': 'Veículos Recuperados'
            }

            occurrence_tabs = st.tabs(list(legend_mapping.values()))

            current_year = datetime.datetime.now().year

            data_current_year = data[data['data'].dt.year == current_year]

            month_names_pt = {
                1: 'Janeiro',
                2: 'Fevereiro',
                3: 'Março',
                4: 'Abril',
                5: 'Maio',
                6: 'Junho',
                7: 'Julho',
                8: 'Agosto',
                9: 'Setembro',
                10: 'Outubro',
                11: 'Novembro',
                12: 'Dezembro'
            }

            for occurrence_tab, occurrence in zip(occurrence_tabs, legend_mapping.keys()):
                with occurrence_tab:
                    if occurrence == 'armas_apreendidas':
                        st.subheader(legend_mapping[occurrence])

                        monthly_occurrences = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()
                        df_monthly_occurrences = pd.DataFrame({
                            'Mês': monthly_occurrences.index.map(month_names_pt),
                            'Total de Ocorrências': monthly_occurrences.values
                        })

                        st.write("Total de Ocorrências por Mês:")

                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.dataframe(df_monthly_occurrences)
                        with col2:
                            fig1, ax1 = plt.subplots(figsize=(10, 6))
                            months_occurrences = df_monthly_occurrences['Mês']
                            counts_occurrences = df_monthly_occurrences['Total de Ocorrências']
                            bars_occurrences = ax1.bar(months_occurrences, counts_occurrences, width=0.6, color='lightgreen')
                            for bar in bars_occurrences:
                                height = bar.get_height()
                                ax1.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                            ax1.set_xlabel('Mês')
                            ax1.set_ylabel('Total de Ocorrências')
                            ax1.set_title(f'Ocorrências Mensais de {legend_mapping[occurrence]} em {current_year}')
                            ax1.set_xticks(range(len(months_occurrences)))
                            ax1.set_xticklabels(months_occurrences, rotation=45, ha='right')
                            plt.tight_layout()
                            st.pyplot(fig1)
                            plt.close(fig1)

                        monthly_arms = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month)['qtd_armas'].sum()
                        df_monthly_arms = pd.DataFrame({
                            'Mês': monthly_arms.index.map(month_names_pt),
                            'Total de Armas Apreendidas': monthly_arms.values
                        })

                        st.write("Total de Armas Apreendidas por Mês:")

                        col3, col4 = st.columns([1, 2])
                        with col3:
                            st.dataframe(df_monthly_arms)
                        with col4:
                            fig2, ax2 = plt.subplots(figsize=(10, 6))
                            months_arms = df_monthly_arms['Mês']
                            counts_arms = df_monthly_arms['Total de Armas Apreendidas']
                            bars_arms = ax2.bar(months_arms, counts_arms, width=0.6, color='skyblue')
                            for bar in bars_arms:
                                height = bar.get_height()
                                ax2.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                            ax2.set_xlabel('Mês')
                            ax2.set_ylabel('Total de Armas Apreendidas')
                            ax2.set_title(f'Total de Armas Apreendidas por Mês em {current_year}')
                            ax2.set_xticks(range(len(months_arms)))
                            ax2.set_xticklabels(months_arms, rotation=45, ha='right')
                            plt.tight_layout()
                            st.pyplot(fig2)
                            plt.close(fig2)

                        def process_weapon_types(weapon_str):
                            try:
                                weapons_dict = ast.literal_eval(weapon_str)
                                return weapons_dict
                            except (ValueError, SyntaxError):
                                return {}

                        weapon_type_counts = {}
                        for weapons in data_current_year[data_current_year[occurrence] == 'SIM']['tipos_armas']:
                            weapons_dict = process_weapon_types(weapons)
                            for weapon, count in weapons_dict.items():
                                if weapon in weapon_type_counts:
                                    weapon_type_counts[weapon] += count
                                else:
                                    weapon_type_counts[weapon] = count

                        df_weapon_types = pd.DataFrame({
                            'Tipo de Arma': weapon_type_counts.keys(),
                            'Total': weapon_type_counts.values()
                        })

                        st.write("Total de Armas por Tipo:")

                        col5, col6 = st.columns([1, 2])
                        with col5:
                            st.dataframe(df_weapon_types)
                        with col6:
                            fig3, ax3 = plt.subplots(figsize=(10, 6))
                            weapon_types_labels = df_weapon_types['Tipo de Arma']
                            weapon_types_counts = df_weapon_types['Total']
                            bars_weapon_types = ax3.bar(weapon_types_labels, weapon_types_counts, width=0.6, color='coral')
                            for bar in bars_weapon_types:
                                height = bar.get_height()
                                ax3.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                            ax3.set_xlabel('Tipo de Arma')
                            ax3.set_ylabel('Total')
                            ax3.set_title(f'Total de Armas Apreendidas por Tipo em {current_year}')
                            ax3.set_xticks(range(len(weapon_types_labels)))
                            ax3.set_xticklabels(weapon_types_labels, rotation=45, ha='right')
                            plt.tight_layout()
                            st.pyplot(fig3)
                            plt.close(fig3)

                        def process_ammo_types(ammo_str):
                            try:
                                ammo_dict = ast.literal_eval(ammo_str)
                                return ammo_dict
                            except (ValueError, SyntaxError):
                                return {}

                        ammo_type_counts = {}
                        for ammo in data_current_year[data_current_year[occurrence] == 'SIM']['tipos_municoes']:
                            ammo_dict = process_ammo_types(ammo)
                            for ammo_type, count in ammo_dict.items():
                                if ammo_type in ammo_type_counts:
                                    ammo_type_counts[ammo_type] += count
                                else:
                                    ammo_type_counts[ammo_type] = count

                        df_ammo_types = pd.DataFrame({
                            'Tipo de Munição': ammo_type_counts.keys(),
                            'Total': ammo_type_counts.values()
                        })

                        st.write("Total de Munições por Tipo:")

                        col7, col8 = st.columns([1, 2])
                        with col7:
                            st.dataframe(df_ammo_types)
                        with col8:
                            fig4, ax4 = plt.subplots(figsize=(10, 6))
                            ammo_types_labels = df_ammo_types['Tipo de Munição']
                            ammo_types_counts = df_ammo_types['Total']
                            bars_ammo_types = ax4.bar(ammo_types_labels, ammo_types_counts, width=0.6, color='lightsalmon')
                            for bar in bars_ammo_types:
                                height = bar.get_height()
                                ax4.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                            ax4.set_xlabel('Tipo de Munição')
                            ax4.set_ylabel('Total')
                            ax4.set_title(f'Total de Munições Apreendidas por Tipo em {current_year}')
                            ax4.set_xticks(range(len(ammo_types_labels)))
                            ax4.set_xticklabels(ammo_types_labels, rotation=45, ha='right')
                            plt.tight_layout()
                            st.pyplot(fig4)
                            plt.close(fig4)

                    with occurrence_tab:
                        if occurrence == 'drogas_apreendidas':
                            st.subheader(legend_mapping[occurrence])

                            monthly_occurrences = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()

                            df_monthly_occurrences = pd.DataFrame({
                                'Mês': monthly_occurrences.index.map(month_names_pt),
                                'Total de Ocorrências': monthly_occurrences.values
                            })

                            st.write("Total de Ocorrências por Mês:")

                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.dataframe(df_monthly_occurrences)
                            with col2:
                                fig1, ax1 = plt.subplots(figsize=(10, 6))
                                months_occurrences = df_monthly_occurrences['Mês']
                                counts_occurrences = df_monthly_occurrences['Total de Ocorrências']
                                bars_occurrences = ax1.bar(months_occurrences, counts_occurrences, width=0.6, color='lightgreen')
                                for bar in bars_occurrences:
                                    height = bar.get_height()
                                    ax1.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax1.set_xlabel('Mês')
                                ax1.set_ylabel('Total de Ocorrências')
                                ax1.set_title(f'Ocorrências Mensais de {legend_mapping[occurrence]} em {current_year}')
                                ax1.set_xticks(range(len(months_occurrences)))
                                ax1.set_xticklabels(months_occurrences, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig1)
                                plt.close(fig1)

                            monthly_drugs = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()

                            df_monthly_drugs = pd.DataFrame({
                                'Mês': monthly_drugs.index.map(month_names_pt),
                                'Total de Drogas Apreendidas': monthly_drugs.values
                            })

                            st.write("Total de Drogas Apreendidas por Mês:")

                            col3, col4 = st.columns([1, 2])
                            with col3:
                                st.dataframe(df_monthly_drugs)
                            with col4:
                                fig2, ax2 = plt.subplots(figsize=(10, 6))
                                months_drugs = df_monthly_drugs['Mês']
                                counts_drugs = df_monthly_drugs['Total de Drogas Apreendidas']
                                bars_drugs = ax2.bar(months_drugs, counts_drugs, width=0.6, color='skyblue')
                                for bar in bars_drugs:
                                    height = bar.get_height()
                                    ax2.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax2.set_xlabel('Mês')
                                ax2.set_ylabel('Total de Drogas Apreendidas')
                                ax2.set_title(f'Total de Drogas Apreendidas por Mês em {current_year}')
                                ax2.set_xticks(range(len(months_drugs)))
                                ax2.set_xticklabels(months_drugs, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig2)
                                plt.close(fig2)

                            st.subheader("Tipos de Drogas Apreendidas")

                            def process_drug_types(drug_str):
                                try:
                                    drugs_dict = ast.literal_eval(drug_str)
                                    return {drug: float(count) for drug, count in drugs_dict.items()}
                                except (ValueError, SyntaxError):
                                    return {}

                            drugs_in_kg = {'MACONHA', 'COCAÍNA', 'CRACK', 'HAXIXE', 'SKANK'}

                            drug_type_counts_kg = {}
                            drug_type_counts_units = {}

                            for drugs in data_current_year[data_current_year[occurrence] == 'SIM']['tipos_drogas']:
                                drugs_dict = process_drug_types(drugs)
                                for drug, count in drugs_dict.items():
                                    if drug in drugs_in_kg:
                                        if drug in drug_type_counts_kg:
                                            drug_type_counts_kg[drug] += count
                                        else:
                                            drug_type_counts_kg[drug] = count
                                    else:
                                        if drug in drug_type_counts_units:
                                            drug_type_counts_units[drug] += count
                                        else:
                                            drug_type_counts_units[drug] = count

                            df_drug_types_kg = pd.DataFrame({
                                'Tipo de Droga': drug_type_counts_kg.keys(),
                                'Total (kg)': drug_type_counts_kg.values()
                            })

                            df_drug_types_units = pd.DataFrame({
                                'Tipo de Droga': drug_type_counts_units.keys(),
                                'Total (Unidades)': drug_type_counts_units.values()
                            })

                            st.write("Total de Drogas por Tipo:")

                            col5, col6 = st.columns(2)
                            with col5:
                                st.write("Total de Drogas por Tipo em kg:")
                                st.dataframe(df_drug_types_kg)
                            with col6:
                                st.write("Total de Drogas por Tipo em Unidades:")
                                st.dataframe(df_drug_types_units)

                    with occurrence_tab:
                        if occurrence == 'presos_apreendidos':
                            st.subheader(legend_mapping[occurrence])

                            monthly_occurrences = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()
                            df_monthly_occurrences = pd.DataFrame({
                                'Mês': monthly_occurrences.index.map(month_names_pt),
                                'Total de Ocorrências': monthly_occurrences.values
                            })

                            st.write("Total de Ocorrências por Mês:")

                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.dataframe(df_monthly_occurrences)
                            with col2:
                                fig1, ax1 = plt.subplots(figsize=(10, 6))
                                months_occurrences = df_monthly_occurrences['Mês']
                                counts_occurrences = df_monthly_occurrences['Total de Ocorrências']
                                bars_occurrences = ax1.bar(months_occurrences, counts_occurrences, width=0.6, color='lightgreen')
                                for bar in bars_occurrences:
                                    height = bar.get_height()
                                    ax1.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax1.set_xlabel('Mês')
                                ax1.set_ylabel('Total de Ocorrências')
                                ax1.set_title(f'Ocorrências Mensais de {legend_mapping[occurrence]} em {current_year}')
                                ax1.set_xticks(range(len(months_occurrences)))
                                ax1.set_xticklabels(months_occurrences, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig1)
                                plt.close(fig1)

                            monthly_arrests = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month)['qtd_presos'].sum()
                            df_monthly_arrests = pd.DataFrame({
                                'Mês': monthly_arrests.index.map(month_names_pt),
                                'Total de Presos Apreendidos': monthly_arrests.values
                            })

                            st.write("Total de Presos Apreendidos por Mês:")

                            col3, col4 = st.columns([1, 2])
                            with col3:
                                st.dataframe(df_monthly_arrests)
                            with col4:
                                fig2, ax2 = plt.subplots(figsize=(10, 6))
                                months_arrests = df_monthly_arrests['Mês']
                                counts_arrests = df_monthly_arrests['Total de Presos Apreendidos']
                                bars_arrests = ax2.bar(months_arrests, counts_arrests, width=0.6, color='skyblue')
                                for bar in bars_arrests:
                                    height = bar.get_height()
                                    ax2.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax2.set_xlabel('Mês')
                                ax2.set_ylabel('Total de Presos Apreendidos')
                                ax2.set_title(f'Total de Presos Apreendidos por Mês em {current_year}')
                                ax2.set_xticks(range(len(months_arrests)))
                                ax2.set_xticklabels(months_arrests, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig2)
                                plt.close(fig2)

                    with occurrence_tab:
                        if occurrence == 'mandados_prisao':
                            st.subheader(legend_mapping[occurrence])

                            monthly_occurrences = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()
                            df_monthly_occurrences = pd.DataFrame({
                                'Mês': monthly_occurrences.index.map(month_names_pt),
                                'Total de Ocorrências': monthly_occurrences.values
                            })

                            st.write("Total de Ocorrências por Mês:")

                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.dataframe(df_monthly_occurrences)
                            with col2:
                                fig1, ax1 = plt.subplots(figsize=(10, 6))
                                months_occurrences = df_monthly_occurrences['Mês']
                                counts_occurrences = df_monthly_occurrences['Total de Ocorrências']
                                bars_occurrences = ax1.bar(months_occurrences, counts_occurrences, width=0.6, color='lightgreen')
                                for bar in bars_occurrences:
                                    height = bar.get_height()
                                    ax1.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax1.set_xlabel('Mês')
                                ax1.set_ylabel('Total de Ocorrências')
                                ax1.set_title(f'Ocorrências Mensais de {legend_mapping[occurrence]} em {current_year}')
                                ax1.set_xticks(range(len(months_occurrences)))
                                ax1.set_xticklabels(months_occurrences, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig1)
                                plt.close(fig1)

                            monthly_warrants = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month)['qtd_mandados'].sum()
                            df_monthly_warrants = pd.DataFrame({
                                'Mês': monthly_warrants.index.map(month_names_pt),
                                'Total de Mandados de Prisão': monthly_warrants.values
                            })

                            st.write("Total de Mandados de Prisão por Mês:")

                            col3, col4 = st.columns([1, 2])
                            with col3:
                                st.dataframe(df_monthly_warrants)
                            with col4:
                                fig2, ax2 = plt.subplots(figsize=(10, 6))
                                months_warrants = df_monthly_warrants['Mês']
                                counts_warrants = df_monthly_warrants['Total de Mandados de Prisão']
                                bars_warrants = ax2.bar(months_warrants, counts_warrants, width=0.6, color='skyblue')
                                for bar in bars_warrants:
                                    height = bar.get_height()
                                    ax2.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax2.set_xlabel('Mês')
                                ax2.set_ylabel('Total de Mandados de Prisão')
                                ax2.set_title(f'Total de Mandados de Prisão por Mês em {current_year}')
                                ax2.set_xticks(range(len(months_warrants)))
                                ax2.set_xticklabels(months_warrants, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig2)
                                plt.close(fig2)

                    with occurrence_tab:
                        if occurrence == 'veiculos_recuperados':
                            st.subheader(legend_mapping[occurrence])

                            monthly_occurrences = data_current_year[data_current_year[occurrence] == 'SIM'].groupby(data_current_year['data'].dt.month).size()
                            df_monthly_occurrences = pd.DataFrame({
                                'Mês': monthly_occurrences.index.map(month_names_pt),
                                'Total de Ocorrências': monthly_occurrences.values
                            })

                            st.write("Total de Ocorrências por Mês:")

                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.dataframe(df_monthly_occurrences)
                            with col2:
                                fig1, ax1 = plt.subplots(figsize=(10, 6))
                                months_occurrences = df_monthly_occurrences['Mês']
                                counts_occurrences = df_monthly_occurrences['Total de Ocorrências']
                                bars_occurrences = ax1.bar(months_occurrences, counts_occurrences, width=0.6, color='lightgreen')
                                for bar in bars_occurrences:
                                    height = bar.get_height()
                                    ax1.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax1.set_xlabel('Mês')
                                ax1.set_ylabel('Total de Ocorrências')
                                ax1.set_title(f'Ocorrências Mensais de {legend_mapping[occurrence]} em {current_year}')
                                ax1.set_xticks(range(len(months_occurrences)))
                                ax1.set_xticklabels(months_occurrences, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig1)
                                plt.close(fig1)

                            def process_vehicle_types(vehicle_str):
                                try:
                                    vehicle_dict = ast.literal_eval(vehicle_str)
                                    return vehicle_dict
                                except (ValueError, SyntaxError):
                                    return {}

                            vehicle_type_counts = {
                                'CARRO': 0,
                                'MOTO': 0,
                                'CAMINHÃO': 0,
                                'ÔNIBUS': 0,
                                'BICICLETA': 0,
                                'OUTROS': 0
                            }

                            for vehicles in data_current_year[data_current_year[occurrence] == 'SIM']['tipos_veiculos']:
                                vehicles_dict = process_vehicle_types(vehicles)
                                for vehicle, count in vehicles_dict.items():
                                    if vehicle in vehicle_type_counts:
                                        vehicle_type_counts[vehicle] += count

                            df_vehicle_types = pd.DataFrame({
                                'Tipo de Veículo': vehicle_type_counts.keys(),
                                'Total': vehicle_type_counts.values()
                            })

                            st.write("Total de Veículos por Tipo:")

                            col3, col4 = st.columns([1, 2])
                            with col3:
                                st.dataframe(df_vehicle_types)
                            with col4:
                                fig2, ax2 = plt.subplots(figsize=(10, 6))
                                vehicle_types_labels = df_vehicle_types['Tipo de Veículo']
                                vehicle_types_counts = df_vehicle_types['Total']
                                bars_vehicle_types = ax2.bar(vehicle_types_labels, vehicle_types_counts, width=0.6, color='skyblue')
                                for bar in bars_vehicle_types:
                                    height = bar.get_height()
                                    ax2.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')
                                ax2.set_xlabel('Tipo de Veículo')
                                ax2.set_ylabel('Total')
                                ax2.set_title(f'Total de Veículos Recuperados por Tipo em {current_year}')
                                ax2.set_xticks(range(len(vehicle_types_labels)))
                                ax2.set_xticklabels(vehicle_types_labels, rotation=45, ha='right')
                                plt.tight_layout()
                                st.pyplot(fig2)
                                plt.close(fig2)

        with tab_estatisticas[5]:
            st.subheader("Produtividade")

            current_year = datetime.datetime.now().year

            data_current_year = data[data['data'].dt.year == current_year]

            monthly_sums = data_current_year.groupby(data_current_year['data'].dt.month)[colunas_ocorrencias].apply(lambda x: x.eq('SIM').sum()).sum(axis=1)

            monthly_data = pd.DataFrame({
                'Mês': monthly_sums.index.map(month_names_pt),
                'Total de Ocorrências': monthly_sums.values
            })

            col1, col2 = st.columns(2)

            with col1:
                st.write("Total de Ocorrências por Mês:")
                st.dataframe(monthly_data)

            with col2:
                st.write("Gráfico de Ocorrências por Mês:")
                fig, ax = plt.subplots(figsize=(8, 6))
                bars = ax.bar(monthly_data['Mês'], monthly_data['Total de Ocorrências'], color='skyblue')

                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2., height, f'{int(height)}', ha='center', va='bottom')

                ax.set_xlabel('Mês')
                ax.set_ylabel('Total de Ocorrências')
                ax.set_title('Produtividade Mensal')
                ax.set_xticks(range(len(monthly_data['Mês'])))
                ax.set_xticklabels(monthly_data['Mês'], rotation=45, ha='right')

                plt.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

# --- Login Page ---
def login_page():
    st.markdown("<h1 style='text-align: center;'>Sistema de Ocorrências Policiais</h1>", unsafe_allow_html=True)
    st.markdown("---")
    exibir_logos()

    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    col_login, col_create = st.columns(2)
    with col_login:
        if st.button("Entrar"):
            role = verify_user(username, password)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['role'] = role
                st.success(f"Bem-vindo(a), {username}!")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")
    with col_create:
        if st.button("Criar Nova Conta"):
            st.session_state['create_account'] = True
            st.rerun()


def create_account_page():
    st.title("Criar Nova Conta")
    st.markdown("---")

    new_username = st.text_input("Novo Usuário")
    new_password = st.text_input("Nova Senha", type="password")
    confirm_password = st.text_input("Confirme a Senha", type="password")

    if st.button("Registrar"):
        if new_password == confirm_password:
            if add_user(new_username, new_password):
                st.success("Conta criada com sucesso! Faça login para continuar.")
                st.session_state['create_account'] = False
                st.rerun()
            else:
                st.error("Nome de usuário já existe. Escolha outro.")
        else:
            st.error("As senhas não coincidem.")

    if st.button("Voltar ao Login"):
        st.session_state['create_account'] = False
        st.rerun()

if __name__ == "__main__":
    init_users_db()
    add_admin_user()

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'create_account' not in st.session_state:
        st.session_state['create_account'] = False
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'role' not in st.session_state:
        st.session_state['role'] = None

    if st.session_state['logged_in']:
        main_app()
        #if st.sidebar.button("Sair"):
            #st.session_state['logged_in'] = False
            #st.session_state['username'] = None
            #st.session_state['role'] = None
            #st.rerun()
    elif st.session_state['create_account']:
        create_account_page()
    else:
        login_page()