import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import os

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Análise de Contas a Pagar")

# --- Funções de Formatação ---
def format_currency_brl(valor, simbolo_moeda="R$"):
    """Formata um valor numérico para o formato de moeda BRL."""
    if pd.isna(valor):
        return ''
    try:
        return f"{simbolo_moeda} {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "Valor inválido"

def format_date_br(data):
    """Formata uma data para o formato DD/MM/YYYY."""
    if pd.isna(data):
        return ''
    return data.strftime('%d/%m/%Y')

# --- Funções de Estilo para DataFrames ---
def highlight_overdue(row):
    """
    Destaca linhas com 'Data Vencimento' anterior à data atual em vermelho.
    Assume que a coluna já foi renomeada para 'Data Vencimento'.
    """
    today = pd.to_datetime('today').normalize() # Normalize para comparar apenas a data, sem hora
    
    # Verifica se a coluna 'Data Vencimento' existe e se o valor não é nulo antes de comparar
    if 'Data Vencimento' in row.index and pd.notna(row['Data Vencimento']) and row['Data Vencimento'] < today:
        return ['background-color: #f8230f'] * len(row) # Vermelho claro
    return [''] * len(row)

# --- Carregamento de Dados ---
INPUT_CSV_FILE = 'contas_pagar.csv'

@st.cache_data
def load_data_from_csv():
    """
    Carrega os dados do arquivo CSV, realiza a conversão de tipos
    e o pré-processamento necessário.
    """
    if not os.path.exists(INPUT_CSV_FILE):
        st.error(f"Erro: O arquivo '{INPUT_CSV_FILE}' não foi encontrado. Por favor, execute 'extract_data.py' primeiro para gerar o CSV.")
        st.stop()

    df = pd.read_csv(INPUT_CSV_FILE)

    df['data_emissao'] = pd.to_datetime(df['data_emissao'], errors='coerce')
    df['data_vencimento'] = pd.to_datetime(df['data_vencimento'], errors='coerce')
    df['data_quitacao'] = pd.to_datetime(df['data_quitacao'], errors='coerce')

    for col in ['valor_documento', 'valor_desconto', 'valor_saldo']:
        df[col] = df[col].astype(str).str.replace(',', '.')
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['fornecedor'] = df['fornecedor'].fillna('Fornecedor Não Informado')
    df['descricao_tipo_documento'] = df['descricao_tipo_documento'].fillna('Não Informado')

    df['numero_documento_base'] = df['numero_documento'].apply(lambda x: x.split('/')[0] if isinstance(x, str) and '/' in x else str(x))

    return df

df = load_data_from_csv()

# --- Funções de Análise ---
def get_valor_total_contas_a_pagar_aberto_mes(df_filtered, mes_referencia):
    """Calcula o valor total das contas em aberto para um determinado mês."""
    df_aberto = df_filtered[
        (df_filtered['status_documento'].str.lower() == 'aberto') &
        (df_filtered['data_vencimento'].dt.month == mes_referencia.month) &
        (df_filtered['data_vencimento'].dt.year == mes_referencia.year)
    ]
    return df_aberto['valor_saldo'].sum()

def get_valor_total_pago_mes(df_filtered, mes_referencia):
    """Calcula o valor total pago para um determinado mês."""
    df_pago = df_filtered[
        (df_filtered['status_documento'].str.lower() == 'quitado') &
        (df_filtered['data_quitacao'].dt.month == mes_referencia.month) &
        (df_filtered['data_quitacao'].dt.year == mes_referencia.year)
    ]
    return (df_pago['valor_documento'] - df_pago['valor_desconto']).sum()

def get_analise_vencimentos_futuros(df_filtered, data_corte_inicio, data_corte_fim, tipos_documento=None):
    """
    Retorna contas em aberto com vencimento em um período futuro,
    opcionalmente filtrado por tipo de documento.
    """
    df_futuro = df_filtered[
        (df_filtered['status_documento'].str.lower() == 'aberto') &
        (df_filtered['data_vencimento'] >= data_corte_inicio) &
        (df_filtered['data_vencimento'] <= data_corte_fim)
    ].copy()

    if tipos_documento and 'Todos' not in tipos_documento:
        df_futuro = df_futuro[df_futuro['descricao_tipo_documento'].isin(tipos_documento)]

    return df_futuro.sort_values(by='data_vencimento')

def get_analise_pagamentos_por_periodo(df_filtered, inicio, fim):
    """Calcula o valor total pago por mês dentro de um período."""
    df_pagos = df_filtered[
        (df_filtered['status_documento'].str.lower() == 'quitado') &
        (df_filtered['data_quitacao'] >= inicio) &
        (df_filtered['data_quitacao'] <= fim)
    ]
    return df_pagos.groupby(pd.Grouper(key='data_quitacao', freq='ME'))['valor_documento'].sum().reset_index()

def get_mapeamento_picos_vencimentos(df_filtered, periodo_analise_inicio, periodo_analise_fim):
    """Mapeia picos de vencimento de contas em aberto por semana."""
    df_aberto = df_filtered[
        (df_filtered['status_documento'].str.lower() == 'aberto') &
        (df_filtered['data_vencimento'] >= periodo_analise_inicio) &
        (df_filtered['data_vencimento'] <= periodo_analise_fim)
    ]
    return df_aberto.groupby(df_aberto['data_vencimento'].dt.to_period('W'))['valor_saldo'].sum().reset_index(name='valor_total').sort_values(by='data_vencimento')

def get_prazo_medio_por_fornecedor(df_filtered):
    """Calcula o prazo médio de pagamento por fornecedor."""
    df_pago_com_parcelas = df_filtered[df_filtered['status_documento'].str.lower() == 'quitado'].copy()
    df_pago_com_parcelas = df_pago_com_parcelas.dropna(subset=['data_vencimento', 'data_emissao'])
    
    if df_pago_com_parcelas.empty:
        return pd.DataFrame(columns=['fornecedor', 'prazo_medio_dias'])

    df_pago_com_parcelas['prazo_dias'] = (df_pago_com_parcelas['data_vencimento'] - df_pago_com_parcelas['data_emissao']).dt.days
    prazo_medio_nota = df_pago_com_parcelas.groupby(['fornecedor', 'numero_documento_base'])['prazo_dias'].mean().reset_index()
    return prazo_medio_nota.groupby('fornecedor')['prazo_dias'].mean().reset_index(name='prazo_medio_dias').sort_values(by='prazo_medio_dias', ascending=False)

def get_distribuicao_por_tipo_documento(df_filtered):
    """Calcula a distribuição do valor total por tipo de documento."""
    return df_filtered.groupby('descricao_tipo_documento')['valor_documento'].sum().reset_index()

# --- Layout do Streamlit ---
st.title("📊 Análise de Contas a Pagar")

# --- Filtros Globais ---
# --- Filtros Globais no Corpo Principal ---
with st.expander("🔍 Filtros Globais", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        status_opcoes = ['Todos'] + sorted(df['status_documento'].dropna().unique().tolist())
        status_selecionados = st.multiselect(
            "Filtrar Status do Documento:",
            options=status_opcoes,
            default=['aberto']
        )

    with col2:
        tipo_opcoes = ['Todos'] + sorted(df['descricao_tipo_documento'].dropna().unique().tolist())
        tipo_selecionados = st.multiselect(
            "Filtrar Tipo de Documento:",
            options=tipo_opcoes,
            default=['Todos']
        )

# Aplicar filtros ao DataFrame principal
df_filtrado = df.copy()

if 'Todos' not in status_selecionados:
    df_filtrado = df_filtrado[df_filtrado['status_documento'].isin(status_selecionados)]

if 'Todos' not in tipo_selecionados:
    df_filtrado = df_filtrado[df_filtrado['descricao_tipo_documento'].isin(tipo_selecionados)]

# --- Visão Geral do Mês Atual ---
st.subheader("Visão Geral do Mês Atual")
today_dt = pd.to_datetime('today')
mes_atual = today_dt.month
ano_atual = today_dt.year
data_referencia_mes = pd.to_datetime(f'{ano_atual}-{mes_atual}-01')

col1, col2 = st.columns(2)

with col1:
    valor_aberto = get_valor_total_contas_a_pagar_aberto_mes(df_filtrado, data_referencia_mes)
    st.metric(label=f"Valor Total em Aberto ({data_referencia_mes.strftime('%B/%Y')})", value=format_currency_brl(valor_aberto))

with col2:
    valor_pago = get_valor_total_pago_mes(df, data_referencia_mes) # Aplicando df_filtrado
    st.metric(label=f"Valor Total Pago ({data_referencia_mes.strftime('%B/%Y')})", value=format_currency_brl(valor_pago))


## 📅 Vencimentos Futuros (Em Aberto)
st.subheader("Vencimentos Futuros (Em Aberto)")

# Using today_dt defined above to keep consistency with current date
mes_atual_period = today_dt.to_period('M')
proximo_mes_period = (today_dt + pd.DateOffset(months=1)).to_period('M')

mes_selecionado_str = st.radio(
    "Selecione o mês para visualizar:",
    options=[mes_atual_period.strftime('%B/%Y'), proximo_mes_period.strftime('%B/%Y')],
    index=0
)

if mes_selecionado_str == mes_atual_period.strftime('%B/%Y'):
    data_filtro_inicio = mes_atual_period.start_time
    data_filtro_fim = mes_atual_period.end_time
else:
    data_filtro_inicio = proximo_mes_period.start_time
    data_filtro_fim = proximo_mes_period.end_time

# Reutiliza as opções de tipo de documento para este filtro específico
todos_tipos_documento = ['Todos'] + df['descricao_tipo_documento'].unique().tolist()
tipos_documento_selecionados_vencimento = st.multiselect(
    "Selecione o(s) Tipo(s) de Documento para Vencimentos Futuros:",
    options=todos_tipos_documento,
    default='Todos'
)

df_vencimentos_futuros = get_analise_vencimentos_futuros(df_filtrado, data_filtro_inicio, data_filtro_fim, tipos_documento_selecionados_vencimento)

if not df_vencimentos_futuros.empty:
    # 1. Selecione e renomeie as colunas primeiro para o DataFrame de exibição
    df_display_vencimentos = df_vencimentos_futuros[['fornecedor', 'numero_documento', 'data_vencimento', 'valor_saldo', 'descricao_tipo_documento']].rename(columns={
        'fornecedor': 'Fornecedor',
        'numero_documento': 'Número Documento',
        'data_vencimento': 'Data Vencimento', # Aqui a coluna é renomeada
        'valor_saldo': 'Valor a Pagar',
        'descricao_tipo_documento': 'Tipo Documento'
    })
    
    # 2. Em seguida, aplique o estilo e a formatação ao DataFrame de exibição
    st.dataframe(df_display_vencimentos.style.apply(highlight_overdue, axis=1).format({ # highlight_overdue agora procura 'Data Vencimento'
        "Valor a Pagar": format_currency_brl,
        "Data Vencimento": format_date_br
    }))
else:
    st.info(f"Não há contas a vencer em aberto para o(s) tipo(s) de documento selecionado(s) no período de {mes_selecionado_str}.")


## 📈 Evolução de Pagamentos por Período
st.subheader("Evolução de Pagamentos por Período")

col_start, col_end = st.columns(2)
with col_start:
    data_inicio_pagamentos = st.date_input("Início do Período de Análise (Pagamentos)", pd.to_datetime(f'{ano_atual}-01-01'))
with col_end:
    data_fim_pagamentos = st.date_input("Fim do Período de Análise (Pagamentos)", today_dt)

df_pagamentos_periodo = get_analise_pagamentos_por_periodo(df, pd.to_datetime(data_inicio_pagamentos), pd.to_datetime(data_fim_pagamentos))

if not df_pagamentos_periodo.empty:
    df_pagamentos_periodo['data_quitacao'] = df_pagamentos_periodo['data_quitacao'].dt.to_period('M').astype(str)
    df_pagamentos_periodo['valor_documento_formatado'] = df_pagamentos_periodo['valor_documento'].apply(format_currency_brl)

    fig_pagamentos = px.bar(df_pagamentos_periodo,
                            x='data_quitacao',
                            y='valor_documento',
                            title='Valor Total Pago por Mês',
                            labels={'data_quitacao': 'Mês de Quitação', 'valor_documento': 'Valor Pago (R$)'},
                            text='valor_documento_formatado',
                            custom_data=['valor_documento_formatado'])
    
    fig_pagamentos.update_traces(
        textposition='outside',
        hovertemplate='<b>Mês de Quitação:</b> %{x}<br><b>Valor Pago:</b> %{customdata[0]}<extra></extra>' 
    )
    
    fig_pagamentos.update_layout(
        xaxis_title="Mês de Quitação",
        yaxis_title="Valor Pago (R$)",
        uniformtext_minsize=8,
        uniformtext_mode='hide',
        yaxis=dict(
            tickprefix="R$ ",
            separatethousands=True,
            tickformat=".2f"
        )
    )
    st.plotly_chart(fig_pagamentos, use_container_width=True)
else:
    st.info("Não há pagamentos no período selecionado com os filtros aplicados.")


## 📊 Picos de Vencimentos
st.subheader("Picos de Vencimentos")

col_pico_start, col_pico_end = st.columns(2)
with col_pico_start:
    data_inicio_picos = st.date_input("Início do Período de Análise (Picos)", today_dt)
with col_pico_end:
    data_fim_picos = st.date_input("Fim do Período de Análise (Picos)", today_dt + pd.DateOffset(months=3))

df_picos_vencimento = get_mapeamento_picos_vencimentos(df_filtrado, pd.to_datetime(data_inicio_picos), pd.to_datetime(data_fim_picos))

if not df_picos_vencimento.empty:
    df_picos_vencimento['data_vencimento'] = df_picos_vencimento['data_vencimento'].astype(str)
    df_picos_vencimento['valor_total_formatado'] = df_picos_vencimento['valor_total'].apply(format_currency_brl)

    fig_picos = px.bar(df_picos_vencimento,
                       x='data_vencimento',
                       y='valor_total',
                       title='Picos de Vencimento de Contas em Aberto (Por Semana)',
                       labels={'data_vencimento': 'Semana de Vencimento', 'valor_total': 'Valor Total a Pagar (R$)'},
                       text='valor_total_formatado',
                       custom_data=['valor_total_formatado'])
    
    fig_picos.update_traces(
        textposition='outside',
        hovertemplate='<b>Semana de Vencimento:</b> %{x}<br><b>Valor Total a Pagar:</b> %{customdata[0]}<extra></extra>'
    )
    
    fig_picos.update_layout(
        xaxis_title="Semana de Vencimento",
        yaxis_title="Valor Total a Pagar (R$)",
        uniformtext_minsize=8,
        uniformtext_mode='hide',
        yaxis=dict(
            tickprefix="R$ ",
            separatethousands=True,
            tickformat=".2f"
        )
    )
    st.plotly_chart(fig_picos, use_container_width=True)
else:
    st.info("Não há picos de vencimento no período selecionado com os filtros aplicados.")


## ⏰ Prazo Médio por Fornecedor (dias)
st.subheader("Prazo Médio por Fornecedor (dias)")
df_prazo_medio = get_prazo_medio_por_fornecedor(df)

if not df_prazo_medio.empty:
    fig_prazo_medio = px.bar(df_prazo_medio,
                             x='prazo_medio_dias',
                             y='fornecedor',
                             orientation='h',
                             title='Prazo Médio de Vencimento por Fornecedor',
                             labels={'prazo_medio_dias': 'Prazo Médio (Dias)', 'fornecedor': 'Fornecedor'},
                             text='prazo_medio_dias')
    fig_prazo_medio.update_traces(texttemplate='%{x:.1f} dias', textposition='outside')
    fig_prazo_medio.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_prazo_medio, use_container_width=True)
else:
    st.info("Não há dados de prazo médio para exibir com os filtros aplicados.")

## 📄 Distribuição por Tipo de Documento
st.subheader("Distribuição por Tipo de Documento")
df_distribuicao_tipo = get_distribuicao_por_tipo_documento(df_filtrado)

if not df_distribuicao_tipo.empty:
    df_distribuicao_tipo['valor_documento_formatado'] = df_distribuicao_tipo['valor_documento'].apply(format_currency_brl)

    fig_distribuicao = px.pie(df_distribuicao_tipo,
                              values='valor_documento',
                              names='descricao_tipo_documento',
                              title='Distribuição de Contas por Tipo de Documento',
                              hole=.3,
                              custom_data=['valor_documento_formatado'])
    fig_distribuicao.update_traces(
        textinfo='percent+label',
        pull=[0.1 if doc == df_distribuicao_tipo['descricao_tipo_documento'].iloc[0] else 0 for doc in df_distribuicao_tipo['descricao_tipo_documento']],
        hovertemplate='<b>%{label}</b><br>Valor: %{customdata[0]}<br>Percentual: %{percent}<extra></extra>'
    )
    st.plotly_chart(fig_distribuicao, use_container_width=True)
else:
    st.info("Não há dados de distribuição por tipo de documento para exibir com os filtros aplicados.")