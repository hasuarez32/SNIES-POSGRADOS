"""
test_pipeline.py

Prueba local del pipeline de posgrado sin Selenium.
Usa dos Excel ya descargados en Programas/ para simular un run real.

Ejecución:
    python scripts/test_pipeline.py
"""

import sys
import logging
import shutil
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_snies_posgrado import (
    load_categorizacion,
    load_snapshot,
    detectar_novedades,
    merge_division,
    acumular,
    _guardar,
    NOVEDADES_DIR,
)

# ── Archivos a usar para la prueba ────────────────────────────────────────────
HOY_FILE     = ROOT / "Programas" / "Programas postgrado 27-08-25.xlsx"
ANTERIOR_FILE = ROOT / "Programas" / "Programas postgrado 20-08-25.xlsx"
TODAY = date(2025, 8, 27)

def main():
    log.info("╔══ TEST pipeline posgrado (sin descarga) ══╗")
    log.info(f"HOY      → {HOY_FILE.name}")
    log.info(f"ANTERIOR → {ANTERIOR_FILE.name}")

    NOVEDADES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Categorización
    cat = load_categorizacion()
    log.info(f"Categorización cargada: {len(cat)} entradas")

    # 2. Snapshots
    df_hoy = load_snapshot(HOY_FILE)
    df_ant = load_snapshot(ANTERIOR_FILE)
    log.info(f"Snapshot HOY:      {len(df_hoy)} programas")
    log.info(f"Snapshot ANTERIOR: {len(df_ant)} programas")

    # 3. Detectar novedades
    nuevos, inactivos, modificados = detectar_novedades(df_hoy, df_ant, TODAY)
    log.info(f"Nuevos={len(nuevos)} | Inactivos={len(inactivos)} | Modificados={len(modificados)}")

    # 4. Merge división
    nuevos    = merge_division(nuevos, cat)
    inactivos = merge_division(inactivos, cat)
    modificados = merge_division(modificados, cat)

    # 5. Acumular y guardar
    _guardar(acumular(NOVEDADES_DIR / "Nuevos posgrado.xlsx",     nuevos),     NOVEDADES_DIR / "Nuevos posgrado.xlsx")
    _guardar(acumular(NOVEDADES_DIR / "Inactivos posgrado.xlsx",  inactivos),  NOVEDADES_DIR / "Inactivos posgrado.xlsx")
    _guardar(acumular(NOVEDADES_DIR / "Modificados posgrado.xlsx",modificados),NOVEDADES_DIR / "Modificados posgrado.xlsx")

    # 6. Gráficos
    from analisis_historico_posgrado import generar_graficos
    chart_paths = generar_graficos()
    log.info(f"Gráficos generados: {chart_paths}")

    # 7. Muestra preview de novedades
    if not nuevos.empty:
        cols = ["NOMBRE_DEL_PROGRAMA", "NOMBRE_INSTITUCIÓN", "NIVEL_DE_FORMACIÓN", "DIVISIÓN UNINORTE"]
        cols = [c for c in cols if c in nuevos.columns]
        log.info(f"\n--- NUEVOS (primeros 5) ---\n{nuevos[cols].head().to_string()}")

    if not inactivos.empty:
        cols = ["NOMBRE_DEL_PROGRAMA", "NOMBRE_INSTITUCIÓN", "NIVEL_DE_FORMACIÓN", "DIVISIÓN UNINORTE"]
        cols = [c for c in cols if c in inactivos.columns]
        log.info(f"\n--- INACTIVOS (primeros 5) ---\n{inactivos[cols].head().to_string()}")

    if not modificados.empty:
        cols = ["NOMBRE_DEL_PROGRAMA", "QUE_CAMBIO", "DIVISIÓN UNINORTE"]
        cols = [c for c in cols if c in modificados.columns]
        log.info(f"\n--- MODIFICADOS (primeros 5) ---\n{modificados[cols].head().to_string()}")

    log.info("╚══ TEST finalizado. ══╝")

if __name__ == "__main__":
    main()
