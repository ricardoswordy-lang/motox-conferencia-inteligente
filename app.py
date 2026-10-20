import io
import re
import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="MotoX | Conferência Inteligente",
    page_icon="🛵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Visual ----------
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1400px;}
.hero {padding: 1.35rem 1.5rem; border-radius: 18px; background: linear-gradient(115deg,#102b46,#176b68); color: white; margin-bottom: 1.1rem;}
.hero h1 {color: white; font-size: 2rem; margin: 0 0 .35rem 0;}
.hero p {color: #e4f5f2; margin: 0; font-size: 1rem;}
.small-note {color: #64748b; font-size: .9rem;}
div[data-testid="stMetric"] {background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,.18); padding: 14px 16px; border-radius: 14px;}
div[data-testid="stMetricLabel"] {font-size: .9rem;}
div[data-testid="stMetricValue"] {font-size: 1.65rem;}
section[data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.15);}
</style>
""", unsafe_allow_html=True)

def norm(v):
    if pd.isna(v):
        return ""
    s = unicodedata.normalize("NFKD", str(v).strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def money(v):
    if pd.isna(v) or str(v).strip() == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9.-]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None

def brl(v):
    if v is None or pd.isna(v):
        return "—"
    return ("R$ {:,.2f}".format(float(v))).replace(",", "X").replace(".", ",").replace("X", ".")

def read_sheets(file):
    excel = pd.ExcelFile(file)
    result = {}
    for sheet in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if not df.empty:
            result[sheet] = df
    return result

def guess_col(cols, terms):
    ranked = []
    for col in cols:
        normalized = norm(col)
        score = sum(3 if normalized == norm(term) else 1 for term in terms if norm(term) in normalized)
        if score:
            ranked.append((score, col))
    return sorted(ranked, key=lambda item: item[0], reverse=True)[0][1] if ranked else cols[0]

def prep(df, name_col, amount_col):
    out = pd.DataFrame({
        "Nome original": df[name_col].astype("string").fillna("").str.strip(),
        "Nome normalizado": df[name_col].map(norm),
        "Valor": df[amount_col].map(money),
    })
    return out[out["Nome normalizado"] != ""].copy()

def run_comparison(aux_df, main_df, aux_name_col, aux_value_col, main_name_col, main_value_col, tolerance):
    aux = prep(aux_df, aux_name_col, aux_value_col)
    main = prep(main_df, main_name_col, main_value_col)

    a = aux.groupby("Nome normalizado", as_index=False).agg(
        Nome_auxiliar=("Nome original", "first"),
        Linhas_auxiliares=("Nome original", "size"),
        Valor_auxiliar=("Valor", lambda s: s.sum(min_count=1)),
    )
    m = main.groupby("Nome normalizado", as_index=False).agg(
        Nome_MotoX=("Nome original", "first"),
        Linhas_MotoX=("Nome original", "size"),
        Valor_MotoX=("Valor", lambda s: s.sum(min_count=1)),
    )
    result = a.merge(m, on="Nome normalizado", how="outer", indicator=True)
    result["Diferença"] = result["Valor_MotoX"] - result["Valor_auxiliar"]
    # Convert to regular string dtype so assigning additional labels works even
    # when pandas infers categorical values from the merge indicator.
    result["Status"] = result["_merge"].map({
        "both": "Valores conferem",
        "left_only": "Não encontrado na MotoX",
        "right_only": "Somente na MotoX",
    }).astype("object")
    both = result["_merge"].eq("both")
    valid = both & result["Valor_auxiliar"].notna() & result["Valor_MotoX"].notna()
    result.loc[valid & (result["Diferença"].abs() > tolerance), "Status"] = "DIVERGÊNCIA DE VALOR"
    result.loc[both & (~result["Valor_auxiliar"].notna() | ~result["Valor_MotoX"].notna()), "Status"] = "Valor ausente / não reconhecido"

    duplicates = aux[aux["Nome normalizado"].duplicated(keep=False)].sort_values("Nome normalizado")
    if duplicates.empty:
        dup_report = pd.DataFrame(columns=["Nome normalizado", "Nome identificado", "Quantidade de linhas", "Valores encontrados"])
    else:
        dup_report = duplicates.groupby("Nome normalizado", as_index=False).agg(
            **{
                "Nome identificado": ("Nome original", lambda s: " | ".join(pd.unique(s.astype(str)))),
                "Quantidade de linhas": ("Nome original", "size"),
                "Valores encontrados": ("Valor", lambda s: " | ".join(brl(v) for v in s)),
            }
        )

    result["Valor auxiliar (R$)"] = result["Valor_auxiliar"].map(brl)
    result["Valor MotoX (R$)"] = result["Valor_MotoX"].map(brl)
    result["Diferença (R$)"] = result["Diferença"].map(brl)
    return aux, main, result, dup_report

def make_report(aux, main, result, duplicates, aux_filename, main_filename):
    display = result[[
        "Nome_auxiliar", "Nome_MotoX", "Valor auxiliar (R$)", "Valor MotoX (R$)",
        "Diferença (R$)", "Linhas_auxiliares", "Linhas_MotoX", "Status"
    ]].rename(columns={
        "Nome_auxiliar": "Nome na planilha auxiliar",
        "Nome_MotoX": "Nome na MotoX",
        "Linhas_auxiliares": "Linhas auxiliares",
        "Linhas_MotoX": "Linhas MotoX",
    })
    attention = display[display["Status"] != "Valores conferem"]
    aux_total = aux["Valor"].sum(min_count=1)
    main_total = main["Valor"].sum(min_count=1)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        display.to_excel(writer, index=False, sheet_name="Comparacao")
        duplicates.to_excel(writer, index=False, sheet_name="Nomes_Duplicados")
        attention.to_excel(writer, index=False, sheet_name="Pendencias")
        pd.DataFrame({
            "Indicador": [
                "Arquivo de auxiliares", "Arquivo MotoX", "Total coluna auxiliar",
                "Total coluna MotoX selecionada", "Diferença entre totais brutos",
                "Nomes correspondentes", "Valores conferem", "Divergências de valor",
                "Nomes não encontrados na MotoX", "Nomes somente na MotoX",
                "Nomes duplicados na planilha auxiliar", "Gerado em",
            ],
            "Resultado": [
                aux_filename, main_filename, aux_total, main_total,
                (main_total or 0) - (aux_total or 0),
                int(result["_merge"].eq("both").sum()),
                int((result["Status"] == "Valores conferem").sum()),
                int((result["Status"] == "DIVERGÊNCIA DE VALOR").sum()),
                int((result["Status"] == "Não encontrado na MotoX").sum()),
                int((result["Status"] == "Somente na MotoX").sum()),
                int(duplicates["Nome normalizado"].nunique()) if len(duplicates) else 0,
                datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            ],
        }).to_excel(writer, index=False, sheet_name="Resumo")
    return buf.getvalue(), display, attention

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🛵 MotoX")
    st.caption("Central de conferência financeira")
    page = st.radio("Navegação", ["Visão geral", "Conferir planilhas", "Como usar"], index=0)
    st.divider()
    st.markdown("**Fluxo de trabalho**")
    st.markdown("1. Anexe os arquivos\n2. Confirme as colunas\n3. Analise divergências\n4. Baixe o relatório")
    st.divider()
    st.caption("Versão online preparada para implantação. Os arquivos são processados durante a sessão do aplicativo.")

st.markdown("""
<div class="hero">
  <h1>Conferência Inteligente de Planilhas</h1>
  <p>Compare pagamentos, encontre diferenças e identifique nomes duplicados em poucos cliques.</p>
</div>
""", unsafe_allow_html=True)

if page == "Visão geral":
    st.subheader("Seu painel de controle")
    st.write("Use o menu lateral para iniciar uma conferência. O robô compara os nomes e valores escolhidos e prepara um relatório Excel.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Conferência de valores", "Automática", help="Compara os valores das colunas selecionadas.")
    c2.metric("Duplicidades", "Detectadas", help="Sinaliza nomes repetidos na planilha de auxiliares.")
    c3.metric("Relatório final", "Excel", help="Gera abas de comparação, resumo e pendências.")
    st.markdown("### O que você vai receber")
    a, b, c = st.columns(3)
    with a:
        st.markdown("#### 💰 Valores")
        st.write("Valores iguais, diferenças em reais e totais das colunas.")
    with b:
        st.markdown("#### 👥 Entregadores")
        st.write("Nomes que correspondem, não encontrados ou repetidos.")
    with c:
        st.markdown("#### 📊 Relatório")
        st.write("Arquivo Excel para arquivar ou encaminhar à equipe.")
    st.info("Para começar, clique em **Conferir planilhas** no menu à esquerda.")

elif page == "Como usar":
    st.subheader("Como usar o robô")
    st.markdown("""
    1. Abra **Conferir planilhas** no menu lateral.
    2. Anexe a planilha dos motoristas auxiliares e a planilha principal da MotoX.
    3. Selecione a aba correta de cada arquivo.
    4. Confira se as colunas selecionadas correspondem ao nome e ao valor que deseja comparar.
    5. Clique em **Executar conferência**.
    6. Revise o painel e baixe o relatório Excel.

    **Importante:** compare colunas equivalentes. Por exemplo, use “Valor a pagar” na planilha de auxiliares e a coluna de comissão correspondente na planilha MotoX.

    O robô normaliza nomes ignorando diferenças de maiúsculas, acentos e espaços. Quando o mesmo nome aparece mais de uma vez, ele agrega os valores desse nome para a comparação e também sinaliza as duplicidades na planilha de auxiliares.

    O aplicativo não faz pagamentos nem altera os arquivos originais.
    """)

else:
    st.subheader("1. Anexe os arquivos")
    up1, up2 = st.columns(2)
    with up1:
        aux_file = st.file_uploader("Planilha dos motoristas auxiliares", type=["xlsx", "xls"], key="aux_upload")
    with up2:
        main_file = st.file_uploader("Planilha principal MotoX / Rio Grande do Sul", type=["xlsx", "xls"], key="main_upload")

    if aux_file and main_file:
        try:
            aux_sheets = read_sheets(aux_file)
            main_sheets = read_sheets(main_file)
            if not aux_sheets or not main_sheets:
                st.error("Não encontrei abas com dados nos dois arquivos.")
                st.stop()

            st.subheader("2. Confirme as abas e colunas")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### 📄 Motoristas auxiliares")
                aux_sheet = st.selectbox("Aba dos auxiliares", list(aux_sheets), key="aux_sheet")
                aux_df = aux_sheets[aux_sheet]
                aux_name_col = st.selectbox("Coluna com nome", list(aux_df.columns),
                    index=list(aux_df.columns).index(guess_col(list(aux_df.columns), ["Entregador", "Motorista", "Nome", "Auxiliar"])), key="aux_name")
                aux_value_col = st.selectbox("Coluna com valor a pagar", list(aux_df.columns),
                    index=list(aux_df.columns).index(guess_col(list(aux_df.columns), ["Valor a pagar", "A pagar", "Total a pagar", "Valor", "Total"])), key="aux_value")
                st.caption(f"{len(aux_df):,} linhas encontradas".replace(",", "."))
            with col2:
                st.markdown("##### 🛵 Planilha MotoX")
                main_sheet = st.selectbox("Aba da MotoX", list(main_sheets), key="main_sheet")
                main_df = main_sheets[main_sheet]
                main_name_col = st.selectbox("Coluna com nome do entregador", list(main_df.columns),
                    index=list(main_df.columns).index(guess_col(list(main_df.columns), ["Entregador auxiliar", "Entregador", "Motorista", "Nome"])), key="main_name")
                main_value_col = st.selectbox("Coluna com valor equivalente", list(main_df.columns),
                    index=list(main_df.columns).index(guess_col(list(main_df.columns), ["Total de comissões", "Comissões", "Valor a pagar", "Total", "Valor"])), key="main_value")
                st.caption(f"{len(main_df):,} linhas encontradas".replace(",", "."))
            tolerance = st.number_input("Tolerância para arredondamento (R$)", min_value=0.0, max_value=1.0, value=0.01, step=0.01)
            if st.button("🔎 Executar conferência", type="primary", use_container_width=True):
                aux, main, result, duplicates = run_comparison(
                    aux_df, main_df, aux_name_col, aux_value_col, main_name_col, main_value_col, tolerance
                )
                report_bytes, display, attention = make_report(
                    aux, main, result, duplicates, aux_file.name, main_file.name
                )
                st.session_state["online_report"] = {
                    "aux": aux, "main": main, "result": result, "duplicates": duplicates,
                    "bytes": report_bytes, "display": display, "attention": attention,
                    "aux_name": aux_file.name, "main_name": main_file.name,
                }
        except Exception as exc:
            st.error(f"Não consegui processar os arquivos: {exc}")
            st.info("Confirme se os arquivos são Excel válidos e se a primeira linha das abas contém os títulos das colunas.")

    if "online_report" in st.session_state:
        r = st.session_state["online_report"]
        result = r["result"]
        duplicates = r["duplicates"]
        aux = r["aux"]
        main = r["main"]
        st.divider()
        st.subheader("3. Resultado da conferência")
        matched = int(result["_merge"].eq("both").sum())
        exact = int((result["Status"] == "Valores conferem").sum())
        divergences = int((result["Status"] == "DIVERGÊNCIA DE VALOR").sum())
        missing = int((result["Status"] == "Não encontrado na MotoX").sum())
        only_main = int((result["Status"] == "Somente na MotoX").sum())
        dup_count = int(duplicates["Nome normalizado"].nunique()) if len(duplicates) else 0

        metrics = st.columns(4)
        metrics[0].metric("Nomes correspondentes", matched)
        metrics[1].metric("Valores conferem", exact)
        metrics[2].metric("Divergências", divergences, delta=None if divergences == 0 else "Revisar", delta_color="inverse")
        metrics[3].metric("Nomes duplicados", dup_count, delta=None if dup_count == 0 else "Revisar", delta_color="inverse")

        total_aux = aux["Valor"].sum(min_count=1)
        total_main = main["Valor"].sum(min_count=1)
        totals = st.columns(3)
        totals[0].metric("Total auxiliar", brl(total_aux))
        totals[1].metric("Total da coluna MotoX", brl(total_main))
        totals[2].metric("Diferença entre totais brutos", brl((total_main or 0) - (total_aux or 0)))

        if divergences or missing or only_main or dup_count:
            st.warning("A conferência terminou, mas existem itens que merecem revisão. Consulte as abas abaixo.")
        else:
            st.success("Conferência concluída: não foram encontradas divergências de valor acima da tolerância.")

        tab1, tab2, tab3 = st.tabs(["📊 Comparação", "⚠️ Pendências", "👥 Nomes duplicados"])
        with tab1:
            st.dataframe(r["display"], use_container_width=True, hide_index=True)
        with tab2:
            if r["attention"].empty:
                st.success("Nenhuma pendência encontrada.")
            else:
                st.dataframe(r["attention"], use_container_width=True, hide_index=True)
        with tab3:
            if duplicates.empty:
                st.success("Nenhum nome duplicado encontrado na coluna selecionada.")
            else:
                st.dataframe(duplicates, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Baixar relatório completo em Excel",
            data=r["bytes"],
            file_name=f"relatorio_conferencia_motox_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    else:
        st.caption("Os resultados aparecerão aqui depois de executar a conferência.")
