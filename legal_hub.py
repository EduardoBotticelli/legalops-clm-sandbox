import streamlit as st
import os
import io
import base64
import requests
import PyPDF2
import warnings
import json
from docxtpl import DocxTemplate
from dotenv import load_dotenv
import google.generativeai as genai

warnings.filterwarnings("ignore")

# --- 1. GOVERNANÇA E SEGURANÇA ---
load_dotenv(os.path.join(os.path.dirname(__file__), 'API.env'))

def buscar_credencial(nome_chave):
    try: return st.secrets[nome_chave]
    except Exception: return os.getenv(nome_chave)

GEMINI_API_KEY = buscar_credencial("GEMINI_API_KEY")
CLICKSIGN_TOKEN = buscar_credencial("CLICKSIGN_TOKEN")

# --- 2. CONFIGURAÇÃO BASE DA IA (CORREÇÃO DO MODELO) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Mudança para 'latest' resolve o erro 404 de versão
    generation_config = {"temperature": 0.0, "response_mime_type": "application/json"}

# --- 3. UI & CSS PREMIUM ---
st.set_page_config(page_title="CLM | LegalOps Hub", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #070B14; color: #F1F5F9; }
    .hub-header { border-bottom: 1px solid #1E293B; padding-bottom: 1rem; margin-bottom: 2rem; margin-top: -1rem; text-align: center;}
    .hub-title { font-size: 2rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.5px; }
    .hub-title span { color: #3B82F6; font-weight: 400; }
    .panel-card { background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .panel-title { font-size: 1rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1.2rem; border-bottom: 1px solid #1E293B; padding-bottom: 0.5rem; }
    .stButton>button { background-color: #0284C7 !important; color: white !important; font-weight: 600 !important; border-radius: 6px !important; width: 100% !important; border: none; transition: all 0.2s; padding: 0.6rem 1rem !important;}
    .stButton>button:hover { background-color: #0369A1 !important; }
    .metric-container { background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column; justify-content: space-between; text-align: center;}
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #F8FAFC; margin-bottom: 4px; }
    .metric-title { font-size: 0.8rem; color: #64748B; font-weight: 600; text-transform: uppercase; }
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hub-header">
    <div class="hub-title">⚖️ CLM Hub <span>| Automação & Inteligência</span></div>
    <div style="font-size: 0.9rem; color: #64748B; letter-spacing: 2px;">CONTRACT LIFECYCLE MANAGEMENT</div>
</div>
""", unsafe_allow_html=True)

tab_inbound, tab_outbound = st.tabs(["🧠 Inbound: Revisão de Contratos (IA)", "📤 Outbound: Geração e Assinatura"])

# --- MÓDULO 1: INBOUND (IA MATRIX) ---
with tab_inbound:
    col_upload, col_result = st.columns([1, 2.2], gap="large")
    
    with col_upload:
        st.markdown('<div class="panel-card"><div class="panel-title">Módulo de Auditoria (IA)</div>', unsafe_allow_html=True)
        up_pdf = st.file_uploader("Upload do Contrato (.pdf)", type="pdf")
        
        if st.button("Executar Due Diligence Contratual"):
            if not up_pdf:
                st.error("Insira um documento PDF.")
            elif not GEMINI_API_KEY:
                st.error("🛑 Chave de API Ausente.")
            else:
                st.session_state['run_ia'] = True
        st.markdown('</div>', unsafe_allow_html=True)

    with col_result:
        if st.session_state.get('run_ia', False) and up_pdf:
            with st.spinner("Analisando contrato..."):
                try:
                    leitor = PyPDF2.PdfReader(up_pdf)
                    txt = "".join([p.extract_text() for p in leitor.pages])
                    
                    prompt = f"Avalie os riscos deste contrato e retorne um JSON com risco_global (ALTO/MEDIO/BAIXO), resumo_executivo e lista de achados (dimensao, gravidade, titulo, analise, clausula). CONTRATO: {txt}"
                    
                    # CORREÇÃO DO NOME DO MODELO PARA EVITAR 404
                    model = genai.GenerativeModel("gemini-1.5-flash-latest", generation_config=generation_config)
                    res = model.generate_content(prompt)
                    dados = json.loads(res.text)
                    
                    r_global = dados.get("risco_global", "BAIXO").upper()
                    if r_global == "ALTO": bg_c, border_c, icone = "#2A1215", "#EF4444", "🔴"
                    elif "MED" in r_global: bg_c, border_c, icone = "#2B2510", "#F59E0B", "🟡"
                    else: bg_c, border_c, icone = "#0B2416", "#10B981", "🟢"

                    st.markdown(f'<div style="background:{bg_c}; border:1px solid {border_c}; border-radius:8px; padding:1.5rem; margin-bottom:1.5rem;">'
                                f'<div style="font-size:1.15rem; font-weight:700; color:{border_c};">{icone} RISCO CONTRATUAL {r_global}</div>'
                                f'<div style="font-size:0.9rem; color:#E2E8F0; margin-top:8px;">{dados.get("resumo_executivo")}</div></div>', unsafe_allow_html=True)
                    
                    for a in dados.get("achados", []):
                        st.markdown(f"<div style='background:#0B1120; border:1px solid #1E293B; border-radius:6px; padding:1.2rem; margin-bottom:10px;'>"
                                    f"<b>{a.get('titulo')}</b><br><small>{a.get('analise')}</small></div>", unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"Erro no processamento da IA: {e}")

# --- MÓDULO 2: OUTBOUND (CORREÇÃO DE BOTÃO SUMIDO) ---
with tab_outbound:
    st.markdown('<div class="panel-card"><div class="panel-title">1. Motor de Geração (Upload do Template .docx)</div>', unsafe_allow_html=True)
    uploaded_template = st.file_uploader("", type="docx")
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_template:
        template_buffer = io.BytesIO(uploaded_template.getvalue())
        doc = DocxTemplate(template_buffer)
        try: variaveis = doc.get_undeclared_template_variables()
        except: variaveis = []

        # CORREÇÃO: Mostrar aviso se o arquivo estiver sem variáveis
        if not variaveis:
            st.warning("⚠️ Este documento não possui variáveis detectadas (ex: {{nome}}). Adicione etiquetas no Word para habilitar o formulário.")
        else:
            col_form, col_sign = st.columns([1.5, 1], gap="large")
            with col_form:
                with st.form("form_assembly"):
                    st.markdown('<div class="panel-title" style="border-bottom:none;">2. Preenchimento de Dados</div>', unsafe_allow_html=True)
                    contexto = {}
                    for var in sorted(variaveis):
                        contexto[var] = st.text_input(f"📝 {var.replace('_', ' ').title()}")
                    btn_render = st.form_submit_button("Gerar Documento Oficial")

            if btn_render:
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                st.session_state['out_bytes'] = bio.getvalue()

            if 'out_bytes' in st.session_state:
                with col_sign:
                    st.markdown('<div class="panel-card" style="border-color:#3B82F6;">', unsafe_allow_html=True)
                    st.success("✅ Documento Pronto!")
                    st.download_button("⬇️ Baixar Cópia", st.session_state['out_bytes'], "Contrato_Gerado.docx")
                    st.markdown('</div>', unsafe_allow_html=True)
