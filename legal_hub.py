import streamlit as st
import os
import io
import base64
import requests
import PyPDF2
import warnings
from docxtpl import DocxTemplate
from dotenv import load_dotenv
import google.generativeai as genai

warnings.filterwarnings("ignore")

# --- 1. GOVERNANÇA E SEGURANÇA ---
caminho_env = os.path.join(os.path.dirname(__file__), 'API.env')
load_dotenv(caminho_env)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLICKSIGN_TOKEN = os.getenv("CLICKSIGN_TOKEN")

# --- 2. CONFIGURAÇÃO BASE DA IA ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Configuração executiva: Temperatura 0.0 para precisão máxima
generation_config = {"temperature": 0.0, "top_p": 1.0, "top_k": 1}

# --- 3. INTERFACE DE USUÁRIO (UI) ---
st.set_page_config(page_title="CLM Sandbox | Enterprise Ops", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #e2e8f0; }
    h1, h2, h3, h4 { color: #ffffff !important; font-weight: 700 !important; }
    h1 span { color: #3b82f6; } 
    .stButton>button { background-color: #3b82f6 !important; color: white !important; font-weight: 800 !important; border-radius: 6px !important; width: 100% !important; border: none;}
    .stButton>button:hover { background-color: #2563eb !important; }
    .stTextInput>div>div>input { border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>⚖️ CLM Sandbox | <span>LegalOps Pipeline</span></h1><br>", unsafe_allow_html=True)

tab_outbound, tab_inbound = st.tabs(["📤 Outbound: Document Assembly & Routing", "📥 Inbound: IDP & Risk Matrix"])

# ==========================================
# MÓDULO 1: OUTBOUND (GERAÇÃO + CLICKSIGN)
# ==========================================
with tab_outbound:
    st.markdown("### Esteira de Geração e Roteamento de Assinaturas")
    uploaded_template = st.file_uploader("Upload do Master Template (.docx)", type="docx", key="outbound_up")

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
                col1, col2 = st.columns(2)
                
                contexto = {}
                for i, var in enumerate(sorted(variaveis)):
                    var_upper = var.upper()
                    label_bonito = var.replace("_", " ").title()
                    
                    if "VALOR" in var_upper or "PREÇO" in var_upper or "PRECO" in var_upper:
                        valor_num = st.number_input(f"💰 {label_bonito} (R$)", min_value=0.0, step=100.0, format="%.2f")
                        contexto[var] = f"{valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                    elif "DATA" in var_upper or "PRAZO" in var_upper:
                        data_sel = st.date_input(f"📅 {label_bonito}")
                        contexto[var] = data_sel.strftime("%d/%m/%Y")
                        
                    elif "CPF" in var_upper or "CNPJ" in var_upper or "DOCUMENTO" in var_upper:
                        col_tipo, col_num = st.columns([1, 2])
                        with col_tipo:
                            tipo_doc = st.selectbox("Tipo", ["CPF", "CNPJ"], key=f"tipo_{var}")
                        with col_num:
                            # CORREÇÃO DA UX: Nome limpo sem repetir a variável
                            contexto[var] = st.text_input(f"🪪 Número do {tipo_doc}")
                            
                    elif "ESTADO" in var_upper or "UF" in var_upper:
                        lista_uf = ["SP", "RJ", "MG", "ES", "PR", "SC", "RS", "MS", "MT", "GO", "DF", "BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI", "MA", "TO", "PA", "AP", "RR", "AM", "AC", "RO"]
                        contexto[var] = st.selectbox(f"🗺️ {label_bonito}", lista_uf)
                        
                    else:
                        contexto[var] = st.text_input(f"📝 {label_bonito}")
                
                st.markdown("---")
                st.markdown("#### 2. Roteamento de Assinatura (Clicksign)")
                st.caption("Preencha esta seção apenas se for enviar para assinatura digital via API.")
                
                col_nome, col_email = st.columns(2)
                with col_nome: sign_nome = st.text_input("Nome do Signatário Principal")
                with col_email: sign_email = st.text_input("E-mail do Signatário")

                st.markdown("<br>", unsafe_allow_html=True)
                
                # SEPARAÇÃO ESTRATÉGICA DOS BOTÕES
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    btn_baixar = st.form_submit_button("⬇️ 1. Apenas Gerar e Baixar (.docx)")
                with col_btn2:
                    btn_clicksign = st.form_submit_button("🚀 2. Assinar via Clicksign")

            # --- LÓGICA DE AÇÃO (Fora do formulário) ---
            if btn_baixar or btn_clicksign:
                
                # Passo comum: Gera o documento em memória independentemente do botão clicado
                doc.render(contexto)
                bio = io.BytesIO()
                doc.save(bio)
                arquivo_bytes = bio.getvalue()

                # Ação 1: Apenas Download
                if btn_baixar:
                    st.success("✅ Documento processado! Clique no botão abaixo para concluir o download.")
                    # O Streamlit renderiza um botão secundário de download real
                    st.download_button(
                        label="📥 Salvar arquivo no meu computador",
                        data=arquivo_bytes,
                        file_name="Contrato_Gerado.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )

                # Ação 2: Disparo via API Clicksign
                elif btn_clicksign:
                    if not CLICKSIGN_TOKEN:
                        st.error("🛑 Erro de Governança: Token da Clicksign ausente.")
                    elif not sign_nome or not sign_email:
                        st.warning("⚠️ Preencha Nome e E-mail do Signatário para rotear o documento.")
                    else:
                        with st.spinner("Injetando dados e roteando via API Clicksign..."):
                            url_base = "https://sandbox.clicksign.com/api/v1"
                            headers = {"Accept": "application/json", "Content-Type": "application/json"}
                            file_b64 = base64.b64encode(arquivo_bytes).decode('utf-8')

                            try:
                                # A. Upload
                                payload_doc = {
                                    "document": {
                                        "path": f"/clm_automatizado/Contrato_{sign_nome.replace(' ', '_')}.docx",
                                        "content_base64": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file_b64}"
                                    }
                                }
                                req_doc = requests.post(f"{url_base}/documents?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_doc)
                                if req_doc.status_code not in [200, 201, 202]:
                                    st.error(f"🛑 Clicksign recusou o documento: {req_doc.text}")
                                    st.stop()
                                doc_key = req_doc.json()['document']['key']

                                # B. Signatário
                                payload_signer = {"signer": {"email": sign_email, "auths": ["email"], "name": sign_nome, "has_documentation": False}}
                                req_signer = requests.post(f"{url_base}/signers?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_signer)
                                if req_signer.status_code not in [200, 201, 202]:
                                    st.error(f"🛑 Clicksign recusou o signatário: {req_signer.text}")
                                    st.stop()
                                signer_key = req_signer.json()['signer']['key']

                                # C. Roteamento
                                payload_list = {"list": {"document_key": doc_key, "signer_key": signer_key, "sign_as": "sign"}}
                                req_list = requests.post(f"{url_base}/lists?access_token={CLICKSIGN_TOKEN}", headers=headers, json=payload_list)
                                if req_list.status_code not in [200, 201, 202]:
                                    st.error(f"🛑 Erro ao criar o link: {req_list.text}")
                                    st.stop()

                                st.success(f"✅ Execução Concluída! Documento roteado com sucesso para {sign_email}.")
                            except Exception as e:
                                st.error(f"Erro crítico na arquitetura da requisição. Detalhes: {e}")

# ==========================================
# MÓDULO 2: INBOUND (IA MATRIX) - VISUAL DASHBOARD
# ==========================================
with tab_inbound:
    st.markdown("### Intelligent Document Processing & Risk Matrix")
    st.markdown("Auditoria de Primeiro Nível para documentos de terceiros.")
    
    uploaded_pdf = st.file_uploader("Upload do Contrato (.pdf)", type="pdf", key="inbound_up")
    
    if uploaded_pdf and st.button("Executar Due Diligence via LLM"):
        if not GEMINI_API_KEY:
            st.error("🛑 Erro de Governança: Chave API do Gemini ausente no arquivo API.env.")
        else:
            with st.spinner("Buscando motor compatível e executando Due Diligence..."):
                leitor_pdf = PyPDF2.PdfReader(uploaded_pdf)
                texto_contrato = "".join([pagina.extract_text() for pagina in leitor_pdf.pages])
                
                # PROMPT REFINADO PARA DEVOLVER JSON PURO
                prompt_enterprise = f"""
                Você é um Diretor de LegalOps avaliando um contrato recebido de terceiros.
                Aja de forma rigorosa, técnica e sem elogios. Avalie: Risco Financeiro, Compliance/LGPD, Risco Operacional e Governança/Foro.

                RETORNE ESTRITAMENTE UM ARQUIVO JSON VÁLIDO. Não inclua nenhuma outra palavra antes ou depois do JSON.
                Siga exatamente esta estrutura:
                {{
                  "risco_global": "Alto",
                  "achados": [
                    {{
                      "dimensao": "Nome da Dimensão (ex: Risco Financeiro)",
                      "titulo": "Resumo do Problema (ex: Multa Abusiva)",
                      "analise": "Explicação técnica detalhada do risco.",
                      "clausula": "Trecho exato do contrato entre aspas."
                    }}
                  ]
                }}
                
                CONTRATO: 
                {texto_contrato}
                """
                
                try:
                    # Sensor Dinâmico
                    modelos_validos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    if not modelos_validos:
                        st.stop()
                    modelo_escolhido = next((m for m in modelos_validos if 'flash' in m.lower()), modelos_validos[0])
                    
                    # Chamada da IA
                    modelo_auditor = genai.GenerativeModel(modelo_escolhido, generation_config=generation_config)
                    resposta = modelo_auditor.generate_content(prompt_enterprise)
                    
                    import json
                    # Tratamento do JSON
                    texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
                    dados = json.loads(texto_limpo)
                    
                    # --- CONSTRUÇÃO DO DASHBOARD VISUAL ---
                    st.divider()
                    st.markdown("## 📊 Relatório Executivo de Due Diligence")
                    
                    # Métrica de Risco Global com cores dinâmicas
                    risco = dados.get("risco_global", "Desconhecido").upper()
                    if "ALTO" in risco:
                        st.error(f"🚨 **RISCO GLOBAL DA OPERAÇÃO: {risco}**")
                    elif "MÉDIO" in risco:
                        st.warning(f"⚠️ **RISCO GLOBAL DA OPERAÇÃO: {risco}**")
                    else:
                        st.success(f"✅ **RISCO GLOBAL DA OPERAÇÃO: {risco}**")
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Gerando Cards Expansíveis (Acordeões) para cada cláusula
                    for achado in dados.get("achados", []):
                        with st.expander(f"📌 {achado['dimensao']} | {achado['titulo']}", expanded=True):
                            st.write(f"**Análise de Risco:** {achado['analise']}")
                            st.info(f"**Trecho Identificado:**\n\n_{achado['clausula']}_")
                            
                except json.JSONDecodeError:
                    st.error("Erro ao formatar o relatório. A IA não retornou um formato de dados estruturado.")
                except Exception as e_fatal:
                    st.error(f"Falha na comunicação com o Google AI. Erro detalhado: {e_fatal}")
