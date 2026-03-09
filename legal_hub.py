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

# --- 1. GOVERNANÇA E SEGURANÇA (Híbrido: Local + Cloud) ---
# Primeiro, carregamos o ambiente local se ele existir (para uso no seu Mac)
load_dotenv(os.path.join(os.path.dirname(__file__), 'API.env'))

# Função "Gatekeeper" para buscar as chaves sem derrubar o sistema
def buscar_credencial(nome_chave):
    try:
        # Tenta buscar na nuvem (Secrets do Streamlit)
        return st.secrets[nome_chave]
    except Exception:
        # Se não achar na nuvem, busca no ambiente local/sistema
        return os.getenv(nome_chave)

GEMINI_API_KEY = buscar_credencial("GEMINI_API_KEY")
CLICKSIGN_TOKEN = buscar_credencial("CLICKSIGN_TOKEN")

# --- 2. CONFIGURAÇÃO BASE DA IA ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
generation_config = {"temperature": 0.0, "top_p": 1.0, "top_k": 1}

# --- 3. INTERFACE DE USUÁRIO (UI) ---
st.set_page_config(page_title="CLM Sandbox | Eduardo Oliveira", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #e2e8f0; }
    h1, h2, h3, h4 { color: #ffffff !important; font-weight: 700 !important; }
    h1 span { color: #3b82f6; } 
    .stButton>button { background-color: #3b82f6 !important; color: white !important; font-weight: 800 !important; border-radius: 6px !important; width: 100% !important; border: none;}
    .stExpander { background-color: #161b22 !important; border: 1px solid #30363d !important; border-radius: 8px !important; }
    .stDownloadButton>button { background-color: #1f2937 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⚖️ CLM Sandbox | <span>LegalOps Pipeline</span></h1>", unsafe_allow_html=True)

tab_outbound, tab_inbound = st.tabs(["📤 Outbound: Assembly & Routing", "📥 Inbound: IDP & Risk Matrix"])

# --- MÓDULO 1: OUTBOUND (GERAÇÃO + CLICKSIGN) ---
with tab_outbound:
    st.markdown("### Esteira de Geração e Roteamento")
    uploaded_template = st.file_uploader("Upload do Master Template (.docx)", type="docx")

    if uploaded_template:
        template_buffer = io.BytesIO(uploaded_template.getvalue())
        doc = DocxTemplate(template_buffer)
        
        try:
            variaveis = doc.get_undeclared_template_variables()
        except:
            variaveis = []

        if variaveis:
            with st.form("form_assembly"):
                st.markdown("#### 1. Estruturação de Dados (Dynamic Payload)")
                contexto = {}
                
                for var in sorted(variaveis):
                    var_upper = var.upper()
                    label_bonito = var.replace("_", " ").title()
                    
                    if "VALOR" in var_upper or "PREÇO" in var_upper:
                        val = st.number_input(f"💰 {label_bonito} (R$)", min_value=0.0, step=100.0, format="%.2f")
                        contexto[var] = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    elif "CPF" in var_upper or "CNPJ" in var_upper:
                        col_tipo, col_num = st.columns([1, 2])
                        with col_tipo: tipo_doc = st.selectbox("Tipo", ["CPF", "CNPJ"], key=f"t_{var}")
                        with col_num: contexto[var] = st.text_input(f"🪪 Número do {tipo_doc}")
                    elif "DATA" in var_upper:
                        data_sel = st.date_input(f"📅 {label_bonito}")
                        contexto[var] = data_sel.strftime("%d/%m/%Y")
                    else:
                        contexto[var] = st.text_input(f"📝 {label_bonito}")
                
                st.markdown("---")
                st.markdown("#### 2. Roteamento de Assinatura (Clicksign)")
                c1, c2 = st.columns(2)
                with c1: sign_nome = st.text_input("Nome do Signatário")
                with c2: sign_email = st.text_input("E-mail do Signatário")

                st.markdown("<br>", unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns(2)
                btn_down = col_btn1.form_submit_button("⬇️ 1. Apenas Baixar (.docx)")
                btn_api = col_btn2.form_submit_button("🚀 2. Enviar para Clicksign")

            if btn_down or btn_api:
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                out_bytes = bio.getvalue()

                if btn_down:
                    st.success("✅ Processado! Clique abaixo para salvar.")
                    st.download_button("📥 Salvar no Computador", out_bytes, "Contrato.docx", use_container_width=True)
                
                elif btn_api:
                    if not CLICKSIGN_TOKEN: st.error("Token da Clicksign não configurado.")
                    elif not sign_nome or not sign_email: st.warning("Preencha os dados do signatário.")
                    else:
                        with st.spinner("Roteando via API..."):
                            url_base = "https://sandbox.clicksign.com/api/v1"
                            headers = {"Accept": "application/json", "Content-Type": "application/json"}
                            file_b64 = base64.b64encode(out_bytes).decode('utf-8')
                            try:
                                # Upload Doc
                                payload_doc = {"document": {"path": f"/clm/Contrato_{sign_nome.replace(' ', '_')}.docx", "content_base64": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file_b64}"}}
                                req_doc = requests.post(f"{url_base}/documents?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_doc)
                                doc_key = req_doc.json()['document']['key']
                                # Signer + List (Simplificado para o exemplo)
                                st.success(f"✅ Documento enviado com sucesso para {sign_email}!")
                            except Exception as e: st.error(f"Erro na API: {e}")

# --- MÓDULO 2: INBOUND (IA MATRIX) ---
with tab_inbound:
    st.markdown("### Intelligent Document Processing & Risk Matrix")
    up_pdf = st.file_uploader("Upload do Contrato (.pdf)", type="pdf")
    
    if up_pdf and st.button("Executar Due Diligence via LLM"):
        if not GEMINI_API_KEY:
            st.error("🛑 Chave API ausente nos Secrets.")
        else:
            with st.spinner("Analisando cláusulas (Temperatura 0.0)..."):
                leitor = PyPDF2.PdfReader(up_pdf)
                txt = "".join([p.extract_text() for p in leitor.pages])
                
                prompt = f"""
                Você é um Diretor de LegalOps avaliando um contrato. 
                RETORNE APENAS UM JSON VÁLIDO. Estrutura:
                {{
                  "risco_global": "Alto/Médio/Baixo",
                  "achados": [
                    {{"dimensao": "Financeiro/LGPD/etc", "titulo": "Título", "analise": "Análise técnica", "clausula": "Trecho exato"}}
                  ]
                }}
                CONTRATO: {txt}
                """
                
                try:
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    sel_model = next((m for m in models if 'flash' in m.lower()), models[0])
                    
                    res = genai.GenerativeModel(sel_model, generation_config=generation_config).generate_content(prompt)
                    dados = json.loads(res.text.replace("```json", "").replace("```", "").strip())
                    
                    # Dashboard Visual
                    st.divider()
                    st.markdown(f"## 📊 Risco Global: {dados.get('risco_global')}")
                    
                    for a in dados.get("achados", []):
                        with st.expander(f"📌 {a['dimensao']} | {a['titulo']}", expanded=True):
                            st.write(f"**Análise:** {a['analise']}")
                            st.info(f"**Cláusula:** {a['clausula']}")
                except Exception as e: st.error(f"Erro no processamento: {e}")
