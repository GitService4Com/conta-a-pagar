import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import os
from datetime import datetime

st.set_page_config(layout="wide", page_title="Análise de Contas a Pagar")

def formatar_moeda(valor, simbolo_moeda="R$"):
    """
    Formata um valor numérico para o formato de moeda brasileiro (R$ X.XXX,XX).
    Retorna uma string vazia se o valor for NaN ou 'Valor inválido' em caso de erro.
    """
    if pd.isna(valor):
        return ''
    try:
        # Garante que o valor é numérico antes de formatar
        valor = float(valor)
        return f"{simbolo_moeda} {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "Valor inválido"

def format_date_br(data):
    """
    Formata uma data para o padrão brasileiro (DD/MM/AAAA).
    Retorna uma string vazia se a data for NaN.
    """
    if pd.isna(data):
        return ''
    return data.strftime('%d/%m/%Y')

def highlight_overdue(row):
    """
    Função para destacar linhas de contas vencidas em um DataFrame.
    Retorna uma lista de strings de estilo CSS.
    """
    today = pd.to_datetime('today').normalize()
    if 'Data Vencimento' in row.index and pd.notna(row['Data Vencimento']):
        try:
            # Tenta converter para datetime se ainda não for
            dt_venc = row['Data Vencimento']
            if not pd.api.types.is_datetime64_any_dtype(dt_venc):
                 dt_venc = pd.to_datetime(dt_venc, errors='coerce')

            if pd.notna(dt_venc) and dt_venc < today:
                return ['background-color: #f8230f'] * len(row) # Vermelho
        except:
            pass # Ignora erros de conversão de data, não aplica destaque
    return [''] * len(row) # Sem destaque

INPUT_CSV_FILE = 'contas_pagar.csv'

@st.cache_data
def load_data_from_csv():
    """
    Carrega e pré-processa os dados do arquivo CSV.
    Utiliza st.cache_data para otimizar o carregamento.
    """
    if not os.path.exists(INPUT_CSV_FILE):
        st.error(f"Erro: O arquivo '{INPUT_CSV_FILE}' não foi encontrado. Por favor, coloque '{INPUT_CSV_FILE}' na mesma pasta do aplicativo.")
        st.stop()

    df = pd.read_csv(INPUT_CSV_FILE)

    # Conversão de colunas de data
    df['data_emissao'] = pd.to_datetime(df['data_emissao'], errors='coerce')
    df['data_vencimento'] = pd.to_datetime(df['data_vencimento'], errors='coerce')
    df['data_quitacao'] = pd.to_datetime(df['data_quitacao'], errors='coerce')

    # Conversão de colunas numéricas (lidando com vírgulas como separador decimal)
    for col in ['valor_documento', 'valor_desconto', 'valor_saldo']:
        df[col] = df[col].astype(str).str.replace(',', '.')
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Preenchimento de valores ausentes em colunas de texto
    df['fornecedor'] = df['fornecedor'].fillna('Fornecedor Não Informado')
    df['descricao_tipo_documento'] = df['descricao_tipo_documento'].fillna('Não Informado')

    # Criação de colunas auxiliares para análise de período
    df['numero_documento_base'] = df['numero_documento'].apply(lambda x: x.split('/')[0] if isinstance(x, str) and '/' in x else str(x))
    df['MES_ANO_VENCIMENTO'] = df['data_vencimento'].dt.to_period('M')
    df['MES_ANO_QUITACAO'] = df['data_quitacao'].dt.to_period('M')
    return df

# Carrega os dados
df = load_data_from_csv()

def get_valor_total_contas_a_pagar(df_filtered):
    """Calcula o valor total de contas a pagar no DataFrame filtrado."""
    return df_filtered['valor_documento'].sum()

def get_valor_total_contas_a_pagar_aberto(df_filtered):
    """Calcula o valor total de contas em aberto no DataFrame filtrado."""
    df_aberto = df_filtered[df_filtered['status_documento'].str.lower() == 'aberto']
    return df_aberto['valor_saldo'].sum()

st.title("📊 Análise de Contas a Pagar")

# ---
st.markdown("---")
## 🔍 Filtros Globais


with st.expander("🔍 Filtros Globais", expanded=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        # Pega só os períodos do ano atual para o filtro de mês
        ano_atual = datetime.today().year
        periodos_ano_atual = df['MES_ANO_VENCIMENTO'].dropna().unique()
        periodos_ano_atual = [p for p in periodos_ano_atual if p.year == ano_atual]

        # Ordena e converte para string
        all_periods = sorted(list(set(pd.Series(periodos_ano_atual).astype(str))))
        meses_opcoes_global = ['Todos os Meses'] + all_periods
        
        # Define 'Todos os Meses' como padrão (índice 0)
        mes_selecionado_global = st.selectbox("Selecione o Mês de Análise:", options=meses_opcoes_global, index=0)

    with col2:
        status_opcoes = ['Todos'] + sorted(df['status_documento'].dropna().unique().tolist())
        # Define 'Todos' como padrão para status
        status_selecionados = st.multiselect("Filtrar Status do Documento:", options=status_opcoes, default=['Todos'])

    with col3:
        tipo_opcoes = ['Todos'] + sorted(df['descricao_tipo_documento'].dropna().unique().tolist())
        # Define 'Todos' como padrão para tipo de documento
        tipo_selecionados = st.multiselect("Filtrar Tipo de Documento:", options=tipo_opcoes, default=['Todos'])

# Aplicação dos filtros no DataFrame global
df_filtrado_global = df.copy()

if mes_selecionado_global != 'Todos os Meses':
    period_selected = pd.Period(mes_selecionado_global, 'M')
    # Filtra por mês de vencimento OU mês de quitação, para abranger ambos os cenários
    df_filtrado_global = df_filtrado_global[
        (df_filtrado_global['MES_ANO_VENCIMENTO'] == period_selected) |
        (df_filtrado_global['MES_ANO_QUITACAO'] == period_selected)
    ]

if 'Todos' not in status_selecionados:
    df_filtrado_global = df_filtrado_global[df_filtrado_global['status_documento'].isin(status_selecionados)]

if 'Todos' not in tipo_selecionados:
    df_filtrado_global = df_filtrado_global[df_filtrado_global['descricao_tipo_documento'].isin(tipo_selecionados)]

# ---
st.markdown("---")
## Visão Geral do Período Selecionado

st.subheader("Visão Geral do Período Selecionado")
titulo_visao_geral = "Todos os Meses" if mes_selecionado_global == 'Todos os Meses' else mes_selecionado_global

col1_metric, col2_metric = st.columns(2)

with col1_metric:
    valor_total_contas = get_valor_total_contas_a_pagar(df_filtrado_global)
    st.metric(label=f"Valor Total de Contas ({titulo_visao_geral})", value=formatar_moeda(valor_total_contas))

with col2_metric:
    valor_aberto = get_valor_total_contas_a_pagar_aberto(df_filtrado_global)
    st.metric(label=f"Valor Total em Aberto ({titulo_visao_geral})", value=formatar_moeda(valor_aberto))

# ---
st.markdown("---")
## Contas em Aberto (Respeitando Período e Filtros)


st.subheader("Contas em Aberto (Respeitando Período e Filtros)")

df_em_aberto = df_filtrado_global[df_filtrado_global['status_documento'].str.lower() == 'aberto']

if not df_em_aberto.empty:
    df_display_aberto = df_em_aberto[['fornecedor', 'numero_documento', 'data_vencimento', 'valor_saldo', 'descricao_tipo_documento']].rename(columns={
        'fornecedor': 'Fornecedor',
        'numero_documento': 'Número Documento',
        'data_vencimento': 'Data Vencimento',
        'valor_saldo': 'Valor a Pagar',
        'descricao_tipo_documento': 'Tipo Documento'
    })
    # Aplica o destaque para vencidos e formatação de moeda/data
    st.dataframe(df_display_aberto.style.apply(highlight_overdue, axis=1).format({
        "Valor a Pagar": formatar_moeda,
        "Data Vencimento": format_date_br
    }))
else:
    st.info("Não há contas em aberto para o período e filtros selecionados.")

# ---
st.markdown("---")
## 📅 Contas a Pagar por Período

st.subheader("📅 Contas a Pagar por Período")

ano_atual = datetime.today().year

if mes_selecionado_global == 'Todos os Meses':
    # Filtra apenas vencimentos do ano atual para o gráfico mensal
    df_ano_atual = df_filtrado_global[df_filtrado_global['data_vencimento'].dt.year == ano_atual]

    valores_periodo = df_ano_atual.groupby(df_ano_atual['MES_ANO_VENCIMENTO'])['valor_documento'].sum().reset_index()
    valores_periodo['MES_ANO_VENCIMENTO'] = valores_periodo['MES_ANO_VENCIMENTO'].astype(str)
    valores_periodo['valor_documento_formatado'] = valores_periodo['valor_documento'].apply(formatar_moeda)
    title_graph = f"📅 Contas a Pagar por Mês de Vencimento ({ano_atual})"
    x_axis = 'MES_ANO_VENCIMENTO'
else:
    # Filtra por dia se um mês específico for selecionado
    valores_periodo = df_filtrado_global.groupby(df_filtrado_global['data_vencimento'].dt.date)['valor_documento'].sum().reset_index()
    valores_periodo['valor_documento_formatado'] = valores_periodo['valor_documento'].apply(formatar_moeda)
    title_graph = "📅 Contas a Pagar por Dia de Vencimento"
    x_axis = 'data_vencimento'

if not valores_periodo.empty:
    fig_venc = px.bar(
        valores_periodo,
        x=x_axis,
        y='valor_documento',
        title=title_graph,
        text='valor_documento_formatado', # Usa a coluna formatada para o texto da barra
        height=600
    )

    fig_venc.update_traces(
        texttemplate='%{text}',
        textposition='outside',
        textfont=dict(size=14)
    )

    fig_venc.update_layout(
        uniformtext_minsize=8,
        uniformtext_mode='show',
        yaxis=dict(tickprefix="R$ "), # Prefixo de moeda no eixo Y
        xaxis_title='Período',
        yaxis_title='Valor Total (R$)'
    )

    st.plotly_chart(fig_venc, use_container_width=True)
else:
    st.info("Não há dados para exibir no gráfico de contas a pagar para os filtros selecionados.")

# ---
st.markdown("---")
## 📌 Contas Vencidas em Aberto (Atrasadas)

st.subheader("📌 Contas Vencidas em Aberto (Atrasadas)")

# Filtra documentos em aberto e que a data de vencimento é anterior a hoje
df_vencidas_em_aberto = df_filtrado_global[
    (df_filtrado_global['status_documento'].str.lower() == 'aberto') &
    (df_filtrado_global['data_vencimento'] < pd.to_datetime('today').normalize())
]

valor_total_vencido = df_vencidas_em_aberto['valor_saldo'].sum()
quantidade_titulos_vencidos = df_vencidas_em_aberto.shape[0]

# Calcula o valor total em aberto para o percentual
valor_total_em_aberto = df_filtrado_global[
    df_filtrado_global['status_documento'].str.lower() == 'aberto'
]['valor_saldo'].sum()

# Percentual de vencido sobre o total em aberto
percentual_vencido = (valor_total_vencido / valor_total_em_aberto * 100) if valor_total_em_aberto > 0 else 0

# Mostra as métricas em colunas
col1_venc, col2_venc, col3_venc = st.columns(3)

with col1_venc:
    st.metric("💰 Valor Total Vencido (Em Aberto)", formatar_moeda(valor_total_vencido))

with col2_venc:
    st.metric("📄 Qtde de Títulos Vencidos", quantidade_titulos_vencidos)

with col3_venc:
    st.metric("📊 % de Vencidos sobre Aberto", f"{percentual_vencido:.2f} %")

st.markdown("---")

st.subheader("📋 Detalhamento dos Títulos Vencidos em Aberto")

if not df_vencidas_em_aberto.empty:
    df_vencidas_display = df_vencidas_em_aberto[[
        'fornecedor', 'numero_documento', 'data_emissao', 'data_vencimento',
        'valor_documento', 'valor_saldo', 'descricao_tipo_documento'
    ]].rename(columns={
        'fornecedor': 'Fornecedor',
        'numero_documento': 'Número Documento',
        'data_emissao': 'Data Emissão',
        'data_vencimento': 'Data Vencimento',
        'valor_documento': 'Valor Documento',
        'valor_saldo': 'Valor em Aberto',
        'descricao_tipo_documento': 'Tipo Documento'
    })

    # Aplica o destaque e formatação
    st.dataframe(
        df_vencidas_display.style
        .apply(highlight_overdue, axis=1)
        .format({
            "Valor Documento": formatar_moeda,
            "Valor em Aberto": formatar_moeda,
            "Data Emissão": format_date_br,
            "Data Vencimento": format_date_br
        })
    )
else:
    st.info("✅ Não há títulos vencidos em aberto para os filtros selecionados.")

# ---
st.markdown("---")
## 📊 Comparativo Pagamentos x Projeções (Mensal)

st.subheader("📊 Comparativo Pagamentos x Projeções (Mensal)")

# Definir intervalo de análise (ano atual)
ano_analise = datetime.today().year

# Filtrar dados para o ano de análise (considerando vencimento ou quitação no ano)
df_ano = df_filtrado_global[
    (df_filtrado_global['data_vencimento'].dt.year == ano_analise) |
    (df_filtrado_global['data_quitacao'].dt.year == ano_analise)
]

# Dados previstos: contas em aberto agrupadas por mês de vencimento
df_previsto = df_ano[df_ano['status_documento'].str.lower() == 'aberto'].copy()
df_previsto = df_previsto.groupby(df_previsto['MES_ANO_VENCIMENTO'])['valor_saldo'].sum().reset_index()
df_previsto.rename(columns={'MES_ANO_VENCIMENTO': 'Período', 'valor_saldo': 'Previsto'}, inplace=True)
df_previsto['Período'] = df_previsto['Período'].astype(str)
# Adiciona coluna formatada para o hover_data
df_previsto['Previsto_formatado'] = df_previsto['Previsto'].apply(formatar_moeda)


# Dados realizados: contas quitadas agrupadas por mês de quitação
df_realizado = df_ano[df_ano['status_documento'].str.lower() == 'quitado'].copy()
df_realizado = df_realizado.groupby(df_realizado['MES_ANO_QUITACAO'])[['valor_documento', 'valor_desconto']].sum().reset_index()
df_realizado['Realizado'] = df_realizado['valor_documento'] - df_realizado['valor_desconto']
df_realizado = df_realizado[['MES_ANO_QUITACAO', 'Realizado']]
df_realizado.rename(columns={'MES_ANO_QUITACAO': 'Período'}, inplace=True)
df_realizado['Período'] = df_realizado['Período'].astype(str)
# Adiciona coluna formatada para o hover_data
df_realizado['Realizado_formatado'] = df_realizado['Realizado'].apply(formatar_moeda)

# Merge dos dois dataframes pelo período (outer join para manter todos os meses)
df_comparativo = pd.merge(df_previsto, df_realizado, on='Período', how='outer').fillna(0)
df_comparativo = df_comparativo.sort_values(by='Período')

# Garante que as colunas formatadas existam após o merge (caso algum lado não tenha dados para um período)
# Aplica formatar_moeda novamente para os NaNs preenchidos por fillna(0)
df_comparativo['Previsto_formatado'] = df_comparativo['Previsto'].apply(formatar_moeda)
df_comparativo['Realizado_formatado'] = df_comparativo['Realizado'].apply(formatar_moeda)


# Criar o DataFrame no formato "long" **incluindo as colunas formatadas** nos id_vars
df_melted_for_chart = df_comparativo.melt(
    id_vars=['Período', 'Previsto_formatado', 'Realizado_formatado'], # Essas colunas serão replicadas
    value_vars=['Previsto', 'Realizado'],
    var_name='Situação', # Renomeia a coluna 'variable' para 'Situação'
    value_name='Valor' # Renomeia a coluna 'value' para 'Valor'
)

# Adiciona uma coluna para o texto formatado das barras
df_melted_for_chart['Texto_Barra'] = df_melted_for_chart['Valor'].apply(formatar_moeda)

# Plot do gráfico de barras duplas
fig_comp = px.bar(
    df_melted_for_chart,
    x='Período',
    y='Valor',
    color='Situação', # Usa 'Situação' para as cores das barras
    barmode='group',
    labels={'Valor': 'Valor (R$)', 'Período': 'Mês', 'Situação': 'Situação'},
    title='Comparativo Mensal: Pagamentos Previsto x Realizado',
    text='Texto_Barra', # Usa a coluna formatada para o texto da barra
    hover_data={
        'Período': True, # Exibir o período no hover
        'Valor': False, # Não exibir o valor bruto no hover, usaremos os formatados
        'Situação': True, # Exibir a situação no hover
        'Previsto_formatado': True, # Exibir o previsto formatado
        'Realizado_formatado': True # Exibir o realizado formatado
    }
)

fig_comp.update_layout(
    yaxis=dict(tickprefix="R$ "), # Prefixo de moeda no eixo Y
    uniformtext_minsize=8,
    uniformtext_mode='show'
)

fig_comp.update_traces(textposition='outside') # Ajusta a posição do texto nas barras
st.plotly_chart(fig_comp, use_container_width=True)

# ---
st.markdown("---")
## 📅 Distribuição de Contas a Pagar por Prazo de Vencimento

st.subheader("📅 Distribuição de Contas a Pagar por Prazo de Vencimento")

hoje = pd.to_datetime('today').normalize()

# Filtrar apenas contas em aberto e com data de vencimento válida no futuro (ou hoje)
df_aberto_prazo = df_filtrado_global[
    (df_filtrado_global['status_documento'].str.lower() == 'aberto') &
    (df_filtrado_global['data_vencimento'].notna())
].copy()

# Calcula os dias restantes para o vencimento
df_aberto_prazo['dias_para_vencimento'] = (df_aberto_prazo['data_vencimento'] - hoje).dt.days

# Categoriza nas faixas de vencimento
def categorizar_prazo(dias):
    if dias <= 0: # Contas já vencidas ou vencendo hoje
        return 'Vencidas/Hoje'
    elif dias <= 7:
        return 'Até 7 dias'
    elif 8 <= dias <= 15:
        return '8 a 15 dias'
    elif 16 <= dias <= 30:
        return '16 a 30 dias'
    else: # dias > 30
        return 'Mais de 30 dias'

df_aberto_prazo['faixa_vencimento'] = df_aberto_prazo['dias_para_vencimento'].apply(categorizar_prazo)

# Agrupa valores por faixa de vencimento
df_prazo = df_aberto_prazo.groupby('faixa_vencimento')['valor_saldo'].sum().reset_index()

# Ordenar faixas para exibição correta no gráfico (incluindo "Vencidas/Hoje")
ordem_faixas = ['Vencidas/Hoje', 'Até 7 dias', '8 a 15 dias', '16 a 30 dias', 'Mais de 30 dias']
df_prazo['faixa_vencimento'] = pd.Categorical(df_prazo['faixa_vencimento'], categories=ordem_faixas, ordered=True)
df_prazo = df_prazo.sort_values('faixa_vencimento')

# Formatando valores para exibição no gráfico
df_prazo['valor_formatado'] = df_prazo['valor_saldo'].apply(formatar_moeda)

# Seletor para escolher tipo de gráfico (Barras ou Pizza)
tipo_grafico = st.radio("Tipo de gráfico:", options=['Barras', 'Pizza'], index=0)

if not df_prazo.empty:
    if tipo_grafico == 'Barras':
        fig_prazo = px.bar(
            df_prazo,
            x='faixa_vencimento',
            y='valor_saldo',
            text='valor_formatado', # Usa a coluna formatada para o texto da barra
            title='Distribuição de Contas a Pagar por Prazo de Vencimento',
            labels={'faixa_vencimento': 'Faixa de Vencimento', 'valor_saldo': 'Valor em Aberto (R$)'}
        )
        fig_prazo.update_traces(textposition='outside')
        fig_prazo.update_layout(yaxis=dict(tickprefix="R$ "), uniformtext_minsize=8, uniformtext_mode='show')
        st.plotly_chart(fig_prazo, use_container_width=True)

    else:  # Gráfico de Pizza
        fig_prazo = px.pie(
            df_prazo,
            names='faixa_vencimento',
            values='valor_saldo',
            title='Distribuição de Contas a Pagar por Prazo de Vencimento',
            hole=0.3, # Cria um gráfico de rosca
            custom_data=['valor_formatado'] # Passa a coluna formatada para o tooltip
        )
        fig_prazo.update_traces(
            textinfo='percent+label', # Exibe porcentagem e label no gráfico
            # Ajusta o hovertemplate para usar a coluna formatada do custom_data
            hovertemplate='<b>%{label}</b><br>Valor: %{customdata[0]}<extra></extra>'
        )
        st.plotly_chart(fig_prazo, use_container_width=True)
else:
    st.info("Não há contas em aberto para análise de prazo de vencimento com os filtros aplicados.")