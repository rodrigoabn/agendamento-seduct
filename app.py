import streamlit as st
from datetime import date, datetime
from fpdf import FPDF
from zoneinfo import ZoneInfo
from src.database import (
    obter_unidades_escolares, 
    obter_funcoes, 
    obter_agendamentos_por_data, 
    criar_agendamento, 
    excluir_agendamento,
    obter_link_login,         
    processar_retorno_login,  
    fazer_logout,
    verificar_login_admin,
    obter_relatorio_agendamentos,
    verificar_login_atendente,
    criar_atendente,
    atualizar_status_agendamento,
    obter_todos_atendentes,
    obter_agendamentos_filtro
)

# =========================================================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# =========================================================================

st.set_page_config(page_title="Agendamento SEDUCT", layout="wide", initial_sidebar_state="expanded")

# --- AJUSTE DE CSS PARA OS BOTÕES (4 LINHAS FIXAS) ---
st.markdown("""
    <style>
    /* Força o botão a respeitar o \\n e cria quebras de linha obrigatórias */
    .stButton button div[data-testid="stMarkdownContainer"] p {
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.5 !important;
    }
    /* Ajusta a altura do botão para caber todas as linhas com folga */
    .stButton button {
        height: auto !important;
        padding-top: 15px !important;
        padding-bottom: 15px !important;
    }
    </style>
""", unsafe_allow_html=True)


# =========================================================================
# LÓGICA DO LOGIN
# =========================================================================

if "code" in st.query_params:
    codigo = st.query_params["code"]
    usuario_supabase = processar_retorno_login(codigo)
    
    if usuario_supabase:
        email = usuario_supabase.email
        if email.endswith("@edu.campos.rj.gov.br"):
            st.session_state.usuario_logado = {"email": email, "is_admin": False, "is_atendente": False}
        else:
            st.error("Acesso restrito! Utilize seu e-mail institucional.")
            fazer_logout()
            
    st.query_params.clear()
    st.rerun()

# =========================================================================
# TELA DE LOGIN
# =========================================================================

if "usuario_logado" not in st.session_state:
    st.title("Agendamento de treinamento SUAP / CENSO ESCOLAR")
    st.write("Por favor, identifique-se para acessar o sistema.")
    st.divider()
    
    tab_usuario, tab_atendente, tab_admin = st.tabs(["👤 Sou Usuário", "🎧 Sou Atendente", "⚙️ Sou Administrador"])
    
    with tab_usuario:
        st.write("Acesso para servidores agendarem atendimento.")
        link_google = obter_link_login()
        botao_html = f"""
            <a href="{link_google}" target="_self" style="
                display: inline-block; padding: 0.5rem 1rem; background-color: #FF4B4B;
                color: white; text-decoration: none; border-radius: 0.5rem; font-weight: 600;
            ">Entrar com o Google(@edu)</a>
        """
        st.markdown(botao_html, unsafe_allow_html=True)
        
    with tab_atendente:
        st.write("Acesso para os atendentes do sistema.")
        email_atend = st.text_input("E-mail Atendente")
        senha_atend = st.text_input("Senha Atendente", type="password")
        if st.button("Entrar como Atendente", type="primary"):
            sucesso, dados_atend = verificar_login_atendente(email_atend, senha_atend)
            if sucesso:
                st.session_state.usuario_logado = {
                    "email": dados_atend['email'], 
                    "nome": dados_atend['nome'],
                    "is_admin": False,
                    "is_atendente": True
                }
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")

    with tab_admin:
        st.write("Acesso exclusivo para gestão geral.")
        email_admin = st.text_input("E-mail Administrador")
        senha_admin = st.text_input("Senha Admin", type="password")
        if st.button("Entrar como Admin", type="primary"):
            sucesso, dados_admin = verificar_login_admin(email_admin, senha_admin)
            if sucesso:
                st.session_state.usuario_logado = {
                    "email": dados_admin['email'], 
                    "nome": dados_admin['nome'],
                    "is_admin": True,
                    "is_atendente": False
                }
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")

    st.stop() 

# =========================================================================
# SISTEMA PRINCIPAL
# =========================================================================

unidades_db = obter_unidades_escolares()
mapa_unidades = {u['nome_unidade']: u['inep'] for u in unidades_db} if unidades_db else {}

funcoes_db = obter_funcoes()
mapa_funcoes = {f['nome']: f['id'] for f in funcoes_db} if funcoes_db else {}

def gerar_horarios():
    """Gera a lista de horários das 08:00 às 11:00 e 14:00 às 17:00 (30 min)"""
    horarios = []
    for hora in [8, 9, 10]:
        for minuto in [0, 30]:
            horarios.append(f"{hora:02d}:{minuto:02d}")
    horarios.append("11:00")
    for hora in [14, 15, 16]:
        for minuto in [0, 30]:
            horarios.append(f"{hora:02d}:{minuto:02d}")
    horarios.append("17:00")
    return horarios

# =========================================================================
# POPUP'S
# =========================================================================

@st.dialog("Cadastrar Atendimento")
def popup_agendamento(data_selecionada, horario):
    st.write(f"**Data:** {data_selecionada.strftime('%d/%m/%Y')} | **Horário:** {horario}")
    matricula = st.text_input("Matrícula")
    nome = st.text_input("Nome")
    unidade = st.selectbox("Unidade Escolar", ["Selecione..."] + list(mapa_unidades.keys()))
    funcao = st.selectbox("Função", ["Selecione..."] + list(mapa_funcoes.keys()))
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Concluir Cadastro", type="primary", use_container_width=True):
            if matricula and nome and unidade != "Selecione..." and funcao != "Selecione...":
                sucesso, _ = criar_agendamento(
                    data_selecionada, horario, matricula, nome, mapa_unidades[unidade], mapa_funcoes[funcao], st.session_state.usuario_logado["email"]
                )
                if sucesso:
                    st.success("Agendado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao agendar.")
            else:
                st.error("Preencha todos os campos.")
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

@st.dialog("Gerenciar Agendamento")
def popup_gerenciar(agendamento_id, data_selecionada, horario, nome_agendado, situacao_atual):
    st.write(f"**Agendamento:** {nome_agendado} - {data_selecionada.strftime('%d/%m/%Y')} às {horario}")
    st.write(f"**Status atual:** `{situacao_atual}`")
    
    is_admin = st.session_state.usuario_logado.get("is_admin", False)
    is_atendente = st.session_state.usuario_logado.get("is_atendente", False)
    email_logado = st.session_state.usuario_logado["email"]
    
    if (is_admin or is_atendente) and (situacao_atual == "Agendado" or not situacao_atual):
        st.divider()
        st.write("Ações do Atendimento:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Atendido", type="primary", use_container_width=True):
                if atualizar_status_agendamento(agendamento_id, "Atendido", email_logado):
                    st.success("Status atualizado!")
                    st.rerun()
        with col2:
            if st.button("❌ Não Compareceu", use_container_width=True):
                if atualizar_status_agendamento(agendamento_id, "Não Compareceu", email_logado):
                    st.warning("Falta registrada!")
                    st.rerun()
                    
    # Lógica alterada: O Administrador (is_admin) sempre pode excluir. Os demais, apenas se for "Agendado"
    if is_admin or situacao_atual == "Agendado" or not situacao_atual:
        st.divider()
        if st.button("🗑️ Excluir Agendamento", use_container_width=True):
            if excluir_agendamento(agendamento_id):
                st.success("Excluído!")
                st.rerun()
            else:
                st.error("Erro ao excluir.")
    else:
        st.divider()
        st.info("📌 Este agendamento já foi finalizado e o registro não pode mais ser excluído.")

@st.dialog("Cadastrar Novo Atendente")
def popup_cadastrar_atendente():
    st.write("Preencha os dados do novo atendente:")
    nome_atend = st.text_input("Nome Completo")
    mat_atend = st.text_input("Matrícula")
    email_atend = st.text_input("E-mail Institucional")
    senha_atend = st.text_input("Senha Temporária", type="password")
    
    if st.button("Salvar Atendente", type="primary", use_container_width=True):
        if nome_atend and mat_atend and email_atend and senha_atend:
            sucesso, msg = criar_atendente(email_atend, nome_atend, mat_atend, senha_atend)
            if sucesso:
                st.success("Atendente cadastrado com sucesso!")
            else:
                st.error("Erro: Este e-mail pode já estar cadastrado.")
        else:
            st.error("Preencha todos os campos.")

@st.dialog("Filtrar Atendimentos", width="large")
def popup_filtrar_atendimentos():
    st.write("Selecione o período e o atendente para visualizar o histórico.")
    
    todos_atendentes = obter_todos_atendentes()
    
    # Prepara a lista de opções para o Selectbox
    opcoes_atendentes = {"Todos os Atendentes": "Todos"}
    mapa_nomes_atendentes = {} # Para usar na tabela
    
    if todos_atendentes:
        for a in todos_atendentes:
            nome_exibicao = f"{a['nome']} ({a['email']})"
            opcoes_atendentes[nome_exibicao] = a['email']
            mapa_nomes_atendentes[a['email']] = a['nome']
        
    col1, col2 = st.columns(2)
    with col1:
        # st.date_input com uma tupla cria um range de datas (Início e Fim)
        data_range = st.date_input("Período (Início e Fim)", value=(date.today(), date.today()))
    with col2:
        atendente_selecionado = st.selectbox("Atendente", list(opcoes_atendentes.keys()))

    if st.button("🔍 Buscar Atendimentos", type="primary", use_container_width=True):
        # Verifica se o usuário selecionou o Início E o Fim no calendário
        if isinstance(data_range, tuple) and len(data_range) == 2:
            data_inicio, data_fim = data_range
            email_busca = opcoes_atendentes[atendente_selecionado]
            
            # Busca no banco
            dados = obter_agendamentos_filtro(data_inicio.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d'), email_busca)
            
            if dados:
                st.success(f"{len(dados)} registro(s) encontrado(s)!")
                
                # Dicionários para traduzir ID para Nomes na tabela
                unidades_reverse = {v: k for k, v in mapa_unidades.items()} if mapa_unidades else {}
                funcoes_reverse = {v: k for k, v in mapa_funcoes.items()} if mapa_funcoes else {}
                
                # Formata os dados para a tabela na tela
                dados_tabela = []
                for d in dados:
                    # Formata data
                    data_str = d.get('data', '')
                    if data_str:
                        try:
                            data_str = datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
                        except: pass
                    
                    id_escola = d.get('unidade_inep') or d.get('inep')
                    id_funcao = d.get('funcao_id') or d.get('id_funcao')
                    
                    dados_tabela.append({
                        "Data": data_str,
                        "Hora": d.get('horario', ''),
                        "Status": d.get('situacao', 'Agendado'),
                        "Atendido": d.get('nome', ''),
                        "Escola": unidades_reverse.get(id_escola, '-'),
                        "Função": funcoes_reverse.get(id_funcao, '-'),
                        "Atendente": mapa_nomes_atendentes.get(d.get('atendente_email'), '-')
                    })
                
                # Exibe a tabela interativa na tela
                st.dataframe(dados_tabela, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum atendimento encontrado para os filtros selecionados.")
        else:
            st.error("Por favor, selecione uma data de Início e uma data de Fim clicando no calendário.")
            
# =========================================================================
# GERAÇÃO DE PDF (RETRATO/A4)
# =========================================================================

def criar_pdf(dados, mes, ano, unidades_reverse, funcoes_reverse, mapa_atendentes):
    pdf = FPDF(orientation='P') # 'P' para Portrait (Vertical/Retrato)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Relatorio de Agendamentos SEDUCT - {mes:02d}/{ano}", ln=True, align='C')
    pdf.ln(5)
    
    # Cabeçalho da Tabela
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(20, 10, "Data", border=1)
    pdf.cell(10, 10, "Hora", border=1)
    pdf.cell(35, 10, "Nome Atendido", border=1)
    pdf.cell(50, 10, "Unidade Escolar", border=1)
    pdf.cell(30, 10, "Função", border=1)
    pdf.cell(18, 10, "Status", border=1)
    pdf.cell(27, 10, "Atendente", border=1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 7)
    for ag in dados:
        # Formatando Data
        data_bruta = ag.get('data', '')
        if isinstance(data_bruta, str) and data_bruta:
            try:
                data_formatada = datetime.strptime(data_bruta, '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                data_formatada = data_bruta
        elif data_bruta:
            data_formatada = data_bruta.strftime('%d/%m/%Y')
        else:
            data_formatada = "-"

        # Resgatando nomes e traduzindo
        nome = str(ag.get('nome', '')).encode('latin-1', 'replace').decode('latin-1')[:22]
        status = str(ag.get('situacao') or 'Agendado').encode('latin-1', 'replace').decode('latin-1')
        
        id_escola = ag.get('unidade_inep') or ag.get('inep')
        nome_escola = str(unidades_reverse.get(id_escola, '-')).encode('latin-1', 'replace').decode('latin-1')[:35]
        
        id_funcao = ag.get('funcao_id') or ag.get('id_funcao')
        nome_funcao = str(funcoes_reverse.get(id_funcao, '-')).encode('latin-1', 'replace').decode('latin-1')[:20]
        
        email_atend = ag.get('atendente_email')
        nome_atendente_real = mapa_atendentes.get(email_atend, '-') if email_atend else '-'
        atendente = str(nome_atendente_real).encode('latin-1', 'replace').decode('latin-1')[:18]
        
        # Desenhando linha
        pdf.cell(20, 10, data_formatada, border=1)
        pdf.cell(10, 10, str(ag.get('horario', '')), border=1)
        pdf.cell(35, 10, nome, border=1)
        pdf.cell(50, 10, nome_escola, border=1)
        pdf.cell(30, 10, nome_funcao, border=1)
        pdf.cell(18, 10, status, border=1)
        pdf.cell(27, 10, atendente, border=1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# =========================================================================
# MENU LATERAL E TELA PRINCIPAL
# =========================================================================

with st.sidebar:
    st.title("Agendamento SEDUCT")
    is_admin = st.session_state.usuario_logado.get("is_admin", False)
    is_atendente = st.session_state.usuario_logado.get("is_atendente", False)
    
    if is_admin:
        st.write(f"👑 **Administrador:** \n`{st.session_state.usuario_logado['nome']}`")
    elif is_atendente:
        st.write(f"🎧 **Atendente:** \n`{st.session_state.usuario_logado['nome']}`")
    else:
        st.write(f"👤 **Logado como:** \n`{st.session_state.usuario_logado['email']}`")
        
    st.divider()
    st.markdown("### 📅 Início / Agendamento")
    data_selecionada = st.date_input("Selecione a Data:", date.today(), format="DD/MM/YYYY")
    
    if is_admin:
        st.divider()
        st.markdown("### ⚙️ Gestão e Relatórios")
        
        if st.button("📋 Listar Atendimentos", use_container_width=True):
            popup_filtrar_atendimentos()
        
        if st.button("➕ Cadastrar Atendente", use_container_width=True):
            popup_cadastrar_atendente()
            
        st.write("") 
        
        col_mes, col_ano = st.columns(2)
        mes_rel = col_mes.selectbox("Mês", range(1, 13), index=date.today().month - 1)
        ano_rel = col_ano.selectbox("Ano", [2024, 2025, 2026], index=2)
        
        dados_relatorio = obter_relatorio_agendamentos(ano_rel, mes_rel)
        
        # Aviso verde de sucesso removido daqui. O botão de gerar PDF aparece diretamente se houver dados.
        if dados_relatorio:
            # Quando o botão PDF é clicado
            if st.button("Gerar Relatório PDF", type="primary", use_container_width=True):
                # Traduzindo IDs para o PDF
                unidades_reverse = {v: k for k, v in mapa_unidades.items()} if mapa_unidades else {}
                funcoes_reverse = {v: k for k, v in mapa_funcoes.items()} if mapa_funcoes else {}
                
                # Buscando os atendentes para mostrar o Nome
                todos_atendentes = obter_todos_atendentes()
                mapa_atendentes = {a['email']: a.get('nome', a['email']) for a in todos_atendentes} if todos_atendentes else {}

                pdf_bytes = criar_pdf(dados_relatorio, mes_rel, ano_rel, unidades_reverse, funcoes_reverse, mapa_atendentes)
                
                st.download_button(
                    label="Baixar Arquivo PDF 📥",
                    data=pdf_bytes,
                    file_name=f"Agendamentos_{mes_rel:02d}_{ano_rel}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.warning("Nenhum agendamento encontrado para este mês/ano.")

    st.divider()
    if st.button("Sair (Logout)"):
        fazer_logout()
        st.session_state.clear()
        st.rerun()

# --- TELA PRINCIPAL ---
st.header("Agendamento de Atendimento")
st.subheader(f"Horários para {data_selecionada.strftime('%d/%m/%Y')}")
st.divider()

# ---> NOVO: Pegando a data e hora atual EXATA de Brasília <---
fuso_br = ZoneInfo("America/Sao_Paulo")
agora = datetime.now(fuso_br)
hoje = agora.date()

# Criar dicionários reversos para buscar os nomes reais pelas IDs do banco
unidades_reverse = {v: k for k, v in mapa_unidades.items()} if mapa_unidades else {}
funcoes_reverse = {v: k for k, v in mapa_funcoes.items()} if mapa_funcoes else {}

agendamentos_do_dia = obter_agendamentos_por_data(data_selecionada)
mapa_agendamentos = {ag['horario']: ag for ag in agendamentos_do_dia} if agendamentos_do_dia else {}
horarios = gerar_horarios()

# Usando 3 colunas para os botões ficarem mais largos e caberem os textos
colunas_por_linha = 3 
for i in range(0, len(horarios), colunas_por_linha):
    cols = st.columns(colunas_por_linha)
    for j, col in enumerate(cols):
        if i + j < len(horarios):
            horario = horarios[i + j]
            
            if horario in mapa_agendamentos:
                agendamento = mapa_agendamentos[horario]
                situacao = agendamento.get("situacao", "Agendado")
                
                nome_usuario = agendamento.get('nome', 'Sem nome')
                id_escola = agendamento.get('unidade_inep') or agendamento.get('inep')
                id_funcao = agendamento.get('funcao_id') or agendamento.get('id_funcao')
                
                nome_escola = unidades_reverse.get(id_escola, 'Escola não informada')
                nome_funcao = funcoes_reverse.get(id_funcao, 'Função não informada')
                
                if situacao == "Atendido":
                    icone = "✅"
                elif situacao == "Não Compareceu":
                    icone = "❌"
                else:
                    if is_admin: icone = "👑"
                    elif is_atendente: icone = "🎧"
                    else: icone = "🔴"
                
                # Monta o texto limpo com o CSS forçando as 4 linhas
                texto_botao = f"{icone} {horario}\n{nome_usuario}\n{nome_escola}\n{nome_funcao}"
                
                if is_admin or is_atendente:
                    if col.button(texto_botao, key=f"btn_{horario}", use_container_width=True):
                        popup_gerenciar(agendamento["id"], data_selecionada, horario, nome_usuario, situacao)
                
                elif agendamento["usuario_email"] == st.session_state.usuario_logado["email"]:
                    texto_seu = f"🔵 {horario}\n{nome_usuario}\n{nome_escola}\n{nome_funcao}"
                    if col.button(texto_seu, key=f"btn_{horario}", use_container_width=True):
                        popup_gerenciar(agendamento["id"], data_selecionada, horario, "você", situacao)
                
                else:
                    texto_ocupado = f"{icone} {horario}\n[ Horário Ocupado ]\n\n"
                    col.button(texto_ocupado, key=f"btn_{horario}", disabled=True, use_container_width=True)
            
            else:
                # ---> NOVO: LÓGICA DE VALIDAÇÃO DE TEMPO NO PASSADO <---
                hora_str, min_str = horario.split(":")
                hora_slot, min_slot = int(hora_str), int(min_str)
                
                is_passado = False
                if data_selecionada < hoje:
                    is_passado = True
                elif data_selecionada == hoje:
                    # Verifica se a hora do slot já passou da hora atual
                    if hora_slot < agora.hour or (hora_slot == agora.hour and min_slot <= agora.minute):
                        is_passado = True

                # Se o horário já passou, desabilita o botão
                if is_passado:
                    texto_indisponivel = f"⚪ {horario}\n[ Horário Encerrado ]\n\n"
                    col.button(texto_indisponivel, key=f"btn_{horario}", disabled=True, use_container_width=True)
                else:
                    texto_livre = f"🟢 {horario}\n[ Horário Livre ]\n\n"
                    if col.button(texto_livre, key=f"btn_{horario}", use_container_width=True):
                        popup_agendamento(data_selecionada, horario)