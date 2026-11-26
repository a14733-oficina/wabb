"""Tratamento dos lançamentos com Pandas e gráficos com Plotly / Seaborn."""
import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

ZONES = ["Área pintada", "Meia dist. esquerda", "Meia dist. direita",
         "Canto esquerdo", "Canto direito", "Topo do arco"]
ARC_R = 237.5          # raio da linha de 3 pontos (23,75 pés)
COURT_Y_MAX = 470      # meio-campo: 47 pés a partir da linha de fundo
MUT, PANEL = "#8a94a1", "#10151b"


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta a zona do campo e se o lançamento é de 3 pontos."""
    d = df.copy()
    x, y = d.loc_x, d.loc_y
    corner = (x.abs() >= 220) & (y <= 92.5)
    paint = (x.abs() <= 80) & (y <= 142.5)
    three = (np.hypot(x, y) >= ARC_R) | corner
    d["zone"] = np.select(
        [paint, corner & (x < 0), corner & (x >= 0), three, x < 0],
        ["Área pintada", "Canto esquerdo", "Canto direito", "Topo do arco", "Meia dist. esquerda"],
        default="Meia dist. direita")
    d["is3"] = three
    return d


def zone_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"attempts": 0, "made": 0, "fg_pct": None, "tp_attempts": 0, "tp_made": 0, "tp_pct": None, "zones": []}
    d = classify(df)
    g = d.groupby("zone").agg(att=("made", "size"), made=("made", "sum")).reindex(ZONES, fill_value=0)
    zones = [{"zone": z, "att": int(r.att), "made": int(r.made),
              "pct": float(r.made / r.att) if r.att else None} for z, r in g.iterrows()]
    t3 = d[d.is3]
    return {"attempts": int(len(d)), "made": int(d.made.sum()), "fg_pct": float(d.made.mean()),
            "tp_attempts": int(len(t3)), "tp_made": int(t3.made.sum()),
            "tp_pct": float(t3.made.mean()) if len(t3) else None, "zones": zones}


def court_shapes(color=MUT):
    ln = dict(color=color, width=1.5)
    return [
        dict(type="rect", x0=-250, y0=-52.5, x1=250, y1=COURT_Y_MAX, line=ln),
        dict(type="rect", x0=-80, y0=-52.5, x1=80, y1=142.5, line=ln),            # área pintada
        dict(type="circle", x0=-60, y0=82.5, x1=60, y1=202.5, line=ln),           # círculo dos lances livres
        dict(type="circle", x0=-7.5, y0=-7.5, x1=7.5, y1=7.5, line=ln),           # cesto
        dict(type="line", x0=-30, y0=-40, x1=30, y1=-40, line=ln),                # tabela
        dict(type="path", path="M -40 0 A 40 40 0 0 1 40 0", line=ln),            # zona restritiva
        dict(type="line", x0=-220, y0=-52.5, x1=-220, y1=89.5, line=ln),
        dict(type="line", x0=220, y0=-52.5, x1=220, y1=89.5, line=ln),
        dict(type="path", path="M -220 89.5 A 237.5 237.5 0 0 1 220 89.5",
             line=dict(color="#f4f7fb", width=2)),
        dict(type="line", x0=-250, y0=418, x1=250, y1=418, line=dict(color=color, width=1, dash="dot")),
    ]


def heat_figure(df: pd.DataFrame, mode: str = "volume", step: int = 25) -> str:
    """Mapa de calor (volume ou eficácia) sobre o campo. Devolve JSON do Plotly."""
    # A NBA pode devolver alguns pontos técnicos fora do campo. Não os deixamos
    # distorcer a escala nem aparecerem fora da representação do meio-campo.
    d = df.copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=["loc_x", "loc_y", "made"])
    d = d[(d.loc_x >= -250) & (d.loc_x <= 250) & (d.loc_y >= -52.5) & (d.loc_y <= COURT_Y_MAX)]
    if d.empty:
        d = pd.DataFrame({"loc_x": [], "loc_y": [], "made": []})
    xb = np.arange(-250, 250 + step, step)
    yb = np.arange(-50, COURT_Y_MAX + step, step)
    att, _, _ = np.histogram2d(d.loc_x, d.loc_y, bins=[xb, yb])
    mk, _, _ = np.histogram2d(d.loc_x[d.made.astype(bool)], d.loc_y[d.made.astype(bool)], bins=[xb, yb])
    xc, yc = (xb[:-1] + xb[1:]) / 2, (yb[:-1] + yb[1:]) / 2
    if mode == "volume":
        z, smooth = att.T, "best"
        scale = [[0, "rgba(16,21,27,0)"], [.05, "#073b4c"], [.22, "#00b4d8"], [.48, "#00f5d4"], [.72, "#ffe600"], [1, "#ff1744"]]
        title, hover = "Tentativas", "Tentativas: %{z:.0f}<extra></extra>"
    else:
        z = np.where(att >= 3, mk / np.maximum(att, 1), np.nan).T     # só células com 3+ lançamentos
        smooth = False
        scale = [[0, "#102a43"], [.25, "#0077b6"], [.5, "#00d4ff"], [.75, "#ffe600"], [1, "#ff1744"]]
        title, hover = "Eficácia", "Eficácia: %{z:.0%}<br>Tentativas: %{customdata:.0f}<extra></extra>"
    custom = att.T if mode != "volume" else None
    fig = go.Figure(go.Heatmap(x=xc, y=yc, z=z, customdata=custom, colorscale=scale,
                               zsmooth=smooth, hoverongaps=False, hovertemplate=hover,
                               colorbar=dict(thickness=12, len=.82, title=dict(text=title, font=dict(color=MUT)),
                                             tickfont=dict(color=MUT))))
    fig.update_layout(
        shapes=court_shapes(), height=620, margin=dict(t=10, r=10, b=10, l=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PANEL,
        xaxis=dict(visible=False, range=[-250, 250], fixedrange=True),
        yaxis=dict(visible=False, range=[-55, COURT_Y_MAX], scaleanchor="x", fixedrange=True))
    return pio.to_json(fig)


def trend_figure(seasons: list, stat: str, label: str) -> str:
    seasons = sorted(seasons, key=lambda s: s["season"])[-10:]
    x = [s["season"] for s in seasons]
    y = [s.get(stat) for s in seasons]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers+text", text=[f"{v:.1f}" if v is not None else "" for v in y],
                               textposition="top center", textfont=dict(color="#f2f4f6"),
                               line=dict(color="#f58a3c", width=3), marker=dict(size=8)))
    fig.update_layout(height=300, margin=dict(t=20, r=20, b=30, l=40), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color=MUT),
                      xaxis=dict(type="category"), yaxis=dict(title=label, gridcolor="#222a34"))
    return pio.to_json(fig)


def distance_png(df: pd.DataFrame) -> bytes:
    """Seaborn: distribuição da distância dos lançamentos (convertidos vs falhados)."""
    d = pd.DataFrame({"Distância (pés)": np.hypot(df.loc_x, df.loc_y) / 10,
                      "Resultado": np.where(df.made, "Convertido", "Falhado")})
    fig, ax = plt.subplots(figsize=(6, 3))
    sns.histplot(data=d, x="Distância (pés)", hue="Resultado", multiple="stack", bins=24, ax=ax,
                 palette={"Convertido": "#f58a3c", "Falhado": "#3b4654"}, edgecolor="none")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(colors=MUT); ax.xaxis.label.set_color(MUT); ax.yaxis.label.set_color(MUT)
    ax.set_ylabel("Lançamentos")
    leg = ax.get_legend()
    if leg:
        plt.setp(leg.get_texts(), color=MUT); leg.get_frame().set_alpha(0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, transparent=True, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
