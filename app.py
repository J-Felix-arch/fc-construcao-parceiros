"""
App para parceiros — lê do Supabase via REST API (dados atualizados 3x/dia: 07h, 12h e 15h)
"""
import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="FC Construção — Parceiros", page_icon="📦", layout="wide")

# ── Supabase REST API ─────────────────────────────────────────────────────────
SUPA_URL    = st.secrets["supabase"]["url"]
SUPA_SECRET = st.secrets["supabase"]["secret"]
HEADERS = {
    "apikey":        SUPA_SECRET,
    "Authorization": f"Bearer {SUPA_SECRET}",
    "Content-Type":  "application/json",
}

def supa_get(tabela: str, params: dict = None) -> list:
    r = requests.get(f"{SUPA_URL}/{tabela}", headers=HEADERS, params=params)
    if r.status_code == 200:
        return r.json()
    return []

# ── Estilo ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;800;900&display=swap');
  * { font-family:'Nunito',sans-serif !important; }
  [data-testid="stAppViewContainer"] { background:#F5F5F5; }
  [data-testid="stSidebar"] { background:#FFFFFF; border-right:3px solid #CC0000; color:#1A1A1A !important; }
  [data-testid="stSidebar"] * { color:#1A1A1A !important; }
  [data-testid="stSidebar"] label { color:#1A1A1A !important; }
  [data-testid="stSidebar"] p { color:#1A1A1A !important; }
  [data-testid="stSidebar"] h2 { color:#1A1A1A !important; }
  [data-testid="stSidebar"] small { color:#555555 !important; }
  [data-testid="stAppViewContainer"] { background:#F5F5F5; color:#1A1A1A !important; }
  [data-testid="stAppViewContainer"] * { color:#1A1A1A !important; }
  .stMultiSelect label, .stDateInput label { color:#1A1A1A !important; }
  .kpi-card { background:#fff; border-radius:8px; padding:20px 16px 14px; box-shadow:0 2px 8px rgba(0,0,0,.08); text-align:center; border-top:4px solid #E0E0E0; }
  .kpi-card.blue   { border-top-color:#CC0000; }
  .kpi-card.red    { border-top-color:#CC0000; }
  .kpi-card.green  { border-top-color:#28A745; }
  .kpi-card.orange { border-top-color:#FF6600; }
  .kpi-lbl { font-size:11px; color:#666666; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }
  .kpi-num { font-size:28px; font-weight:900; color:#1A1A1A; line-height:1.1; }
  .kpi-sub { font-size:12px; color:#999999; margin-top:5px; }
  .section-header { background:#CC0000; border-radius:6px; padding:12px 20px; margin:24px 0 16px; }
  .section-header span { font-size:15px; font-weight:700; color:#FFFFFF; }
  div[data-testid="metric-container"] { display:none; }
</style>
""", unsafe_allow_html=True)

HOJE = date.today()

def proximo_dia_util(d):
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5: nd += timedelta(days=1)
    return nd

PROXIMO = proximo_dia_util(HOJE)
DIA2 = proximo_dia_util(proximo_dia_util(proximo_dia_util(HOJE)))

FILIAIS = {
    1:"1 — Garanhuns", 2:"2 — Imbiribeira", 3:"3 — Paralela",
    4:"4 — Tamarineira", 5:"5 — Aracaju", 6:"6 — João Pessoa",
    7:"7 — Ponta Negra", 8:"8 — Caruaru", 9:"9 — Barris",
    11:"11 — Fortaleza", 80:"80 — MDC", 81:"81 — OBC",
    82:"82 — OL Sal", 91:"91 — Constr. Cabo", 92:"92 — CD Cabo",
    93:"93 — Alhandra", 94:"94 — CD Lauro",
}

# ── Carregar dados ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def carregar_pendentes(dt_ini: str, dt_fim: str) -> pd.DataFrame:
    rows = supa_get("pendentes", {
        "prazo": f"gte.{dt_ini}",
        "and": f"(prazo.lte.{dt_fim})",
        "select": "filial,pedido,dt_fat,prazo,peso_kg,dias_atraso,status_dia,transportadora,status_pedido,status_coleta",
        "limit": 10000,
    })
    # A REST API do Supabase não suporta "and" como parâmetro diretamente; usar dois filtros separados
    rows = supa_get("pendentes", {
        "prazo": f"gte.{dt_ini}",
        "select": "filial,pedido,dt_fat,prazo,peso_kg,dias_atraso,status_dia,transportadora,status_pedido,status_coleta",
        "limit": 10000,
    })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # filtrar prazo <= dt_fim no lado Python
    df["prazo"] = pd.to_datetime(df["prazo"])
    df = df[df["prazo"] <= pd.Timestamp(dt_fim)]
    df["PESO_TON"] = df["peso_kg"] / 1000
    df.columns = [c.upper() for c in df.columns]
    df["PESO_TON"] = df["PESO_KG"] / 1000
    return df

@st.cache_data(ttl=600, show_spinner=False)
def ultima_atualizacao() -> str:
    try:
        rows = supa_get("sync_log", {
            "status": "eq.OK",
            "order": "executado_em.desc",
            "limit": 1,
            "select": "executado_em",
        })
        if rows:
            from datetime import datetime
            dt = datetime.fromisoformat(rows[0]["executado_em"].replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
    except:
        pass
    return "—"

def kpi(col, lbl, val, sub="", cls=""):
    col.markdown(f'<div class="kpi-card {cls}"><div class="kpi-lbl">{lbl}</div>'
                 f'<div class="kpi-num">{val}</div><div class="kpi-sub">{sub}</div></div>',
                 unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 FC Construção")
    st.markdown(f"**Parceiros** — somente leitura")
    st.markdown("---")
    st.markdown("### 📅 Período")
    dt_ini = st.date_input("De",  value=HOJE - timedelta(days=5), format="DD/MM/YYYY")
    dt_fim = st.date_input("Até", value=DIA2, format="DD/MM/YYYY")
    st.markdown("---")
    upd = ultima_atualizacao()
    st.markdown(f"🕐 **Última atualização:**\n\n{upd}")
    st.caption("Dados atualizados às 07h, 12h e 15h")
    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# ── Carregar ────────────────────────────────────────────────────────────────────
with st.spinner("Carregando..."):
    df_pend = carregar_pendentes(str(dt_ini), str(dt_fim))

if df_pend.empty:
    st.info("Sem dados no período selecionado."); st.stop()

# ── Cabeçalho ──────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:12px;font-weight:900;color:#CC0000;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px">Ferreira Costa</div>'
    '<div style="font-size:26px;font-weight:900;color:#1A1A1A">📦 Monitoramento FC Construção</div>'
    f'<div style="font-size:13px;color:#666">Parceiros · Período: {dt_ini.strftime("%d/%m")} → {dt_fim.strftime("%d/%m/%Y")}</div>',
    unsafe_allow_html=True)
st.markdown("---")

# ── Filtros ────────────────────────────────────────────────────────────────────
f1, f2 = st.columns([3, 3])
filiais_disp = sorted(df_pend["FILIAL"].unique().tolist())
with f1:
    fil_sel = st.multiselect("🏭 Filiais", filiais_disp, default=filiais_disp,
                              format_func=lambda x: FILIAIS.get(int(x), str(x)))

fil_int = [int(f) for f in fil_sel] if fil_sel else filiais_disp
dp = df_pend[df_pend["FILIAL"].isin(fil_int)].copy()

if not dp.empty:
    dp["PRAZO_DT"] = pd.to_datetime(dp["PRAZO"])
    dp["DT_S"] = dp["PRAZO_DT"].dt.strftime("%d/%m")

st.markdown("---")

# ── KPIs ────────────────────────────────────────────────────────────────────────
at_ton = float(dp[dp["STATUS_DIA"]=="Atrasado"    ]["PESO_TON"].sum()) if not dp.empty else 0
hj_ton = float(dp[dp["STATUS_DIA"]=="Vence Hoje"  ]["PESO_TON"].sum()) if not dp.empty else 0
pr_ton = float(dp[dp["STATUS_DIA"]=="Proximos Dias"]["PESO_TON"].sum()) if not dp.empty else 0
tot_p  = int(dp["PEDIDO"].nunique()) if not dp.empty else 0
planej = at_ton + hj_ton + pr_ton

k = st.columns(5)
kpi(k[0], "📋 Pendentes",   f"{tot_p:,}".replace(",","."), f"{dt_ini.strftime('%d/%m')}→{dt_fim.strftime('%d/%m')}")
kpi(k[1], "🔴 Atrasados",   f"{at_ton:.1f}t", f"{int(dp[dp['STATUS_DIA']=='Atrasado']['PEDIDO'].nunique() if not dp.empty else 0)} pedidos", "red")
kpi(k[2], "🟡 Vence Hoje",  f"{hj_ton:.1f}t", f"{int(dp[dp['STATUS_DIA']=='Vence Hoje']['PEDIDO'].nunique() if not dp.empty else 0)} pedidos", "orange")
kpi(k[3], "🟢 Próximos",    f"{pr_ton:.1f}t", f"{int(dp[dp['STATUS_DIA']=='Proximos Dias']['PEDIDO'].nunique() if not dp.empty else 0)} pedidos", "green")
kpi(k[4], f"🎯 Total período", f"{planej:.1f}t", f"{tot_p} pedidos", "blue")

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráfico por data ────────────────────────────────────────────────────────────
if not dp.empty:
    st.markdown('<div class="section-header"><span>📊 Pendentes por Data de Prazo</span></div>',
                unsafe_allow_html=True)
    datas_ord = sorted(dp["PRAZO_DT"].dt.date.unique())
    datas_s   = [d.strftime("%d/%m") for d in datas_ord]
    agg = dp.groupby(["DT_S","STATUS_DIA"]).agg(TON=("PESO_TON","sum"), QTD=("PEDIDO","nunique")).reset_index()

    fig = go.Figure()
    for status, cor in [("Atrasado","#D93025"),("Vence Hoje","#F29900"),("Proximos Dias","#1E8E3E")]:
        lbl_map = {"Atrasado":"Atrasado","Vence Hoje":"Vence Hoje","Proximos Dias":"Próximos Dias"}
        sub = agg[agg["STATUS_DIA"]==status].set_index("DT_S")
        y, txt = [], []
        for d in datas_s:
            if d in sub.index:
                t = float(sub.loc[d,"TON"]); y.append(round(t,1)); txt.append(f"{t:.1f}t")
            else:
                y.append(0); txt.append("")
        fig.add_bar(name=lbl_map[status], x=datas_s, y=y, text=txt,
                    textposition="outside", marker_color=cor,
                    textfont=dict(color=cor, size=12, weight=700))

    for d_m, lbl, cor_m in [(HOJE.strftime("%d/%m"),"HOJE","#202124"),(PROXIMO.strftime("%d/%m"),"PRÓX.","#1A73E8")]:
        if d_m in datas_s:
            idx = datas_s.index(d_m)
            fig.add_shape(type="line", xref="x", yref="paper",
                          x0=idx-.5, x1=idx-.5, y0=0, y1=1,
                          line=dict(color=cor_m, width=2, dash="dot"))
            fig.add_annotation(x=idx-.5, y=1.08, xref="x", yref="paper",
                                text=f"▶ {lbl} ({d_m})", showarrow=False,
                                font=dict(color=cor_m, size=10), bgcolor="white",
                                bordercolor=cor_m, borderwidth=1, xanchor="center")

    fig.update_layout(
        barmode="stack", plot_bgcolor="white", paper_bgcolor="#F5F6FA",
        legend=dict(orientation="h", y=1.10, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#E8EAED", title="Toneladas"),
        height=440, margin=dict(t=80, b=40, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Por Transportadora ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header"><span>🚚 Pendentes por Transportadora</span></div>',
                unsafe_allow_html=True)
    agg_t = dp.groupby(["TRANSPORTADORA","STATUS_DIA"]).agg(TON=("PESO_TON","sum")).reset_index()
    t_ord = agg_t.groupby("TRANSPORTADORA")["TON"].sum().sort_values(ascending=True).index.tolist()
    fig2 = go.Figure()
    for status, cor in [("Atrasado","#D93025"),("Vence Hoje","#F29900"),("Proximos Dias","#1E8E3E")]:
        lbl_map2 = {"Atrasado":"Atrasado","Vence Hoje":"Vence Hoje","Proximos Dias":"Próximos Dias"}
        sub = agg_t[agg_t["STATUS_DIA"]==status].set_index("TRANSPORTADORA")
        xv = [float(sub.loc[t,"TON"]) if t in sub.index else 0 for t in t_ord]
        fig2.add_bar(name=lbl_map2[status], y=t_ord, x=xv, orientation="h",
                     text=[f"{v:.1f}t" if v>=.5 else "" for v in xv],
                     textposition="outside", marker_color=cor,
                     textfont=dict(color=cor, size=11, weight=700))
    fig2.update_layout(
        barmode="stack", plot_bgcolor="white", paper_bgcolor="#F5F6FA",
        legend=dict(orientation="h", y=1.05, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=True, gridcolor="#E8EAED", title="Toneladas"),
        yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        height=max(300, len(t_ord)*32+80), margin=dict(t=60, b=20, l=10, r=10),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Tabela ─────────────────────────────────────────────────────────────────
    with st.expander("📋 Ver pedidos pendentes"):
        df_tab = dp.copy()
        df_tab["FILIAL_NOME"] = df_tab["FILIAL"].map(lambda x: FILIAIS.get(int(x),str(x)))
        df_tab["DT_FAT"] = pd.to_datetime(df_tab["DT_FAT"]).dt.strftime("%d/%m/%Y")
        df_tab["PRAZO"]  = pd.to_datetime(df_tab["PRAZO"]).dt.strftime("%d/%m/%Y")
        cols = ["FILIAL_NOME","PEDIDO","TRANSPORTADORA","STATUS_PEDIDO","STATUS_COLETA",
                "DT_FAT","PRAZO","PESO_KG","DIAS_ATRASO","STATUS_DIA"]
        rename = {"FILIAL_NOME":"Filial","PEDIDO":"Pedido","TRANSPORTADORA":"Transportadora",
                  "STATUS_PEDIDO":"Status","STATUS_COLETA":"Status Coleta",
                  "DT_FAT":"Criação","PRAZO":"Prazo","PESO_KG":"Peso (kg)",
                  "DIAS_ATRASO":"Dias Atraso","STATUS_DIA":"Status Prazo"}
        existing = [c for c in cols if c in df_tab.columns]
        st.dataframe(df_tab[existing].rename(columns=rename),
                     use_container_width=True, hide_index=True)
        st.caption(f"{df_tab['PEDIDO'].nunique():,} pedidos | {df_tab['PESO_KG'].sum()/1000:,.1f} ton".replace(",","."))
