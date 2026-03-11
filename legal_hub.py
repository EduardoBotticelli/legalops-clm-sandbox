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

# --- 2. CONFIGURAÇÃO BASE DA IA ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
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
    .panel-title { font-size: 1rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.8rem; border-bottom: 1px solid #1E293B; padding-bottom: 0.5rem; }
    
    .stButton>button { background-color: #0284C7 !important; color: white !important; font-weight: 600 !important; border-radius: 6px !important; width: 100% !important; border: none; transition: all 0.2s; padding: 0.6rem 1rem !important;}
    .stButton>button:hover { background-color: #0369A1 !important; }
    
    .metric-container { background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column; justify-content: space-between; text-align: center;}
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #F8FAFC; margin-bottom: 4px; }
    .metric-title { font-size: 0.8rem; color: #64748B; font-weight: 600; text-transform: uppercase; }
    
    .stTextInput>div>div>input { background-color: #070B14 !important; color: white !important; border: 1px solid #334155 !important; }
    
    /* Esconder o label padrão do file_uploader para ficar mais limpo */
    [data-testid="stFileUploader"] label { display: none; }
    
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hub-header">
    <div class="hub-title">⚖️ CLM Hub <span>| Automação & Inteligência</span></div>
    <div style="font-size: 0.9rem; color: #64748B; letter-spacing: 2px;">CONTRACT LIFECYCLE MANAGEMENT</div>
</div>
""", unsafe_allow_html=True)

tab_inbound, tab_outbound = st.tabs(["🧠 Inbound: Revisão de IA", "📤 Outbound: Geração e Assinatura"])

# --- MÓDULO 1: INBOUND (IA MATRIX) ---
with tab_inbound:
    col_upload, col_result = st.columns([1, 2.2], gap="large")
    
    with col_upload:
        # Texto explicativo acoplado e margem inferior reduzida para integrar com o botão de upload
        st.markdown('''
        <div class="panel-card" style="margin-bottom: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: none;">
            <div class="panel-title">🧠 Auditoria Semântica</div>
            <p style="color: #94A3B8; font-size: 0.85rem; line-height: 1.5; margin-bottom: 0;">
                Faça o upload do seu contrato. A Inteligência Artificial fará a leitura completa do documento, identificará o nível de risco e destacará cláusulas abusivas ou ausentes.
            </p>
        </div>
        ''', unsafe_allow_html=True)
        
        up_pdf = st.file_uploader("Upload do Contrato (.pdf)", type="pdf")
        
        if st.button("Executar Due Diligence Contratual"):
            if not up_pdf: st.error("Insira um documento PDF.")
            elif not GEMINI_API_KEY: st.error("🛑 Chave de API Ausente.")
            else: st.session_state['run_ia'] = True

    with col_result:
        if st.session_state.get('run_ia', False) and up_pdf:
            with st.spinner("Analisando estrutura do contrato..."):
                try:
                    leitor = PyPDF2.PdfReader(up_pdf)
                    txt = "".join([p.extract_text() for p in leitor.pages])
                    
                    prompt = f"""Você é um Diretor de LegalOps avaliando um contrato. 
                    RETORNE APENAS UM JSON VÁLIDO. Estrutura:
                    {{
                      "risco_global": "Alto/Médio/Baixo",
                      "resumo": "Resumo clínico em 2 frases",
                      "achados": [
                        {{"dimensao": "LGPD/Financeiro/etc", "gravidade": "Alta/Media/Baixa", "titulo": "Título", "analise": "Análise técnica", "clausula": "Trecho exato"}}
                      ]
                    }}
                    CONTRATO: {txt}"""
                    
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    sel_model = next((m for m in models if 'flash' in m.lower()), models[0])
                    
                    res = genai.GenerativeModel(sel_model, generation_config=generation_config).generate_content(prompt)
                    dados = json.loads(res.text)
                    
                    r_global = dados.get("risco_global", "BAIXO").upper()
                    if "ALTO" in r_global: bg, border, icone = "#2A1215", "#EF4444", "🔴"
                    elif "MED" in r_global: bg, border, icone = "#2B2510", "#F59E0B", "🟡"
                    else: bg, border, icone = "#0B2416", "#10B981", "🟢"

                    st.markdown(f'''<div style="background:{bg}; border:1px solid {border}; border-radius:8px; padding:1.5rem; margin-bottom:1.5rem;">
                        <div style="font-size:1.15rem; font-weight:700; color:{border};">{icone} RISCO CONTRATUAL {r_global}</div>
                        <div style="font-size:0.9rem; color:#E2E8F0; margin-top:8px;">{dados.get("resumo", "")}</div></div>''', unsafe_allow_html=True)
                    
                    st.markdown("<div class='panel-title'>Inspeção de Cláusulas</div>", unsafe_allow_html=True)
                    for a in dados.get("achados", []):
                        cor_h = "#EF4444" if "ALTA" in a.get("gravidade", "").upper() else ("#F59E0B" if "MEDIA" in a.get("gravidade", "").upper() else "#10B981")
                        st.markdown(f"""<div style='background:#0B1120; border:1px solid #1E293B; border-left:3px solid {cor_h}; border-radius:6px; padding:1.2rem; margin-bottom:10px;'>
                            <div style='font-weight:700; color:#F8FAFC; margin-bottom:5px;'>{a.get('titulo')} ({a.get('dimensao')})</div>
                            <div style='font-size:0.85rem; color:#CBD5E1;'>{a.get('analise')}</div>
                            <div style='font-size:0.8rem; color:#64748B; margin-top:10px; font-family:monospace;'>"{a.get('clausula')}"</div></div>""", unsafe_allow_html=True)
                except Exception as e: st.error(f"Erro: {e}")

# --- MÓDULO 2: OUTBOUND (GERAÇÃO E CLICKSIGN) ---
with tab_outbound:
    # Instruções e Upload integrados
    st.markdown('''
    <div class="panel-card" style="margin-bottom: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: none;">
        <div class="panel-title">📄 1. Template Master (.docx)</div>
        <p style="color: #94A3B8; font-size: 0.85rem; margin-bottom: 0;">
            Carregue o modelo base do contrato em Word. O sistema identificará as variáveis (ex: {{nome}}) automaticamente para preenchimento.
        </p>
    </div>
    ''', unsafe_allow_html=True)
    
    up_docx = st.file_uploader("Upload do Template", type="docx")

    # Limpa a memória se o usuário trocar ou remover o arquivo
    if up_docx is None:
        st.session_state['pronto_para_assinar'] = False

    if up_docx:
        doc = DocxTemplate(io.BytesIO(up_docx.getvalue()))
        try: variaveis = doc.get_undeclared_template_variables()
        except: variaveis = []

        if not variaveis:
            st.warning("⚠️ Nenhuma variável {{...}} encontrada neste documento.")
        else:
            col_left, col_right = st.columns([1.5, 1], gap="large")
            
            with col_left:
                with st.form("f_gen"):
                    st.markdown('<div class="panel-title" style="border:none;">2. Preenchimento de Dados</div>', unsafe_allow_html=True)
                    contexto = {}
                    for var in sorted(variaveis):
                        var_up = var.upper()
                        if "CPF" in var_up or "CNPJ" in var_up:
                            c_t, c_n = st.columns([1, 2])
                            tipo = c_t.selectbox("Tipo", ["CPF", "CNPJ"], key=f"t_{var}")
                            contexto[var] = c_n.text_input(f"🪪 Número do {tipo}", key=f"v_{var}")
                        elif "VALOR" in var_up:
                            contexto[var] = st.number_input(f"💰 {var.replace('_',' ').title()}", format="%.2f")
                        else:
                            contexto[var] = st.text_input(f"📝 {var.replace('_',' ').title()}")
                    
                    btn_gen = st.form_submit_button("Gerar Contrato Oficial")

            # Lógica de renderização apenas ao clicar
            if btn_gen:
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                st.session_state['out_bytes'] = bio.getvalue()
                st.session_state['pronto_para_assinar'] = True

            # Coluna Direita (Sucesso, Download e Clicksign) só aparece se o doc foi gerado
            if st.session_state.get('pronto_para_assinar') and 'out_bytes' in st.session_state:
                with col_right:
                    st.markdown('<div class="panel-card" style="border-color:#3B82F6;">', unsafe_allow_html=True)
                    st.markdown('<div class="panel-title" style="color: #F8FAFC;">3. Assinatura e Envio</div>', unsafe_allow_html=True)
                    
                    st.success("✅ Documento Renderizado!")
                    st.download_button("📥 Baixar Arquivo Físico", st.session_state['out_bytes'], "Contrato_Final.docx", use_container_width=True)
                    
                    st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)
                    st.markdown("<p style='font-size:0.85rem; color:#94A3B8; margin-bottom:5px;'>Integração Clicksign API</p>", unsafe_allow_html=True)
                    
                    # Formulário de Assinatura
                    sign_nome = st.text_input("Nome do Signatário")
                    sign_email = st.text_input("E-mail corporativo")
                    
                    if st.button("🚀 Disparar Fluxo Clicksign"):
                        if not CLICKSIGN_TOKEN: 
                            st.error("Token da Clicksign ausente nas configurações.")
                        elif not sign_nome or not sign_email: 
                            st.warning("Preencha Nome e E-mail.")
                        else:
                            with st.spinner("Conectando ao servidor Clicksign..."):
                                try:
                                    url_base = "https://sandbox.clicksign.com/api/v1"
                                    headers = {"Accept": "application/json", "Content-Type": "application/json"}
                                    file_b64 = base64.b64encode(st.session_state['out_bytes']).decode('utf-8')
                                    payload_doc = {
                                        "document": {
                                            "path": f"/clm/Contrato_{sign_nome.replace(' ', '_')}.docx", 
                                            "content_base64": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file_b64}"
                                        }
                                    }
                                    req_doc = requests.post(f"{url_base}/documents?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_doc)
                                    
                                    if req_doc.status_code in [200, 201, 202]:
                                        st.success(f"✅ Protocolo enviado! (Signatário: {sign_email})")
                                    else:
                                        st.error(f"Erro Clicksign: {req_doc.text}")
                                except Exception as e: 
                                    st.error(f"Falha de Conexão: {e}")
                                    
                    st.markdown('</div>', unsafe_allow_html=True)
