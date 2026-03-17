import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from zoneinfo import ZoneInfo

# 1. Inicia a conexão com o Supabase de forma otimizada (em cache)
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# 2. Busca as unidades escolares que estão com ativo = true
def obter_unidades_escolares():
    resposta = supabase.table("unidades_escolares") \
        .select("inep, nome_unidade") \
        .eq("ativo", True) \
        .order("nome_unidade") \
        .execute()
    return resposta.data

# 3. Busca os cargos/funções cadastrados
def obter_funcoes():
    resposta = supabase.table("funcoes") \
        .select("id, nome") \
        .order("nome") \
        .execute()
    return resposta.data

# 4. Busca os agendamentos de uma data específica
def obter_agendamentos_por_data(data_busca):
    # Converte a data do Streamlit para texto no formato do banco (YYYY-MM-DD)
    data_str = data_busca.strftime('%Y-%m-%d')
    resposta = supabase.table("agendamentos") \
        .select("*") \
        .eq("data", data_str) \
        .execute()
    return resposta.data

# 5. Salva um novo agendamento no banco
def criar_agendamento(data, horario, matricula, nome, unidade_inep, funcao_id, usuario_email):
    dados = {
        "data": data.strftime('%Y-%m-%d'),
        "horario": horario,
        "matricula": matricula,
        "nome": nome,
        "unidade_inep": unidade_inep,
        "funcao_id": funcao_id,
        "usuario_email": usuario_email
    }
    
    # Tratamento para evitar que o app quebre se duas pessoas clicarem juntas
    try:
        resposta = supabase.table("agendamentos").insert(dados).execute()
        return True, resposta.data
    except Exception as e:
        # Se cair aqui, provavelmente violou a regra UNIQUE (alguém pegou o horário antes)
        return False, str(e)

# 6. Exclui um agendamento (somente o próprio usuário ou admin poderão chamar isso depois)
def excluir_agendamento(agendamento_id):
    try:
        supabase.table("agendamentos").delete().eq("id", agendamento_id).execute()
        return True
    except Exception as e:
        return False


# --- NOVAS FUNÇÕES DE AUTENTICAÇÃO E RELATÓRIOS ---

def obter_link_login():
    """Gera o link de autenticação seguro do Google via Supabase"""
    resposta = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            # Redireciona de volta para o app local
            "redirect_to": "https://agendamento-treinamento.streamlit.app" 
        }
    })
    return resposta.url

def processar_retorno_login(auth_code):
    """Troca o código de retorno do Google por uma sessão real do usuário"""
    try:
        resposta = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
        return resposta.user
    except Exception as e:
        return None

def fazer_logout():
    """Encerra a sessão no Supabase"""
    supabase.auth.sign_out()

def verificar_login_admin(email, senha):
    """Verifica se o email e senha batem com a tabela de administradores"""
    try:
        response = supabase.table('administradores').select('*').eq('email', email).eq('senha', senha).execute()
        if response.data:
            return True, response.data[0]
        return False, None
    except Exception as e:
        print("Erro no login admin:", e)
        return False, None

def obter_relatorio_agendamentos(ano, mes):
    """Busca todos os agendamentos de um mês e ano específicos"""
    try:
        data_inicio = f"{ano}-{mes:02d}-01"
        if mes == 12:
            data_fim = f"{ano+1}-01-01"
        else:
            data_fim = f"{ano}-{mes+1:02d}-01"
            
        response = supabase.table('agendamentos').select(
            '*'
        ).gte('data', data_inicio).lt('data', data_fim).order('data').order('horario').execute()
        
        return response.data
    except Exception as e:
        print("Erro ao gerar relatório:", e)
        return []

def verificar_login_atendente(email, senha):
    """Verifica se o email e senha batem com a tabela de atendentes"""
    try:
        response = supabase.table('atendentes').select('*').eq('email', email).eq('senha', senha).execute()
        if response.data:
            return True, response.data[0]
        return False, None
    except Exception as e:
        print("Erro no login de atendente:", e)
        return False, None

def criar_atendente(email, nome, matricula, senha):
    """Salva um novo atendente no banco de dados"""
    try:
        dados = {
            "email": email,
            "nome": nome,
            "matricula": matricula,
            "senha": senha
        }
        response = supabase.table('atendentes').insert(dados).execute()
        return True, response.data
    except Exception as e:
        print("Erro ao criar atendente:", e)
        return False, str(e)

def atualizar_status_agendamento(agendamento_id, status, atendente_email):
    """Atualiza a situação do agendamento (Atendido ou Não Compareceu)"""
    try:
        # Pega a data e hora exata de BRASÍLIA
        fuso_br = ZoneInfo("America/Sao_Paulo")
        agora = datetime.now(fuso_br).isoformat()
        
        dados = {
            "situacao": status,
            "horario_atendimento": agora,
            "atendente_email": atendente_email
        }
        response = supabase.table('agendamentos').update(dados).eq('id', agendamento_id).execute()
        return True
    except Exception as e:
        print("Erro ao atualizar status:", e)
        return False

def obter_todos_atendentes():
    """Busca todos os atendentes para mapear e-mail -> nome no PDF"""
    try:
        response = supabase.table('atendentes').select('email, nome').execute()
        return response.data
    except Exception as e:
        print("Erro ao buscar atendentes:", e)
        return []

def obter_agendamentos_filtro(data_inicio, data_fim, email_atendente=None):
    """Busca agendamentos por um período de datas e opcionalmente por atendente"""
    try:
        # Busca maior ou igual (gte) à data_inicio e menor ou igual (lte) à data_fim
        query = supabase.table('agendamentos').select('*').gte('data', data_inicio).lte('data', data_fim)
        
        # Se um atendente específico for escolhido, aplica o filtro de email
        if email_atendente and email_atendente != "Todos":
            query = query.eq('atendente_email', email_atendente)
            
        response = query.order('data').order('horario').execute()
        return response.data
    except Exception as e:
        print("Erro ao filtrar agendamentos:", e)
        return []