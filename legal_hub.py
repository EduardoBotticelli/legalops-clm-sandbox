import streamlit as st
import os
import io
import time
import PyPDF2
import warnings
import json
from docxtpl import DocxTemplate
from dotenv import load_dotenv
import google.generativeai as genai

# Ocultar marcação do Streamlit (menu, footer, e logo)
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .viewerBadge_container__1QSob {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

warnings.filterwarnings("ignore")

# --- 1. GOVERNANÇA E SEGURANÇA ---
load_dotenv(os.path.join(os.path.dirname(__file__), 'API.env'))
def buscar_credencial(nome_chave):
    try: return st.secrets[nome_chave]
    except Exception: return os.getenv(nome_chave)

GEMINI_API_KEY = buscar_credencial("GEMINI_API_KEY")

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
    
    /* Header Principal */
    .hub-header { border-bottom: 1px solid #1E293B; padding-bottom: 1rem; margin-bottom: 2.5rem; margin-top: -1rem; text-align: center;}
    .hub-title { font-size: 2rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.5px; }
    .hub-title span { color: #3B82F6; font-weight: 400; }
    
    /* Títulos Nativos Estilizados */
    h4 { font-size: 1rem !important; font-weight: 600 !important; color: #94A3B8 !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; margin-bottom: 1.2rem !important; border-bottom: 1px solid #1E293B !important; padding-bottom: 0.5rem !important; margin-top: 1.5rem !important;}
    
    /* Botões Premium */
    .stButton>button { background-color: #0284C7 !important; color: white !important; font-weight: 600 !important; border-radius: 6px !important; width: 100% !important; border: none; transition: all 0.2s; padding: 0.6rem 1rem !important; margin-top: 10px;}
    .stButton>button:hover { background-color: #0369A1 !important; }
    
    /* Risk Metrics Box */
    .metric-container { background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.2rem; display: flex; flex-direction: column; justify-content: space-between; text-align: center;}
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #F8FAFC; margin-bottom: 4px; }
    .metric-title { font-size: 0.8rem; color: #64748B; font-weight: 600; text-transform: uppercase; }
    
    .stTextInput>div>div>input { background-color: #070B14 !important; color: white !important; border: 1px solid #334155 !important; }
    
    /* Esconder o label padrão do file_uploader e sujeiras visuais */
    [data-testid="stFileUploader"] label { display: none; }
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
        st.markdown('''
        <div style="background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="font-size: 1rem; font-weight: 600; color: #F8FAFC; margin-bottom: 0.8rem;">🧠 AUDITORIA SEMÂNTICA (IA)</div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
                Faça o upload do seu contrato em PDF. O motor de Inteligência Artificial fará a leitura integral do documento, identificará o nível de risco global e extrairá as cláusulas abusivas ou ausentes.
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        up_pdf = st.file_uploader("Upload do Contrato (.pdf)", type="pdf", key="inbound_upload")
        
        # Limpa o cache da IA se um novo arquivo for enviado
        current_pdf_id = up_pdf.file_id if up_pdf else None
        if st.session_state.get('last_pdf_id') != current_pdf_id:
            st.session_state['last_pdf_id'] = current_pdf_id
            st.session_state.pop('ia_results', None)
        
        if st.button("Executar Due Diligence Contratual"):
            if not up_pdf: 
                st.error("Por favor, anexe o documento PDF primeiro.")
            elif not GEMINI_API_KEY: 
                st.error("🛑 Chave de API Ausente.")
            else: 
                with st.spinner("Motor de IA mapeando os riscos do contrato..."):
                    try:
                        leitor = PyPDF2.PdfReader(up_pdf)
                        txt = "".join([p.extract_text() for p in leitor.pages])
                        
                        prompt = f"""Você é um Diretor de LegalOps avaliando um contrato. 
                        RETORNE APENAS UM JSON VÁLIDO. Estrutura:
                        {{
                          "risco_global": "Alto/Médio/Baixo",
                          "resumo": "Resumo clínico em 2 frases diretas.",
                          "achados": [
                            {{"dimensao": "Ex: LGPD / Financeiro / Prazo", "gravidade": "Alta/Media/Baixa", "titulo": "Título do Risco", "analise": "Sua análise técnica explicando o porquê do risco", "clausula": "Copie o trecho exato do texto"}}
                          ]
                        }}
                        CONTRATO: {txt}"""
                        
                        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        sel_model = next((m for m in models if 'flash' in m.lower()), models[0])
                        
                        res = genai.GenerativeModel(sel_model, generation_config=generation_config).generate_content(prompt)
                        # Salva o resultado na sessão para não recarregar
                        st.session_state['ia_results'] = res.text
                    except Exception as e: 
                        st.error(f"Erro ao processar a IA: {e}")

    with col_result:
        # Só renderiza se houver resultado salvo na sessão
        if 'ia_results' in st.session_state:
            try:
                dados = json.loads(st.session_state['ia_results'])
                
                r_global = dados.get("risco_global", "BAIXO").upper()
                if "ALTO" in r_global: bg, border, icone = "#2A1215", "#EF4444", "🔴"
                elif "MED" in r_global: bg, border, icone = "#2B2510", "#F59E0B", "🟡"
                else: bg, border, icone = "#0B2416", "#10B981", "🟢"
                
                # Resumo Executivo Elegante
                st.markdown(f'''<div style="background:{bg}; border:1px solid {border}; border-radius:8px; padding:1.8rem; margin-bottom:2.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                    <div style="font-size:1.2rem; font-weight:800; color:{border}; margin-bottom: 8px;">{icone} RISCO CONTRATUAL {r_global}</div>
                    <div style="font-size:0.95rem; color:#E2E8F0; line-height: 1.6;">{dados.get("resumo", "")}</div></div>''', unsafe_allow_html=True)
                
                st.markdown("#### Inspeção de Cláusulas")
                
                for a in dados.get("achados", []):
                    cor_h = "#EF4444" if "ALTA" in a.get("gravidade", "").upper() else ("#F59E0B" if "MEDIA" in a.get("gravidade", "").upper() else "#10B981")
                    st.markdown(f"""
                    <div style='background:#0B1120; border:1px solid #1E293B; border-left:4px solid {cor_h}; border-radius:8px; padding:1.5rem; margin-bottom:1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);'>
                        <div style='font-size:1.05rem; font-weight:700; color:#F8FAFC; margin-bottom:8px;'>
                            {a.get('titulo')} 
                            <span style='font-size:0.75rem; background:#1E293B; padding:4px 10px; border-radius:12px; color:#94A3B8; margin-left:10px; font-weight:600;'>{a.get('dimensao')}</span>
                        </div>
                        <div style='font-size:0.9rem; color:#CBD5E1; line-height: 1.5; margin-bottom: 12px;'>{a.get('analise')}</div>
                        <div style='font-size:0.85rem; background:#070B14; border: 1px solid #1E293B; padding:12px; border-radius:6px; color:#64748B; font-family:monospace; line-height:1.4;'>"{a.get('clausula')}"</div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e: 
                st.error(f"Erro ao exibir dados: {e}")

# --- MÓDULO 2: OUTBOUND (GERAÇÃO E MOCKUP DE ASSINATURA) ---
with tab_outbound:
    st.markdown('''
    <div style="background: #0B1120; border: 1px solid #1E293B; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div style="font-size: 1rem; font-weight: 600; color: #F8FAFC; margin-bottom: 0.8rem;">📄 1. TEMPLATE MASTER (.DOCX)</div>
        <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.5;">
            Carregue o modelo padrão do contrato em Word. O sistema fará a varredura automática procurando por marcações (ex: {{nome_cliente}}) e criará os campos de preenchimento abaixo.
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    up_docx = st.file_uploader("Upload do Template", type="docx", key="outbound_upload")
    current_file_id = up_docx.file_id if up_docx else None
    
    # Limpa dados de geração se o template mudar
    if st.session_state.get('last_file_id') != current_file_id:
        st.session_state['last_file_id'] = current_file_id
        st.session_state.pop('out_bytes', None)
        st.session_state.pop('pronto_para_assinar', None)
        
    if up_docx:
        doc = DocxTemplate(io.BytesIO(up_docx.getvalue()))
        try: variaveis = doc.get_undeclared_template_variables()
        except: variaveis = []
        
        if not variaveis:
            st.warning("⚠️ O sistema não encontrou nenhuma variável (chaves {{...}}) neste documento. Altere o Word e tente novamente.")
        else:
            col_left, col_right = st.columns([1.5, 1], gap="large")
            
            with col_left:
                with st.form("f_gen"):
                    st.markdown('#### 2. Preenchimento de Dados')
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
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_gen = st.form_submit_button("Gerar Contrato Oficial")
                    
            if btn_gen:
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                st.session_state['out_bytes'] = bio.getvalue()
                st.session_state['pronto_para_assinar'] = True
                
            if st.session_state.get('pronto_para_assinar') and 'out_bytes' in st.session_state:
                with col_right:
                    st.markdown('#### 3. Assinatura e Envio')
                    st.success("✅ Documento Pronto e Renderizado!")
                    st.download_button("📥 Baixar Arquivo Físico (.docx)", st.session_state['out_bytes'], "Contrato_Final.docx", use_container_width=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    with st.container():
                        st.markdown("<div style='font-size: 0.9rem; font-weight: 600; color: #38BDF8; margin-bottom: 10px;'>Simulador de Assinatura (Sandbox)</div>", unsafe_allow_html=True)
                        sign_nome = st.text_input("Nome do Signatário", placeholder="João da Silva")
                        sign_email = st.text_input("E-mail corporativo", placeholder="joao@empresa.com")
                        
                        if st.button("🚀 Simular Disparo via API"):
                            if not sign_nome or not sign_email: 
                                st.warning("⚠️ Preencha Nome e E-mail do Signatário para simular o envio.")
                            else:
                                with st.spinner("Orquestrando disparo via API (Sandbox)..."):
                                    time.sleep(1.5) # Simula latência de rede
                                    
                                    st.info(f"""
                                    **🟢 Fluxo Orquestrado com Sucesso!**
                                    
                                    **Ambiente Sandbox:** Em uma operação real (Produção), este documento seria disparado via integração e o signatário **{sign_nome}** receberia um alerta no e-mail **{sign_email}**.
                                    
                                    *Para fins de demonstração neste portfólio, a API externa foi substituída por este simulador. O fluxo encerra com a disponibilização do download do contrato acima.*
                                    """)
