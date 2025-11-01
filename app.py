#!/usr/bin/env python3
"""
Aplicação Web - Tratamento Automatizado de Logs RAW LogRhythm para Power BI (.xlsx agrupando e somando valores iguais)

Autor: Pablo Nunes de Oliveira
Atualizado: 01/11/2025

Funcionalidades:
- Recebe arquivos RAW (.xls ou .xlsx)
- Limpa e extrai apenas colunas relevantes
- Agrupa valores iguais (tipo tabela dinâmica, por categoria) e soma
- Ordena coluna de soma do maior para o menor
- Salva SEMPRE em .xlsx (extensão correta)
- Renomeia a aba para o nome do arquivo
- Regra especial para arquivos TopImpactedHost corrige coluna Count deslocada
"""

from flask import Flask, request, send_file, render_template
import pandas as pd
import openpyxl
import xlrd
import os
import socket

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_COLS = [
    "Recipient", "Sum_LogCount", "Sender", "Impacted Host", "Count", "Origin Host", "Object",
    "Origin Login", "Threat Name", "Classification", "Event", "Log Host", "Total Logs",
    "Alarm Rule Name", "Total Count"
]

def treat_excel(file_path):
    """
    Lê arquivo .xls ou .xlsx, identifica cabeçalho, filtra colunas relevantes,
    agrupa automaticamente por coluna categórica e soma, ordena desc, 
    salva como .xlsx, renomeia a aba para o nome do arquivo.
    Regra especial: Se for TopImpactedHost, alinha a coluna Count.
    """
    ext_original = os.path.splitext(file_path)[1].lower()
    file_xlsx = os.path.splitext(file_path)[0] + '.xlsx'

    # Leitura conforme formato original
    if ext_original == '.xls':
        df = pd.read_excel(file_path, header=None, engine='xlrd')
    elif ext_original == '.xlsx':
        df = pd.read_excel(file_path, header=None, engine='openpyxl')
    else:
        return None

    filename = os.path.basename(file_path)

    # REGRA ESPECIAL TopImpactedHost: corrige a coluna COUNT deslocada apenas para esse caso
    if 'TopImpactedHost' in filename:
        # Busca cabeçalho (em qualquer linha) e aplica shift só na coluna Count
        found_header = None
        for idx in range(0, len(df)):
            row = df.iloc[idx].astype(str).tolist()
            if any(col in row for col in ALLOWED_COLS):
                found_header = idx
                header = row
                break
        if found_header is not None:
            data = df.iloc[found_header+1:].reset_index(drop=True)
            data.columns = header
            # Corrige deslocamento da coluna Count: sobe os valores uma linha
            if 'Count' in data.columns:
                data['Count'] = data['Count'].shift(-1)
                # Se sair uma linha a mais no fim, remove essa linha (onde Count vira NaN)
                data = data.dropna(subset=['Count'])
            relevantes = [c for c in header if any(col in c for col in ALLOWED_COLS)]
            data = data[relevantes]
        else:
            return None
    else:
        # FLUXO PADRÃO PARA DEMAIS ARQUIVOS
        # Busca cabeçalho a partir da linha 0 até o fim, para máxima compatibilidade
        found_header = None
        for idx in range(0, len(df)):
            row = df.iloc[idx].astype(str).tolist()
            if any(col in row for col in ALLOWED_COLS):
                found_header = idx
                header = row
                break
        if found_header is not None:
            data = df.iloc[found_header+1:]
            data.columns = header
            relevantes = [c for c in header if any(col in c for col in ALLOWED_COLS)]
            data = data[relevantes]
        else:
            return None

    data = data.dropna(how='all')

    # Detecta dinamicamente a coluna de soma (Count, Total Logs, Sum_LogCount) e a categórica
    col_soma = next((c for c in data.columns if 'Count' in c or 'Logs' in c), None)
    col_cat = [c for c in data.columns if c != col_soma][0] if col_soma and len(data.columns)>1 else None

    # Se possível, realiza o agrupamento, soma e ordenação descendente
    if col_soma and col_cat:
        data[col_soma] = pd.to_numeric(data[col_soma], errors='coerce')
        data = data.groupby(col_cat, as_index=False)[col_soma].sum()
        data = data.sort_values(by=col_soma, ascending=False)

    # Salva como .xlsx
    data.to_excel(file_xlsx, index=False)

    # Renomeia a aba
    wb = openpyxl.load_workbook(file_xlsx)
    aba_nome = os.path.splitext(os.path.basename(file_xlsx))[0]
    ws = wb.active
    ws.title = aba_nome
    wb.save(file_xlsx)

    return file_xlsx

@app.route('/', methods=['GET'])
def index():
    """Página inicial com drag-and-drop, seleção e botão."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Recebe o arquivo, processa e devolve sempre .xlsx, agrupado, ordenado, aba nomeada.
    """
    file = request.files['file']
    filename_base = os.path.splitext(file.filename)[0]
    raw_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(raw_path)
    file_xlsx = treat_excel(raw_path)
    if file_xlsx:
        download_name = filename_base + '.xlsx'
        return send_file(file_xlsx, as_attachment=True, download_name=download_name)
    else:
        return "Arquivo não contém cabeçalho relevante ou houve erro no tratamento!", 400

def get_local_ip():
    """Exibe IP local para facilitar o acesso em rede."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    ip = get_local_ip()
    print("="*60)
    print(f"Tratador Automático de Logs (.xlsx only, agrupamento dinâmico) disponível na rede:")
    print(f" --> http://{ip}:5000")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=True)
