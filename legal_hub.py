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

# --- 2. CONFIGURAÇÃO BASE DA IA (JSON MODE NATIVO) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Garante que a resposta da IA nunca vai quebrar o sistema
    generation_config = {"temperature": 0.0, "response_mime_type": "application/json"}

# --- 3. UI & CSS PREMIUM (SaaS) ---
st.set_page_config(page_title="CLM | LegalOps Hub", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #070B14; color: #F1F5F9; }
    
    /* Header */
    .hub-header { border-bottom: 1px solid #1E293B; padding-bottom: 1rem; margin-bottom: 2rem; margin-top: -1rem; text-align: center;}
    .hub-title { font-size: 2rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.5px; }
    .hub-title span { color: #3B82F6; font-weight: 400; }
    
    /* Cards */
    .panel-card { background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .panel-title { font-size: 1rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1.2rem; border-bottom: 1px solid #1E293B; padding-bottom: 0.5rem; }
    
    /* Botões Premium */
    .stButton>button { background-color: #0284C7 !important; color: white !important; font-weight: 600 !important; border-radius: 6px !important; width: 100% !important; border: none; transition: all 0.2s; padding: 0.6rem 1rem !important;}
    .stButton>button:hover { background-color: #0369A1 !important; }
    .stDownloadButton>button { background-color: #1E293B !important; border: 1px solid #334155 !important; }
    .stDownloadButton>button:hover { background-color: #334155 !important; }
    
    /* Tabs Customizadas */
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; }
    .stTabs [data-baseweb="tab"] { height: 3rem; white-space: pre-wrap; color: #94A3B8; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #3B82F6 !important; border-bottom-color: #3B82F6 !important; }
    
    /* Risk Metrics Box */
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
        st.markdown("<p style='color:#94A3B8; font-size:0.85rem;'>Carregue um contrato para análise preditiva de riscos, cláusulas abusivas e conformidade.</p>", unsafe_allow_html=True)
        up_pdf = st.file_uploader("", type="pdf")
        
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
            with st.spinner("Motor de IA a analisar estrutura semântica do contrato..."):
                try:
                    leitor = PyPDF2.PdfReader(up_pdf)
                    txt = "".join([p.extract_text() for p in leitor.pages])
                    
                    # Prompt estruturado para devolver JSON Exato
                    prompt = f"""
                    Você é um Diretor de LegalOps avaliando um contrato. 
                    Estrutura rigorosa do JSON esperado:
                    {{
                      "risco_global": "ALTO" (apenas ALTO, MEDIO ou BAIXO),
                      "resumo_executivo": "Sua avaliação em 2 frases clínicas",
                      "achados": [
                        {{
                          "dimensao": "ex: Financeiro, LGPD, Prazo", 
                          "gravidade": "ALTA, MEDIA ou BAIXA",
                          "titulo": "Título da observação", 
                          "analise": "Análise técnica", 
                          "clausula": "Trecho exato do PDF"
                        }}
                      ]
                    }}
                    CONTRATO: {txt}
                    """
                    
                    model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)
                    res = model.generate_content(prompt)
                    dados = json.loads(res.text) # Não precisa mais limpar, o Gemini garante o JSON.
                    
                    # Lógica de Cores Baseada no Risco Global
                    r_global = dados.get("risco_global", "BAIXO").upper()
                    if r_global == "ALTO": bg_c, border_c, icone = "#2A1215", "#EF4444", "🔴"
                    elif r_global == "MEDIO" or r_global == "MÉDIO": bg_c, border_c, icone = "#2B2510", "#F59E0B", "🟡"
                    else: bg_c, border_c, icone = "#0B2416", "#10B981", "🟢"

                    # 1. Resumo Executivo
                    st.markdown(f'''
                    <div style="background: {bg_c}; border: 1px solid {border_c}; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;">
                        <div style="font-size: 0.85rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; font-weight: 600;">Diagnóstico da Inteligência Artificial</div>
                        <div style="font-size: 1.15rem; font-weight: 700; margin-bottom: 10px; color: {border_c};">
                            {icone} RISCO CONTRATUAL {r_global}
                        </div>
                        <div style="font-size: 0.9rem; color: #E2E8F0; line-height: 1.5;">{dados.get("resumo_executivo", "")}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    # 2. Cartões de Métricas
                    qtd_alertas = len(dados.get("achados", []))
                    qtd_criticos = len([a for a in dados.get("achados", []) if "ALTA" in a.get("gravidade", "").upper()])
                    
                    st.markdown(f'''
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 2rem;">
                        <div class="metric-container"><div class="metric-value">{qtd_alertas}</div><div class="metric-title">Cláusulas Mapeadas</div></div>
                        <div class="metric-container"><div class="metric-value" style="color:#EF4444;">{qtd_criticos}</div><div class="metric-title">Apontamentos Críticos</div></div>
                        <div class="metric-container"><div class="metric-value" style="color:#38BDF8;">IA</div><div class="metric-title">Agente de Revisão</div></div>
                    </div>
                    ''', unsafe_allow_html=True)

                    # 3. Detalhamento de Achados
                    st.markdown("<div class='panel-title'>Inspeção de Cláusulas</div>", unsafe_allow_html=True)
                    for a in dados.get("achados", []):
                        cor_borda = "#EF4444" if "ALTA" in a.get("gravidade", "").upper() else ("#F59E0B" if "MEDIA" in a.get("gravidade", "").upper() else "#10B981")
                        st.markdown(f"""
                        <div style='background: #0B1120; border: 1px solid #1E293B; border-left: 3px solid {cor_borda}; border-radius: 6px; padding: 1.2rem; margin-bottom: 10px;'>
                            <div style='display: flex; justify-content: space-between; margin-bottom: 8px;'>
                                <span style='font-weight: 700; color: #F8FAFC;'>{a.get('titulo')}</span>
                                <span style='font-size: 0.7rem; background: #1E293B; padding: 2px 8px; border-radius: 12px; color: #94A3B8;'>{a.get('dimensao')}</span>
                            </div>
                            <div style='font-size: 0.85rem; color: #CBD5E1; margin-bottom: 10px;'>{a.get('analise')}</div>
                            <div style='font-size: 0.8rem; background: #070B14; padding: 8px; border-radius: 4px; color: #64748B; font-family: monospace;'>"{a.get('clausula')}"</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                except Exception as e:
                    st.error(f"Erro no processamento da IA: {e}")

# --- MÓDULO 2: OUTBOUND (GERAÇÃO + CLICKSIGN) ---
with tab_outbound:
    st.markdown('<div class="panel-card"><div class="panel-title">1. Motor de Geração (Upload do Master Template .docx)</div>', unsafe_allow_html=True)
    uploaded_template = st.file_uploader("", type="docx", key="up_outbound")
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_template:
        template_buffer = io.BytesIO(uploaded_template.getvalue())
        doc = DocxTemplate(template_buffer)
        try: variaveis = doc.get_undeclared_template_variables()
        except: variaveis = []

        if variaveis:
            col_form, col_sign = st.columns([1.5, 1], gap="large")
            
            with col_form:
                with st.form("form_assembly"):
                    st.markdown('<div class="panel-title" style="margin-bottom:0px; border-bottom: none;">2. Payload Dinâmico (Váriaveis do Contrato)</div>', unsafe_allow_html=True)
                    contexto = {}
                    
                    for var in sorted(variaveis):
                        var_upper = var.upper()
                        label = var.replace("_", " ").title()
                        
                        if "VALOR" in var_upper or "PREÇO" in var_upper:
                            val = st.number_input(f"💰 {label} (R$)", min_value=0.0, step=100.0, format="%.2f")
                            contexto[var] = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        elif "CPF" in var_upper or "CNPJ" in var_upper:
                            c_t, c_n = st.columns([1, 2])
                            tipo_doc = c_t.selectbox("Tipo", ["CPF", "CNPJ"], key=f"t_{var}")
                            contexto[var] = c_n.text_input(f"🪪 Número ({tipo_doc})")
                        elif "DATA" in var_upper:
                            contexto[var] = st.date_input(f"📅 {label}").strftime("%d/%m/%Y")
                        else:
                            contexto[var] = st.text_input(f"📝 {label}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_render = st.form_submit_button("Gerar Documento Oficial")

            if btn_render or st.session_state.get('doc_renderizado'):
                st.session_state['doc_renderizado'] = True
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                out_bytes = bio.getvalue()

                with col_sign:
                    st.markdown('<div class="panel-card" style="border-color: #3B82F6;">', unsafe_allow_html=True)
                    st.markdown('<div class="panel-title" style="color: #F8FAFC;">3. Roteamento de Assinatura</div>', unsafe_allow_html=True)
                    st.success("✅ Contrato Montado com Sucesso!")
                    
                    st.download_button("⬇️ Baixar Cópia (.docx)", out_bytes, "Contrato_Gerado.docx", use_container_width=True)
                    
                    st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)
                    st.markdown("<p style='font-size:0.85rem; color:#94A3B8; margin-bottom:5px;'>Integração Clicksign API</p>", unsafe_allow_html=True)
                    sign_nome = st.text_input("Nome do Signatário")
                    sign_email = st.text_input("E-mail corporativo")
                    
                    if st.button("🚀 Disparar Fluxo de Assinatura"):
                        if not CLICKSIGN_TOKEN: st.error("Token da Clicksign ausente nas configurações.")
                        elif not sign_nome or not sign_email: st.warning("Preencha Nome e E-mail.")
                        else:
                            with st.spinner("Comunicando com o servidor Clicksign..."):
                                try:
                                    url_base = "https://sandbox.clicksign.com/api/v1"
                                    headers = {"Accept": "application/json", "Content-Type": "application/json"}
                                    file_b64 = base64.b64encode(out_bytes).decode('utf-8')
                                    payload_doc = {"document": {"path": f"/clm/Contrato_{sign_nome.replace(' ', '_')}.docx", "content_base64": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file_b64}"}}
                                    req_doc = requests.post(f"{url_base}/documents?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_doc)
                                    if req_doc.status_code in [200, 201, 202]:
                                        st.success(f"✅ Protocolo enviado! (Signatário: {sign_email})")
                                    else:
                                        st.error(f"Erro Clicksign: {req_doc.text}")
                                except Exception as e: st.error(f"Falha de Conexão: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)
