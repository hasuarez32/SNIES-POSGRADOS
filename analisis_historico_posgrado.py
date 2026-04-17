"""
analisis_historico_posgrado.py

Genera dos gráficos para posgrado:

1. Novedades — Nuevos vs Inactivos por División Uninorte.
2. Divisiones Uninorte con más programas únicos modificados.

Ejecución standalone:
    python analisis_historico_posgrado.py

También puede ser importado desde run_snies_posgrado.py:
    from analisis_historico_posgrado import generar_graficos
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
NOVEDADES_DIR = BASE / "Análisis programas postgrado SNIES"

DIV_COL = "DIVISIÓN UNINORTE"
SNIES_COL = "CÓDIGO_SNIES_DEL_PROGRAMA"

COLOR_NUEVOS = "#2ca02c"
COLOR_INACTIVOS = "#d62728"
COLOR_MODIFICADOS = "#ff7f0e"


def _conteo_por_division(path: Path) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=int)
    df = pd.read_excel(path)
    col = next((c for c in df.columns if "DIVIS" in c.upper() and "UNINORTE" in c.upper()), None)
    if col is None:
        return pd.Series(dtype=int)
    return df[col].value_counts()


def _chart_nuevos_vs_inactivos(conteos: pd.DataFrame, out_path: Path) -> None:
    n = len(conteos)
    height = 0.35
    fig, ax = plt.subplots(figsize=(12, max(5, n * 0.7)))
    y = range(n)

    bars_n = ax.barh(
        [i + height / 2 for i in y],
        conteos["Nuevos"],
        height=height,
        color=COLOR_NUEVOS,
        label="Nuevos",
    )
    bars_i = ax.barh(
        [i - height / 2 for i in y],
        conteos["Inactivos"],
        height=height,
        color=COLOR_INACTIVOS,
        label="Inactivos",
    )

    ax.bar_label(bars_n, padding=3, fontsize=8)
    ax.bar_label(bars_i, padding=3, fontsize=8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(conteos.index, fontsize=9)
    ax.set_xlabel("Número de programas")
    ax.set_title(
        "Nuevos vs Inactivos por División Uninorte — Posgrado\n"
        "(acumulado histórico de detecciones)",
        fontsize=12,
        fontweight="bold",
    )
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _conteo_modificados_unicos_por_division(path: Path) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=int)
    df = pd.read_excel(path)
    div_col = next((c for c in df.columns if "DIVIS" in c.upper() and "UNINORTE" in c.upper()), None)
    if div_col is None:
        return pd.Series(dtype=int)
    df = df.copy()
    df[div_col] = df[div_col].fillna("Sin clasificar")
    if SNIES_COL in df.columns:
        df[SNIES_COL] = pd.to_numeric(df[SNIES_COL], errors="coerce")
        df = df.dropna(subset=[SNIES_COL])
        df[SNIES_COL] = df[SNIES_COL].astype(int)
        conteo = df.groupby(div_col)[SNIES_COL].nunique()
    else:
        conteo = df[div_col].value_counts()
    return conteo.sort_values(ascending=False)


def _chart_modificados_unicos_por_division(conteo: pd.Series, out_path: Path, top_n: int = 10) -> None:
    top = conteo.head(top_n).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(12, max(5, len(top) * 0.65)))
    bars = ax.barh(top.index, top.values, color=COLOR_MODIFICADOS)
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_xlabel("Programas únicos modificados")
    ax.set_title(
        "Top divisiones Uninorte con más programas únicos modificados — Posgrado",
        fontsize=12,
        fontweight="bold",
    )
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generar_graficos() -> list[str]:
    """
    Genera los dos gráficos operativos para posgrado.
    Devuelve la lista de rutas de los PNG generados.
    """
    NOVEDADES_DIR.mkdir(parents=True, exist_ok=True)
    generados: list[str] = []

    # Gráfico 1: Nuevos vs Inactivos por división
    nuevos_c = _conteo_por_division(NOVEDADES_DIR / "Nuevos posgrado.xlsx").rename("Nuevos")
    inactivos_c = _conteo_por_division(NOVEDADES_DIR / "Inactivos posgrado.xlsx").rename("Inactivos")
    conteos = (
        pd.concat([nuevos_c, inactivos_c], axis=1)
        .fillna(0)
        .astype(int)
        .sort_values("Nuevos", ascending=True)
    )

    out_path = NOVEDADES_DIR / "grafico_novedades_posgrado.png"
    if not conteos.empty and conteos[["Nuevos", "Inactivos"]].sum().sum() > 0:
        if out_path.exists():
            out_path.unlink()
        _chart_nuevos_vs_inactivos(conteos, out_path)
        generados.append(str(out_path))
        print(f"[posgrado] Gráfico guardado: {out_path}")
    else:
        print("[posgrado] Sin datos suficientes para el gráfico de novedades.")

    # Gráfico 2: Modificados únicos por división
    modificados = _conteo_modificados_unicos_por_division(NOVEDADES_DIR / "Modificados posgrado.xlsx")
    out_mod = NOVEDADES_DIR / "grafico_modificados_unicos_por_division_posgrado.png"
    if modificados.empty:
        print("[posgrado] Sin datos suficientes para el gráfico de modificados por división.")
    else:
        if out_mod.exists():
            out_mod.unlink()
        _chart_modificados_unicos_por_division(modificados, out_mod)
        generados.append(str(out_mod))
        print(f"[posgrado] Gráfico guardado: {out_mod}")

    return generados


def main() -> None:
    print("Generando gráficos de posgrado SNIES...")
    generados = generar_graficos()
    print(f"{len(generados)} gráfico(s) generado(s). Listo.")


if __name__ == "__main__":
    main()
