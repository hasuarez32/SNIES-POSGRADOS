#!/usr/bin/env python3
"""
generar_dashboard.py
Genera el dashboard HTML para SNIES Posgrado.

Produce:
  docs/index.html
  docs/nuevos.html
  docs/inactivos.html
  docs/modificados.html

Ejecutar desde la raíz del repositorio:
  python docs/generar_dashboard.py
"""
import json
import glob
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DOCS = Path(__file__).parent
NOVEDADES = ROOT / "data" / "novedades"
PROGRAMAS = ROOT / "Programas"

# ── Columnas ───────────────────────────────────────────────────────────────────

COLS_DETAIL = [
    "FECHA_OBTENCION",
    "CÓDIGO_SNIES_DEL_PROGRAMA",
    "NOMBRE_DEL_PROGRAMA",
    "NOMBRE_INSTITUCIÓN",
    "NIVEL_DE_FORMACIÓN",
    "SECTOR",
    "MODALIDAD",
    "DEPARTAMENTO_OFERTA_PROGRAMA",
    "MUNICIPIO_OFERTA_PROGRAMA",
    "NÚMERO_CRÉDITOS",
    "COSTO_MATRÍCULA_ESTUD_NUEVOS",
    "PERIODICIDAD",
    "FECHA_DE_REGISTRO_EN_SNIES",
    "CINE_F_2013_AC_CAMPO_AMPLIO",
    "DIVISIÓN UNINORTE",
]

COLS_MOD_DETAIL = [
    "FECHA_OBTENCION",
    "QUE_CAMBIO",
    "CÓDIGO_SNIES_DEL_PROGRAMA",
    "NOMBRE_DEL_PROGRAMA",
    "NOMBRE_INSTITUCIÓN",
    "NIVEL_DE_FORMACIÓN",
    "SECTOR",
    "MODALIDAD",
    "MODALIDAD_ANTERIOR",
    "DEPARTAMENTO_OFERTA_PROGRAMA",
    "NÚMERO_CRÉDITOS",
    "NÚMERO_CRÉDITOS_ANTERIOR",
    "COSTO_MATRÍCULA_ESTUD_NUEVOS",
    "COSTO_MATRÍCULA_ESTUD_NUEVOS_ANTERIOR",
    "FECHA_DE_REGISTRO_EN_SNIES",
    "DIVISIÓN UNINORTE",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_fecha(val):
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _fecha_str(dt):
    return dt.strftime("%Y-%m-%d") if dt else ""


def _normalizar_fechas(df):
    if "FECHA_OBTENCION" not in df.columns:
        return df
    df = df.copy()
    df["FECHA_OBTENCION"] = df["FECHA_OBTENCION"].apply(
        lambda x: _fecha_str(_parse_fecha(x))
    )
    return df


def _count_last(df):
    if df.empty or "FECHA_OBTENCION" not in df.columns:
        return 0, ""
    dates = df["FECHA_OBTENCION"].apply(_parse_fecha)
    valid = dates.dropna()
    if valid.empty:
        return len(df), ""
    last = valid.max()
    mask = dates.apply(lambda d: d == last if d else False)
    return int(mask.sum()), _fecha_str(last)


def _to_records(df, cols):
    available = [c for c in cols if c in df.columns]
    df2 = df[available].copy()
    if "FECHA_OBTENCION" in df2.columns:
        df2 = df2.sort_values("FECHA_OBTENCION", ascending=False)
    records = []
    for _, row in df2.iterrows():
        rec = {}
        for c in available:
            v = row[c]
            if pd.isna(v):
                rec[c] = ""
            elif isinstance(v, float) and v == int(v):
                rec[c] = str(int(v))
            else:
                rec[c] = str(v)
        records.append(rec)
    return records


def _top_n(df, col, n=10):
    if col not in df.columns:
        return [], []
    vc = df[col].fillna("N/A").value_counts().head(n)
    return vc.index.tolist(), vc.values.tolist()


def _unique_sorted(df, col):
    if col not in df.columns:
        return []
    return sorted(df[col].dropna().unique().tolist())


def _timeline_snaps():
    snaps = glob.glob(str(PROGRAMAS / "Programas postgrado *.xlsx"))
    rows = []
    for s in snaps:
        m = re.search(r"(\d{2}-\d{2}-\d{2,4})", s)
        if not m:
            continue
        raw = m.group(1)
        parts = raw.split("-")
        dd, mm, yy = parts[0], parts[1], parts[2]
        if len(yy) == 2:
            yy = "20" + yy
        try:
            dt = datetime(int(yy), int(mm), int(dd))
        except ValueError:
            continue
        try:
            df = pd.read_excel(s, usecols=["NOMBRE_DEL_PROGRAMA"])
            rows.append((dt, len(df)))
        except Exception:
            continue
    rows.sort(key=lambda x: x[0])
    return [r[0].strftime("%Y-%m-%d") for r in rows], [r[1] for r in rows]


def _que_cambio_campo(s):
    if not s:
        return "Otro"
    return str(s).split(":")[0].strip()


# ── CSS compartido ─────────────────────────────────────────────────────────────

COMMON_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f0f2f5; color: #1a1a2e; font-size: 14px; }
header { background: linear-gradient(135deg, #003f88 0%, #0059c1 100%);
         color: #fff; padding: 1.2rem 2rem;
         display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }
header h1 { font-size: 1.4rem; font-weight: 700; }
header .sub { font-size: 0.82rem; opacity: 0.8; margin-top: 3px; }
.back { color: #ffd166; text-decoration: none; font-size: 0.82rem;
        border: 1px solid rgba(255,209,102,0.5); padding: 5px 12px;
        border-radius: 5px; white-space: nowrap; margin-left: auto; }
.back:hover { background: rgba(255,209,102,0.15); }
main { max-width: 1440px; margin: 0 auto; padding: 1.5rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
         gap: 1rem; margin-bottom: 1.5rem; }
.card { background: #fff; border-radius: 10px; padding: 1.2rem 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.card .label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: .06em;
               color: #6b7280; margin-bottom: 4px; }
.card .value { font-size: 2rem; font-weight: 800; color: #003f88; line-height: 1.1; }
.card .sub { font-size: 0.77rem; color: #9ca3af; margin-top: 4px; }
.card.green .value { color: #059669; }
.card.red .value { color: #dc2626; }
.card.amber .value { color: #d97706; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
          gap: 1rem; margin-bottom: 1.5rem; }
.chart-box { background: #fff; border-radius: 10px; padding: 1rem 1.2rem;
             box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.chart-box h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: .06em;
                color: #6b7280; margin-bottom: 0.6rem; }
.filters { background: #fff; border-radius: 10px; padding: 1rem 1.5rem;
           box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 1.5rem;
           display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: flex-end; }
.fg { display: flex; flex-direction: column; gap: 3px; }
.fg label { font-size: 0.68rem; text-transform: uppercase; color: #6b7280;
             letter-spacing: .05em; font-weight: 600; }
.fg select, .fg input {
  border: 1px solid #e5e7eb; border-radius: 6px; padding: 6px 10px;
  font-size: 0.83rem; color: #1a1a2e; background: #f9fafb; min-width: 140px; }
.fg select:focus, .fg input:focus {
  outline: none; border-color: #003f88; background: #fff; box-shadow: 0 0 0 2px rgba(0,63,136,.1); }
.btn-clear { padding: 6px 14px; border: 1px solid #e5e7eb; border-radius: 6px;
             background: #f9fafb; cursor: pointer; font-size: 0.83rem;
             color: #6b7280; align-self: flex-end; }
.btn-clear:hover { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.table-wrap { background: #fff; border-radius: 10px; padding: 1rem 1.2rem;
              box-shadow: 0 2px 8px rgba(0,0,0,0.07); overflow-x: auto; }
.table-info { font-size: 0.8rem; color: #6b7280; margin-bottom: 0.75rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th { background: #f8fafc; position: sticky; top: 0; z-index: 1;
     border-bottom: 2px solid #e5e7eb; padding: 9px 10px; text-align: left;
     white-space: nowrap; cursor: pointer; user-select: none;
     color: #374151; font-weight: 600; }
th:hover { background: #eff6ff; color: #003f88; }
th.asc::after { content: ' ↑'; color: #003f88; }
th.desc::after { content: ' ↓'; color: #003f88; }
td { border-bottom: 1px solid #f3f4f6; padding: 7px 10px; vertical-align: top; }
td.prog { max-width: 260px; }
td.inst { max-width: 220px; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f5f9ff; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 0.7rem; font-weight: 600; white-space: nowrap; }
.b-oficial { background: #dbeafe; color: #1e40af; }
.b-privado { background: #fef3c7; color: #92400e; }
.b-maestria { background: #ede9fe; color: #5b21b6; }
.b-doctorado { background: #fce7f3; color: #9d174d; }
.b-esp-univ { background: #d1fae5; color: #065f46; }
.b-esp-med { background: #ffedd5; color: #9a3412; }
.b-esp-tec { background: #e0f2fe; color: #075985; }
.change-pill { background: #fff7ed; color: #9a3412; padding: 2px 7px;
               border-radius: 5px; font-family: monospace; font-size: 0.75rem;
               display: inline-block; max-width: 300px; word-break: break-all; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
"""

PLOTLY_CDN = '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>'

PLOTLY_LAYOUT = """{
  margin: {l:10,r:10,t:10,b:10},
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: {family: 'inherit', size: 11},
  showlegend: false
}"""

CFG = "{responsive:true, displayModeBar:false}"

# ── Badge helpers (JS) ─────────────────────────────────────────────────────────

JS_BADGES = """
function sectorBadge(s) {
  if (!s) return '';
  const cls = s === 'Oficial' ? 'b-oficial' : 'b-privado';
  return `<span class="badge ${cls}">${s}</span>`;
}
function nivelBadge(n) {
  if (!n) return n;
  const m = {
    'Maestría': 'b-maestria',
    'Doctorado': 'b-doctorado',
    'Especialización universitaria': 'b-esp-univ',
    'Especialización médico quirúrgica': 'b-esp-med',
    'Especialización tecnológica': 'b-esp-tec',
  };
  const cls = m[n] || 'b-esp-univ';
  return `<span class="badge ${cls}">${n}</span>`;
}
function changePill(s) {
  if (!s) return '';
  return `<span class="change-pill">${s}</span>`;
}
function fmt(v) { return v || '—'; }
function fmtNum(v) {
  if (!v) return '—';
  const n = parseFloat(v);
  return isNaN(n) ? v : n.toLocaleString('es-CO');
}
"""

# ── index.html ─────────────────────────────────────────────────────────────────

def build_index(df_n, df_i, df_m, snap_dates, snap_counts, today):
    last_n, fecha_n = _count_last(df_n)
    last_i, fecha_i = _count_last(df_i)
    last_m, fecha_m = _count_last(df_m)
    total_snap = snap_counts[-1] if snap_counts else 0

    niv_n_lbl, niv_n_val = _top_n(df_n, "NIVEL_DE_FORMACIÓN")
    niv_i_lbl, niv_i_val = _top_n(df_i, "NIVEL_DE_FORMACIÓN")
    sec_n_lbl, sec_n_val = _top_n(df_n, "SECTOR")
    div_n_lbl, div_n_val = _top_n(df_n, "DIVISIÓN UNINORTE", 12)
    dep_i_lbl, dep_i_val = _top_n(df_i, "DEPARTAMENTO_OFERTA_PROGRAMA", 12)

    data_js = json.dumps({
        "timeline": {"dates": snap_dates, "counts": snap_counts},
        "niv_n": {"labels": niv_n_lbl, "values": niv_n_val},
        "niv_i": {"labels": niv_i_lbl, "values": niv_i_val},
        "sec_n": {"labels": sec_n_lbl, "values": sec_n_val},
        "div_n": {"labels": div_n_lbl, "values": div_n_val},
        "dep_i": {"labels": dep_i_lbl, "values": dep_i_val},
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNIES Monitor · Posgrado</title>
<style>
{COMMON_CSS}
.hero {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
         gap:1rem; margin-bottom:1.5rem; }}
.hero-card {{ background:#fff; border-radius:12px; padding:1.5rem;
              box-shadow:0 2px 8px rgba(0,0,0,.07); text-decoration:none;
              color:inherit; border-left:5px solid #e5e7eb;
              transition:transform .15s,box-shadow .15s; display:block; }}
.hero-card:hover {{ transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.12); }}
.hero-card.green {{ border-color:#059669; }}
.hero-card.red {{ border-color:#dc2626; }}
.hero-card.amber {{ border-color:#d97706; }}
.hc-tag {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.07em;
           color:#6b7280; font-weight:700; margin-bottom:6px; }}
.hc-num {{ font-size:2.6rem; font-weight:800; line-height:1; }}
.hero-card.green .hc-num {{ color:#059669; }}
.hero-card.red .hc-num {{ color:#dc2626; }}
.hero-card.amber .hc-num {{ color:#d97706; }}
.hc-sub {{ font-size:.78rem; color:#9ca3af; margin-top:5px; }}
.hc-arrow {{ float:right; font-size:1.3rem; color:#d1d5db; margin-top:-36px; }}
.full {{ grid-column:1/-1 !important; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>SNIES Monitor · Posgrado</h1>
    <div class="sub">Programas de posgrado en Colombia · Actualizado: {today}</div>
  </div>
</header>
<main>
  <div class="cards">
    <div class="card">
      <div class="label">Programas activos (último snapshot)</div>
      <div class="value">{total_snap:,}</div>
      <div class="sub">{'Fecha: ' + snap_dates[-1] if snap_dates else ''}</div>
    </div>
    <div class="card green">
      <div class="label">Nuevos · último run</div>
      <div class="value">{last_n:,}</div>
      <div class="sub">Acumulado: {len(df_n):,} · {fecha_n}</div>
    </div>
    <div class="card red">
      <div class="label">Inactivos · último run</div>
      <div class="value">{last_i:,}</div>
      <div class="sub">Acumulado: {len(df_i):,} · {fecha_i}</div>
    </div>
    <div class="card amber">
      <div class="label">Modificados · último run</div>
      <div class="value">{last_m:,}</div>
      <div class="sub">Acumulado: {len(df_m):,} · {fecha_m}</div>
    </div>
  </div>

  <div class="hero">
    <a class="hero-card green" href="nuevos.html">
      <div class="hc-tag">Programas Nuevos</div>
      <div class="hc-num">{last_n:,}</div>
      <div class="hc-sub">en el último run &nbsp;·&nbsp; {len(df_n):,} acumulados</div>
      <div class="hc-arrow">→</div>
    </a>
    <a class="hero-card red" href="inactivos.html">
      <div class="hc-tag">Programas Inactivos</div>
      <div class="hc-num">{last_i:,}</div>
      <div class="hc-sub">en el último run &nbsp;·&nbsp; {len(df_i):,} acumulados</div>
      <div class="hc-arrow">→</div>
    </a>
    <a class="hero-card amber" href="modificados.html">
      <div class="hc-tag">Programas Modificados</div>
      <div class="hc-num">{last_m:,}</div>
      <div class="hc-sub">en el último run &nbsp;·&nbsp; {len(df_m):,} acumulados</div>
      <div class="hc-arrow">→</div>
    </a>
  </div>

  <div class="charts">
    <div class="chart-box full" style="grid-column:1/-1">
      <h3>Evolución histórica · programas de posgrado activos</h3>
      <div id="ch-tl" style="height:260px"></div>
    </div>
    <div class="chart-box">
      <h3>Nuevos por nivel de formación</h3>
      <div id="ch-niv-n" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Inactivos por nivel de formación</h3>
      <div id="ch-niv-i" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Nuevos por sector</h3>
      <div id="ch-sec" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Nuevos por División Uninorte</h3>
      <div id="ch-div" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Top 12 departamentos con más inactivos</h3>
      <div id="ch-dep-i" style="height:280px"></div>
    </div>
  </div>
</main>
{PLOTLY_CDN}
<script>
const D = {data_js};
const LAY = {PLOTLY_LAYOUT};
const CFG = {CFG};
const BL = ['#003f88','#0059c1','#2979d5','#5ba3e8','#98c9f5','#c3ddf5'];

Plotly.newPlot('ch-tl', [{{
  x: D.timeline.dates, y: D.timeline.counts, type:'scatter', mode:'lines+markers',
  line:{{color:'#003f88',width:2.5}}, marker:{{size:7,color:'#003f88'}},
  fill:'tozeroy', fillcolor:'rgba(0,63,136,0.07)',
  hovertemplate:'%{{x}}<br>%{{y:,}} programas<extra></extra>'
}}], {{...LAY, margin:{{l:60,r:20,t:20,b:60}},
       yaxis:{{tickformat:',d'}}}}, CFG);

Plotly.newPlot('ch-niv-n', [{{
  x: D.niv_n.values, y: D.niv_n.labels, type:'bar', orientation:'h',
  marker:{{color:'#059669'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:230,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-niv-i', [{{
  x: D.niv_i.values, y: D.niv_i.labels, type:'bar', orientation:'h',
  marker:{{color:'#dc2626'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:230,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-sec', [{{
  labels: D.sec_n.labels, values: D.sec_n.values, type:'pie', hole:0.42,
  marker:{{colors:['#003f88','#f0a500','#059669']}},
  textposition:'outside',
  hovertemplate:'%{{label}}<br>%{{value:,}} (%{{percent}})<extra></extra>'
}}], {{...LAY, margin:{{l:20,r:20,t:20,b:20}}, showlegend:true,
       legend:{{orientation:'h',y:-0.15}}}}, CFG);

Plotly.newPlot('ch-div', [{{
  x: D.div_n.values, y: D.div_n.labels, type:'bar', orientation:'h',
  marker:{{color:'#0059c1'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:260,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-dep-i', [{{
  x: D.dep_i.values, y: D.dep_i.labels, type:'bar', orientation:'h',
  marker:{{color:'#dc2626'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:160,r:30,t:10,b:30}}}}, CFG);
</script>
</body>
</html>"""


# ── Página de detalle (nuevos / inactivos) ─────────────────────────────────────

def build_detail_page(tipo, df, cols, color, today):
    last_count, last_fecha = _count_last(df)
    df = _normalizar_fechas(df)

    records = _to_records(df, cols)

    # Opciones de filtros
    opts_nivel  = _unique_sorted(df, "NIVEL_DE_FORMACIÓN")
    opts_sector = _unique_sorted(df, "SECTOR")
    opts_div    = _unique_sorted(df, "DIVISIÓN UNINORTE")
    opts_modal  = _unique_sorted(df, "MODALIDAD")
    opts_dep    = _unique_sorted(df, "DEPARTAMENTO_OFERTA_PROGRAMA")
    opts_fecha  = sorted(df["FECHA_OBTENCION"].dropna().unique().tolist(), reverse=True)

    # Gráficos
    niv_lbl, niv_val   = _top_n(df, "NIVEL_DE_FORMACIÓN")
    sec_lbl, sec_val   = _top_n(df, "SECTOR")
    inst_lbl, inst_val = _top_n(df, "NOMBRE_INSTITUCIÓN", 12)
    div_lbl, div_val   = _top_n(df, "DIVISIÓN UNINORTE")
    dep_lbl, dep_val   = _top_n(df, "DEPARTAMENTO_OFERTA_PROGRAMA", 15)
    mod_lbl, mod_val   = _top_n(df, "MODALIDAD")

    # Timeline por FECHA_OBTENCION
    if "FECHA_OBTENCION" in df.columns:
        tl = df.groupby("FECHA_OBTENCION").size().sort_index()
        tl_dates = tl.index.tolist()
        tl_vals  = tl.values.tolist()
    else:
        tl_dates, tl_vals = [], []

    titulos = {"nuevos": "Programas Nuevos", "inactivos": "Programas Inactivos"}
    titulo = titulos.get(tipo, tipo.capitalize())

    colores = {"nuevos": "#059669", "inactivos": "#dc2626"}
    col_hex = colores.get(tipo, color)

    col_keys = [c for c in cols if c in df.columns]
    headers_js  = json.dumps(col_keys, ensure_ascii=False)
    records_js  = json.dumps(records, ensure_ascii=False)
    opts_nivel_js  = json.dumps(opts_nivel,  ensure_ascii=False)
    opts_sector_js = json.dumps(opts_sector, ensure_ascii=False)
    opts_div_js    = json.dumps(opts_div,    ensure_ascii=False)
    opts_modal_js  = json.dumps(opts_modal,  ensure_ascii=False)
    opts_dep_js    = json.dumps(opts_dep,    ensure_ascii=False)
    opts_fecha_js  = json.dumps(opts_fecha,  ensure_ascii=False)

    charts_js = json.dumps({
        "niv":  {"labels": niv_lbl,  "values": niv_val},
        "sec":  {"labels": sec_lbl,  "values": sec_val},
        "inst": {"labels": inst_lbl, "values": inst_val},
        "div":  {"labels": div_lbl,  "values": div_val},
        "dep":  {"labels": dep_lbl,  "values": dep_val},
        "mod":  {"labels": mod_lbl,  "values": mod_val},
        "tl":   {"dates": tl_dates,  "values": tl_vals},
    }, ensure_ascii=False)

    col_header_html = "".join(f"<th data-col='{c}'>{c}</th>" for c in col_keys)

    def _opt_html(values):
        return "".join(f'<option value="{v}">{v}</option>' for v in values)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNIES Posgrado · {titulo}</title>
<style>
{COMMON_CSS}
</style>
</head>
<body>
<header>
  <div>
    <h1>SNIES Monitor · Posgrado</h1>
    <div class="sub">{titulo} · Actualizado: {today}</div>
  </div>
  <a class="back" href="index.html">← Dashboard</a>
</header>
<main>
  <div class="cards">
    <div class="card">
      <div class="label">Total acumulado</div>
      <div class="value" style="color:{col_hex}">{len(df):,}</div>
      <div class="sub">todos los runs</div>
    </div>
    <div class="card">
      <div class="label">Último run</div>
      <div class="value" style="color:{col_hex}">{last_count:,}</div>
      <div class="sub">{last_fecha}</div>
    </div>
    <div class="card">
      <div class="label">Registros mostrados</div>
      <div class="value" id="rec-count" style="color:#374151">—</div>
      <div class="sub">según filtros activos</div>
    </div>
  </div>

  <div class="filters">
    <div class="fg">
      <label>Nivel de formación</label>
      <select id="f-nivel"><option value="">Todos</option>
        {_opt_html(opts_nivel)}</select>
    </div>
    <div class="fg">
      <label>Sector</label>
      <select id="f-sector"><option value="">Todos</option>
        {_opt_html(opts_sector)}</select>
    </div>
    <div class="fg">
      <label>División Uninorte</label>
      <select id="f-div"><option value="">Todas</option>
        {_opt_html(opts_div)}</select>
    </div>
    <div class="fg">
      <label>Modalidad</label>
      <select id="f-modal"><option value="">Todas</option>
        {_opt_html(opts_modal)}</select>
    </div>
    <div class="fg">
      <label>Departamento</label>
      <select id="f-dep"><option value="">Todos</option>
        {_opt_html(opts_dep)}</select>
    </div>
    <div class="fg">
      <label>Fecha run</label>
      <select id="f-fecha"><option value="">Todas</option>
        {_opt_html(opts_fecha)}</select>
    </div>
    <div class="fg">
      <label>Buscar</label>
      <input id="f-search" type="text" placeholder="Nombre, código, institución…">
    </div>
    <button class="btn-clear" onclick="clearFilters()">Limpiar</button>
  </div>

  <div class="charts" id="charts-section">
    <div class="chart-box" style="grid-column:1/-1">
      <h3>{tipo.capitalize()} por fecha de run</h3>
      <div id="ch-tl" style="height:200px"></div>
    </div>
    <div class="chart-box">
      <h3>Por nivel de formación</h3>
      <div id="ch-niv" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Por sector</h3>
      <div id="ch-sec" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Top 12 instituciones</h3>
      <div id="ch-inst" style="height:320px"></div>
    </div>
    <div class="chart-box">
      <h3>Por División Uninorte</h3>
      <div id="ch-div" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Top 15 departamentos</h3>
      <div id="ch-dep" style="height:320px"></div>
    </div>
    <div class="chart-box">
      <h3>Por modalidad</h3>
      <div id="ch-mod" style="height:280px"></div>
    </div>
  </div>

  <div class="table-wrap">
    <div class="table-info" id="tbl-info"></div>
    <table id="tbl">
      <thead><tr>{col_header_html}</tr></thead>
      <tbody id="tbl-body"></tbody>
    </table>
  </div>
</main>
{PLOTLY_CDN}
<script>
const HEADERS = {headers_js};
const ALL_DATA = {records_js};
const C = {charts_js};
const COL_HEX = '{col_hex}';

{JS_BADGES}

// ── Sort state ──────────────────────────────────────────────────────────────
let sortCol = 'FECHA_OBTENCION', sortDir = -1;

function getFiltered() {{
  const nivel  = document.getElementById('f-nivel').value;
  const sector = document.getElementById('f-sector').value;
  const div    = document.getElementById('f-div').value;
  const modal  = document.getElementById('f-modal').value;
  const dep    = document.getElementById('f-dep').value;
  const fecha  = document.getElementById('f-fecha').value;
  const q      = document.getElementById('f-search').value.toLowerCase();
  return ALL_DATA.filter(r => {{
    if (nivel  && r['NIVEL_DE_FORMACIÓN']        !== nivel)  return false;
    if (sector && r['SECTOR']                    !== sector) return false;
    if (div    && r['DIVISIÓN UNINORTE']          !== div)    return false;
    if (modal  && r['MODALIDAD']                 !== modal)  return false;
    if (dep    && r['DEPARTAMENTO_OFERTA_PROGRAMA'] !== dep)  return false;
    if (fecha  && r['FECHA_OBTENCION']            !== fecha)  return false;
    if (q) {{
      const hay = Object.values(r).join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});
}}

function cellHtml(col, val) {{
  if (col === 'SECTOR') return sectorBadge(val);
  if (col === 'NIVEL_DE_FORMACIÓN') return nivelBadge(val);
  if (col === 'COSTO_MATRÍCULA_ESTUD_NUEVOS') return `<span class="num">${{fmtNum(val)}}</span>`;
  if (col === 'NÚMERO_CRÉDITOS') return `<span class="num">${{fmt(val)}}</span>`;
  return fmt(val);
}}

function renderTable(data) {{
  const sorted = [...data].sort((a,b) => {{
    const av = a[sortCol] || '', bv = b[sortCol] || '';
    return av < bv ? -sortDir : av > bv ? sortDir : 0;
  }});
  const tbody = document.getElementById('tbl-body');
  tbody.innerHTML = sorted.map(r => {{
    const cells = HEADERS.map(h => {{
      const tdClass = h === 'NOMBRE_DEL_PROGRAMA' ? ' class="prog"'
                    : h === 'NOMBRE_INSTITUCIÓN'  ? ' class="inst"' : '';
      return `<td${{tdClass}}>${{cellHtml(h, r[h])}}</td>`;
    }}).join('');
    return `<tr>${{cells}}</tr>`;
  }}).join('');
  document.getElementById('rec-count').textContent = data.length.toLocaleString('es-CO');
  document.getElementById('tbl-info').textContent =
    `Mostrando ${{data.length.toLocaleString('es-CO')}} de ${{ALL_DATA.length.toLocaleString('es-CO')}} registros`;
}}

function update() {{
  renderTable(getFiltered());
}}

function clearFilters() {{
  ['f-nivel','f-sector','f-div','f-modal','f-dep','f-fecha'].forEach(id => {{
    document.getElementById(id).value = '';
  }});
  document.getElementById('f-search').value = '';
  update();
}}

// ── Sort on header click ────────────────────────────────────────────────────
document.getElementById('tbl').querySelector('thead').addEventListener('click', e => {{
  const th = e.target.closest('th');
  if (!th) return;
  const col = th.dataset.col;
  if (sortCol === col) {{ sortDir *= -1; }}
  else {{ sortCol = col; sortDir = -1; }}
  document.querySelectorAll('th').forEach(t => t.classList.remove('asc','desc'));
  th.classList.add(sortDir === 1 ? 'asc' : 'desc');
  update();
}});

['f-nivel','f-sector','f-div','f-modal','f-dep','f-fecha'].forEach(id =>
  document.getElementById(id).addEventListener('change', update));
document.getElementById('f-search').addEventListener('input', update);

// ── Init ────────────────────────────────────────────────────────────────────
update();

// ── Charts ──────────────────────────────────────────────────────────────────
const LAY = {PLOTLY_LAYOUT};
const CFG = {CFG};

Plotly.newPlot('ch-tl', [{{
  x: C.tl.dates, y: C.tl.values, type:'bar',
  marker:{{color: COL_HEX}},
  hovertemplate:'%{{x}}<br>%{{y:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:50,r:20,t:10,b:60}}}}, CFG);

Plotly.newPlot('ch-niv', [{{
  x: C.niv.values, y: C.niv.labels, type:'bar', orientation:'h',
  marker:{{color: COL_HEX}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:230,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-sec', [{{
  labels: C.sec.labels, values: C.sec.values, type:'pie', hole:0.42,
  marker:{{colors:['#003f88','#f0a500','#059669']}},
  hovertemplate:'%{{label}}<br>%{{value:,}} (%{{percent}})<extra></extra>'
}}], {{...LAY, margin:{{l:20,r:20,t:20,b:20}}, showlegend:true,
       legend:{{orientation:'h',y:-0.15}}}}, CFG);

Plotly.newPlot('ch-inst', [{{
  x: C.inst.values, y: C.inst.labels, type:'bar', orientation:'h',
  marker:{{color: COL_HEX}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:260,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-div', [{{
  x: C.div.values, y: C.div.labels, type:'bar', orientation:'h',
  marker:{{color:'#0059c1'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:260,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-dep', [{{
  x: C.dep.values, y: C.dep.labels, type:'bar', orientation:'h',
  marker:{{color:'#2979d5'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:160,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-mod', [{{
  x: C.mod.values, y: C.mod.labels, type:'bar', orientation:'h',
  marker:{{color:'#5ba3e8'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:190,r:30,t:10,b:30}}}}, CFG);
</script>
</body>
</html>"""


# ── modificados.html ───────────────────────────────────────────────────────────

def build_modificados(df, today):
    last_count, last_fecha = _count_last(df)
    df = _normalizar_fechas(df)

    # Extraer campo que cambió
    if "QUE_CAMBIO" in df.columns:
        df = df.copy()
        df["_campo"] = df["QUE_CAMBIO"].apply(_que_cambio_campo)
    else:
        df["_campo"] = "Desconocido"

    cols = COLS_MOD_DETAIL
    col_keys = [c for c in cols if c in df.columns]
    records = _to_records(df, cols)

    opts_nivel  = _unique_sorted(df, "NIVEL_DE_FORMACIÓN")
    opts_sector = _unique_sorted(df, "SECTOR")
    opts_div    = _unique_sorted(df, "DIVISIÓN UNINORTE")
    opts_campo  = _unique_sorted(df, "_campo")
    opts_fecha  = sorted(df["FECHA_OBTENCION"].dropna().unique().tolist(), reverse=True)
    opts_dep    = _unique_sorted(df, "DEPARTAMENTO_OFERTA_PROGRAMA")

    campo_lbl, campo_val = _top_n(df, "_campo", 15)
    inst_lbl,  inst_val  = _top_n(df, "NOMBRE_INSTITUCIÓN", 12)
    niv_lbl,   niv_val   = _top_n(df, "NIVEL_DE_FORMACIÓN")
    div_lbl,   div_val   = _top_n(df, "DIVISIÓN UNINORTE")
    dep_lbl,   dep_val   = _top_n(df, "DEPARTAMENTO_OFERTA_PROGRAMA", 12)

    if "FECHA_OBTENCION" in df.columns:
        tl = df.groupby("FECHA_OBTENCION").size().sort_index()
        tl_dates, tl_vals = tl.index.tolist(), tl.values.tolist()
    else:
        tl_dates, tl_vals = [], []

    # Scatter créditos
    df_sc = df.dropna(subset=["NÚMERO_CRÉDITOS","NÚMERO_CRÉDITOS_ANTERIOR"]) \
               if "NÚMERO_CRÉDITOS" in df.columns and "NÚMERO_CRÉDITOS_ANTERIOR" in df.columns \
               else pd.DataFrame()
    sc_x, sc_y, sc_txt = [], [], []
    if not df_sc.empty:
        def _to_num(s):
            try: return float(str(s).replace(",","").strip())
            except: return None
        for _, row in df_sc.iterrows():
            xv = _to_num(row["NÚMERO_CRÉDITOS_ANTERIOR"])
            yv = _to_num(row["NÚMERO_CRÉDITOS"])
            if xv is not None and yv is not None and xv > 0 and yv > 0:
                sc_x.append(xv)
                sc_y.append(yv)
                sc_txt.append(str(row.get("NOMBRE_DEL_PROGRAMA",""))[:40])

    col_hex = "#d97706"
    headers_js  = json.dumps(col_keys, ensure_ascii=False)
    records_js  = json.dumps(records, ensure_ascii=False)
    opts_nivel_js  = json.dumps(opts_nivel,  ensure_ascii=False)
    opts_sector_js = json.dumps(opts_sector, ensure_ascii=False)
    opts_div_js    = json.dumps(opts_div,    ensure_ascii=False)
    opts_campo_js  = json.dumps(opts_campo,  ensure_ascii=False)
    opts_fecha_js  = json.dumps(opts_fecha,  ensure_ascii=False)
    opts_dep_js    = json.dumps(opts_dep,    ensure_ascii=False)

    def _opt_html(values):
        return "".join(f'<option value="{v}">{v}</option>' for v in values)

    charts_js = json.dumps({
        "campo": {"labels": campo_lbl, "values": campo_val},
        "inst":  {"labels": inst_lbl,  "values": inst_val},
        "niv":   {"labels": niv_lbl,   "values": niv_val},
        "div":   {"labels": div_lbl,   "values": div_val},
        "dep":   {"labels": dep_lbl,   "values": dep_val},
        "tl":    {"dates": tl_dates,   "values": tl_vals},
        "sc":    {"x": sc_x, "y": sc_y, "text": sc_txt},
    }, ensure_ascii=False)

    col_header_html = "".join(f"<th data-col='{c}'>{c}</th>" for c in col_keys)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNIES Posgrado · Modificados</title>
<style>
{COMMON_CSS}
</style>
</head>
<body>
<header>
  <div>
    <h1>SNIES Monitor · Posgrado</h1>
    <div class="sub">Programas Modificados · Actualizado: {today}</div>
  </div>
  <a class="back" href="index.html">← Dashboard</a>
</header>
<main>
  <div class="cards">
    <div class="card">
      <div class="label">Total acumulado</div>
      <div class="value" style="color:{col_hex}">{len(df):,}</div>
      <div class="sub">todos los runs</div>
    </div>
    <div class="card">
      <div class="label">Último run</div>
      <div class="value" style="color:{col_hex}">{last_count:,}</div>
      <div class="sub">{last_fecha}</div>
    </div>
    <div class="card">
      <div class="label">Registros mostrados</div>
      <div class="value" id="rec-count" style="color:#374151">—</div>
      <div class="sub">según filtros activos</div>
    </div>
  </div>

  <div class="filters">
    <div class="fg">
      <label>Nivel de formación</label>
      <select id="f-nivel"><option value="">Todos</option>
        {_opt_html(opts_nivel)}</select>
    </div>
    <div class="fg">
      <label>Sector</label>
      <select id="f-sector"><option value="">Todos</option>
        {_opt_html(opts_sector)}</select>
    </div>
    <div class="fg">
      <label>División Uninorte</label>
      <select id="f-div"><option value="">Todas</option>
        {_opt_html(opts_div)}</select>
    </div>
    <div class="fg">
      <label>Campo que cambió</label>
      <select id="f-campo"><option value="">Todos</option>
        {_opt_html(opts_campo)}</select>
    </div>
    <div class="fg">
      <label>Departamento</label>
      <select id="f-dep"><option value="">Todos</option>
        {_opt_html(opts_dep)}</select>
    </div>
    <div class="fg">
      <label>Fecha run</label>
      <select id="f-fecha"><option value="">Todas</option>
        {_opt_html(opts_fecha)}</select>
    </div>
    <div class="fg">
      <label>Buscar</label>
      <input id="f-search" type="text" placeholder="Nombre, código, institución…">
    </div>
    <button class="btn-clear" onclick="clearFilters()">Limpiar</button>
  </div>

  <div class="charts">
    <div class="chart-box" style="grid-column:1/-1">
      <h3>Modificaciones por fecha de run</h3>
      <div id="ch-tl" style="height:200px"></div>
    </div>
    <div class="chart-box">
      <h3>Campos que más cambian (top 15)</h3>
      <div id="ch-campo" style="height:360px"></div>
    </div>
    <div class="chart-box">
      <h3>Top 12 instituciones modificadas</h3>
      <div id="ch-inst" style="height:320px"></div>
    </div>
    <div class="chart-box">
      <h3>Por nivel de formación</h3>
      <div id="ch-niv" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Por División Uninorte</h3>
      <div id="ch-div" style="height:280px"></div>
    </div>
    <div class="chart-box">
      <h3>Top 12 departamentos afectados</h3>
      <div id="ch-dep" style="height:320px"></div>
    </div>
    <div class="chart-box">
      <h3>Créditos: antes vs después</h3>
      <div id="ch-sc" style="height:300px"></div>
    </div>
  </div>

  <div class="table-wrap">
    <div class="table-info" id="tbl-info"></div>
    <table id="tbl">
      <thead><tr>{col_header_html}</tr></thead>
      <tbody id="tbl-body"></tbody>
    </table>
  </div>
</main>
{PLOTLY_CDN}
<script>
const HEADERS = {headers_js};
const ALL_DATA = {records_js};
const C = {charts_js};

{JS_BADGES}

let sortCol = 'FECHA_OBTENCION', sortDir = -1;

function getFiltered() {{
  const nivel  = document.getElementById('f-nivel').value;
  const sector = document.getElementById('f-sector').value;
  const div    = document.getElementById('f-div').value;
  const campo  = document.getElementById('f-campo').value;
  const dep    = document.getElementById('f-dep').value;
  const fecha  = document.getElementById('f-fecha').value;
  const q      = document.getElementById('f-search').value.toLowerCase();
  return ALL_DATA.filter(r => {{
    if (nivel  && r['NIVEL_DE_FORMACIÓN']           !== nivel)  return false;
    if (sector && r['SECTOR']                       !== sector) return false;
    if (div    && r['DIVISIÓN UNINORTE']             !== div)    return false;
    if (fecha  && r['FECHA_OBTENCION']               !== fecha)  return false;
    if (dep    && r['DEPARTAMENTO_OFERTA_PROGRAMA']  !== dep)    return false;
    if (campo) {{
      const qc = r['QUE_CAMBIO'] || '';
      if (!qc.startsWith(campo)) return false;
    }}
    if (q) {{
      if (!Object.values(r).join(' ').toLowerCase().includes(q)) return false;
    }}
    return true;
  }});
}}

function cellHtml(col, val) {{
  if (col === 'SECTOR') return sectorBadge(val);
  if (col === 'NIVEL_DE_FORMACIÓN') return nivelBadge(val);
  if (col === 'QUE_CAMBIO') return changePill(val);
  if (['COSTO_MATRÍCULA_ESTUD_NUEVOS','COSTO_MATRÍCULA_ESTUD_NUEVOS_ANTERIOR',
       'NÚMERO_CRÉDITOS','NÚMERO_CRÉDITOS_ANTERIOR'].includes(col))
    return `<span class="num">${{fmtNum(val)}}</span>`;
  return fmt(val);
}}

function renderTable(data) {{
  const sorted = [...data].sort((a,b) => {{
    const av = a[sortCol]||'', bv = b[sortCol]||'';
    return av < bv ? -sortDir : av > bv ? sortDir : 0;
  }});
  const tbody = document.getElementById('tbl-body');
  tbody.innerHTML = sorted.map(r => {{
    const cells = HEADERS.map(h => {{
      const cls = h === 'NOMBRE_DEL_PROGRAMA' ? ' class="prog"'
               : h === 'NOMBRE_INSTITUCIÓN'  ? ' class="inst"' : '';
      return `<td${{cls}}>${{cellHtml(h, r[h])}}</td>`;
    }}).join('');
    return `<tr>${{cells}}</tr>`;
  }}).join('');
  document.getElementById('rec-count').textContent = data.length.toLocaleString('es-CO');
  document.getElementById('tbl-info').textContent =
    `Mostrando ${{data.length.toLocaleString('es-CO')}} de ${{ALL_DATA.length.toLocaleString('es-CO')}} registros`;
}}

function update() {{ renderTable(getFiltered()); }}
function clearFilters() {{
  ['f-nivel','f-sector','f-div','f-campo','f-dep','f-fecha'].forEach(id =>
    document.getElementById(id).value = '');
  document.getElementById('f-search').value = '';
  update();
}}

document.getElementById('tbl').querySelector('thead').addEventListener('click', e => {{
  const th = e.target.closest('th');
  if (!th) return;
  const col = th.dataset.col;
  sortDir = sortCol === col ? sortDir * -1 : -1;
  sortCol = col;
  document.querySelectorAll('th').forEach(t => t.classList.remove('asc','desc'));
  th.classList.add(sortDir === 1 ? 'asc' : 'desc');
  update();
}});

['f-nivel','f-sector','f-div','f-campo','f-dep','f-fecha'].forEach(id =>
  document.getElementById(id).addEventListener('change', update));
document.getElementById('f-search').addEventListener('input', update);

update();

// ── Charts ──────────────────────────────────────────────────────────────────
const LAY = {PLOTLY_LAYOUT};
const CFG = {CFG};

Plotly.newPlot('ch-tl', [{{
  x: C.tl.dates, y: C.tl.values, type:'bar',
  marker:{{color:'#d97706'}},
  hovertemplate:'%{{x}}<br>%{{y:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:60,r:20,t:10,b:60}}}}, CFG);

Plotly.newPlot('ch-campo', [{{
  x: C.campo.values, y: C.campo.labels, type:'bar', orientation:'h',
  marker:{{color:'#d97706'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:230,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-inst', [{{
  x: C.inst.values, y: C.inst.labels, type:'bar', orientation:'h',
  marker:{{color:'#92400e'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:260,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-niv', [{{
  x: C.niv.values, y: C.niv.labels, type:'bar', orientation:'h',
  marker:{{color:'#b45309'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:230,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-div', [{{
  x: C.div.values, y: C.div.labels, type:'bar', orientation:'h',
  marker:{{color:'#0059c1'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:260,r:30,t:10,b:30}}}}, CFG);

Plotly.newPlot('ch-dep', [{{
  x: C.dep.values, y: C.dep.labels, type:'bar', orientation:'h',
  marker:{{color:'#2979d5'}},
  hovertemplate:'%{{y}}<br>%{{x:,}}<extra></extra>'
}}], {{...LAY, margin:{{l:160,r:30,t:10,b:30}}}}, CFG);

if (C.sc.x.length > 0) {{
  const maxV = Math.max(...C.sc.x, ...C.sc.y);
  Plotly.newPlot('ch-sc', [
    {{
      x: C.sc.x, y: C.sc.y, mode:'markers', type:'scatter',
      text: C.sc.text,
      marker:{{color:'#d97706', size:7, opacity:0.7}},
      hovertemplate:'%{{text}}<br>Antes: %{{x}}<br>Después: %{{y}}<extra></extra>'
    }},
    {{
      x:[0,maxV], y:[0,maxV], mode:'lines', type:'scatter',
      line:{{color:'#9ca3af', width:1, dash:'dot'}},
      hoverinfo:'skip', showlegend:false
    }}
  ], {{...LAY, margin:{{l:60,r:20,t:10,b:60}},
        xaxis:{{title:'Créditos anteriores'}},
        yaxis:{{title:'Créditos actuales'}}}}, CFG);
}} else {{
  document.getElementById('ch-sc').innerHTML =
    '<p style="color:#9ca3af;padding:2rem;text-align:center">Sin datos de créditos para comparar</p>';
}}
</script>
</body>
</html>"""


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    today = datetime.today().strftime("%Y-%m-%d")
    print(f"[{today}] Leyendo novedades…")

    df_n = pd.read_excel(NOVEDADES / "Nuevos_posgrado.xlsx")
    df_i = pd.read_excel(NOVEDADES / "Inactivos_posgrado.xlsx")
    df_m = pd.read_excel(NOVEDADES / "Modificados_posgrado.xlsx")

    print(f"  Nuevos: {len(df_n):,}  Inactivos: {len(df_i):,}  Modificados: {len(df_m):,}")

    snap_dates, snap_counts = _timeline_snaps()
    print(f"  Snapshots históricos: {len(snap_dates)}")

    DOCS.mkdir(exist_ok=True)

    print("Generando index.html…")
    (DOCS / "index.html").write_text(
        build_index(df_n, df_i, df_m, snap_dates, snap_counts, today),
        encoding="utf-8"
    )

    print("Generando nuevos.html…")
    (DOCS / "nuevos.html").write_text(
        build_detail_page("nuevos", df_n, COLS_DETAIL, "#059669", today),
        encoding="utf-8"
    )

    print("Generando inactivos.html…")
    (DOCS / "inactivos.html").write_text(
        build_detail_page("inactivos", df_i, COLS_DETAIL, "#dc2626", today),
        encoding="utf-8"
    )

    print("Generando modificados.html…")
    (DOCS / "modificados.html").write_text(
        build_modificados(df_m, today),
        encoding="utf-8"
    )

    print("OK Dashboard generado en docs/")
    for f in ["index.html","nuevos.html","inactivos.html","modificados.html"]:
        size = (DOCS / f).stat().st_size
        print(f"  {f}: {size/1024:.0f} KB")


if __name__ == "__main__":
    main()
