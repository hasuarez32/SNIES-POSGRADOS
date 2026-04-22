"""
run_snies_posgrado.py

Orquestador principal del monitor SNIES para posgrado.

Descarga el snapshot de posgrado, detecta novedades (nuevos, inactivos,
modificados), acumula los resultados en data/novedades/ y llama al
módulo de correo.

Ejecución:
    python scripts/run_snies_posgrado.py
"""

import os
import re
import sys
import logging
import shutil
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ── Logging ───────────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Rutas base ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR     = ROOT / "data"
NOVEDADES_DIR = ROOT / "data" / "novedades"
PROGRAMAS_DIR = ROOT / "Programas"
CAT_FILE      = ROOT / "Categorización divisiones SNIES .xlsx"
TMP_DIR       = ROOT / "tmp"

NOVEDADES_DIR.mkdir(parents=True, exist_ok=True)
PROGRAMAS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Constantes ────────────────────────────────────────────────────────────────
SNIES_URL = "https://hecaa.mineducacion.gov.co/consultaspublicas/programas"
DOWNLOAD_TIMEOUT = 120

# XPath del botón de descarga — anclado al texto visible, no a IDs dinámicos JSF
# Los filtros ya no usan XPaths: se aplican via _pf_select_radio con los values del input
XPATHS = {
    "descarga": '//button[.//span[normalize-space()="Descargar programas"]]',
}

# ── Columnas de trabajo ───────────────────────────────────────────────────────
BASE_COLS = [
    "CÓDIGO_INSTITUCIÓN",
    "NOMBRE_INSTITUCIÓN",
    "SECTOR",
    "DEPARTAMENTO_OFERTA_PROGRAMA",
    "MUNICIPIO_OFERTA_PROGRAMA",
    "CÓDIGO_SNIES_DEL_PROGRAMA",
    "NOMBRE_DEL_PROGRAMA",
    "MODALIDAD",
    "NÚMERO_CRÉDITOS",
    "NÚMERO_PERIODOS_DE_DURACIÓN",
    "PERIODICIDAD",
    "COSTO_MATRÍCULA_ESTUD_NUEVOS",
    "PERIODICIDAD_ADMISIONES",
    "FECHA_DE_REGISTRO_EN_SNIES",
    "CINE_F_2013_AC_CAMPO_AMPLIO",
    "CINE_F_2013_AC_CAMPO_ESPECÍFIC",
    "CINE_F_2013_AC_CAMPO_DETALLADO",
    "NÚCLEO_BÁSICO_DEL_CONOCIMIENTO",
    "NIVEL_DE_FORMACIÓN",
]

COLS_VIGILAR = [
    "MODALIDAD",
    "NÚMERO_CRÉDITOS",
    "COSTO_MATRÍCULA_ESTUD_NUEVOS",
    "MUNICIPIO_OFERTA_PROGRAMA",
    "NIVEL_DE_FORMACIÓN",
]

# ── Selenium ──────────────────────────────────────────────────────────────────
def _build_driver(download_dir: Path, headless: bool = True) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        },
    )
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )


def _safe_click(driver: webdriver.Chrome, xpath: str, timeout: int = 15) -> None:
    locator = (By.XPATH, xpath)
    for attempt in range(2):
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
            el.click()
            return
        except (StaleElementReferenceException, TimeoutException):
            if attempt == 1:
                raise
            time.sleep(2)


def _click_radio_box(driver: webdriver.Chrome, box_xpath: str, label: str, timeout: int = 30) -> None:
    """Hace JavaScript .click() en el div.ui-radiobutton-box de PrimeFaces.
    PrimeFaces escucha click en el box (no onchange del input), así que esto
    dispara su handler jQuery que actualiza el input y llama PrimeFaces.ab()."""
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, box_xpath))
    )
    driver.execute_script("arguments[0].click();", el)
    log.info(f"[radio] click JS en box → {label}")


def _wait_ajax(driver: webdriver.Chrome, timeout: int = 20) -> None:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "return (typeof jQuery === 'undefined' || jQuery.active === 0) && "
                "(typeof PrimeFaces === 'undefined' || PrimeFaces.ajax.Queue.isEmpty())"
            )
        )
    except TimeoutException:
        log.warning("AJAX no terminó en %ds; continuando de todas formas.", timeout)


def descargar_snies(download_dir: Path) -> Path:
    xp = XPATHS
    expected_file = download_dir / "Programas.xlsx"
    partial_file = download_dir / "Programas.crdownload"

    for f in (expected_file, partial_file):
        if f.exists():
            f.unlink()

    headless = os.environ.get("SNIES_HEADLESS", "1") != "0"
    driver = _build_driver(download_dir, headless=headless)

    try:
        log.info("[posgrado] Abriendo SNIES...")
        driver.get(SNIES_URL)
        time.sleep(8)

        screenshot_path = TMP_DIR / "debug_snies.png"
        driver.save_screenshot(str(screenshot_path))
        log.info(f"[posgrado] Screenshot guardado en {screenshot_path}")

        log.info("[posgrado] Aplicando filtros (institución activa, programa activo, posgrado)...")
        # Usamos el LABEL para navegar al box — los labels con cuentas son únicos en la página.
        # label→padre(td)→hijo div.ui-radiobutton→hijo div.ui-radiobutton-box
        _click_radio_box(driver,
            '//label[normalize-space()="Activo"]/../div[contains(@class,"ui-radiobutton")]/div[contains(@class,"ui-radiobutton-box")]',
            "institución Activo")
        _wait_ajax(driver)
        time.sleep(3)

        _click_radio_box(driver,
            '//label[starts-with(normalize-space(),"Activo (")]/../div[contains(@class,"ui-radiobutton")]/div[contains(@class,"ui-radiobutton-box")]',
            "programa Activo")
        _wait_ajax(driver)
        time.sleep(3)

        _click_radio_box(driver,
            '//label[starts-with(normalize-space(),"Posgrado (")]/../div[contains(@class,"ui-radiobutton")]/div[contains(@class,"ui-radiobutton-box")]',
            "académico Posgrado")
        _wait_ajax(driver)
        time.sleep(5)

        # "Nivel Formación: Todos" es el default — no se toca para evitar ambigüedad
        # con los otros labels "Todos" del panel (Estado Institución, Tipo de sede, etc.)

        driver.save_screenshot(str(TMP_DIR / "debug_post_filtros.png"))
        log.info("[posgrado] Screenshot post-filtros guardado")

        log.info("[posgrado] Solicitando descarga...")
        _safe_click(driver, xp["descarga"])

        elapsed = 0
        while elapsed < DOWNLOAD_TIMEOUT:
            time.sleep(5)
            elapsed += 5
            if expected_file.exists() and not partial_file.exists():
                log.info(f"[posgrado] Descarga completada en {elapsed}s.")
                break
            log.info(f"[posgrado] Esperando descarga... ({elapsed}s)")
        else:
            raise TimeoutError(
                f"[posgrado] Archivo no apareció tras {DOWNLOAD_TIMEOUT}s. "
                "Verifica que los XPaths del portal no hayan cambiado."
            )

    finally:
        driver.quit()

    return expected_file


# ── Carga de datos ────────────────────────────────────────────────────────────
def load_categorizacion() -> pd.DataFrame:
    return (
        pd.read_excel(CAT_FILE, sheet_name="Hoja3")[
            ["CINE_F_2013_AC_CAMPO_DETALLADO", "DIVISIÓN UNINORTE"]
        ]
        .drop_duplicates()
    )


def load_snapshot(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Programas")
    df = df.iloc[:-2].copy()

    cols_ok = [c for c in BASE_COLS if c in df.columns]
    df = df[cols_ok].copy()

    df["CÓDIGO_SNIES_DEL_PROGRAMA"] = pd.to_numeric(
        df["CÓDIGO_SNIES_DEL_PROGRAMA"], errors="coerce"
    )
    df = df.dropna(subset=["CÓDIGO_SNIES_DEL_PROGRAMA"])
    df["CÓDIGO_SNIES_DEL_PROGRAMA"] = df["CÓDIGO_SNIES_DEL_PROGRAMA"].astype(int)
    df["NÚMERO_CRÉDITOS"] = df["NÚMERO_CRÉDITOS"].fillna(0).astype(int)
    df["FECHA_DE_REGISTRO_EN_SNIES"] = pd.to_datetime(
        df["FECHA_DE_REGISTRO_EN_SNIES"], errors="coerce"
    ).dt.date

    return df


# ── Lógica de negocio ─────────────────────────────────────────────────────────
def detectar_novedades(
    df_hoy: pd.DataFrame,
    df_ant: pd.DataFrame,
    today: date,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snies_hoy = set(df_hoy["CÓDIGO_SNIES_DEL_PROGRAMA"])
    snies_ant = set(df_ant["CÓDIGO_SNIES_DEL_PROGRAMA"])

    nuevosDF = df_hoy[df_hoy["CÓDIGO_SNIES_DEL_PROGRAMA"].isin(snies_hoy - snies_ant)].copy()
    inactivosDF = df_ant[df_ant["CÓDIGO_SNIES_DEL_PROGRAMA"].isin(snies_ant - snies_hoy)].copy()

    # Detectar modificados
    comunes = snies_hoy & snies_ant
    df_com_hoy = df_hoy[df_hoy["CÓDIGO_SNIES_DEL_PROGRAMA"].isin(comunes)]
    df_com_ant = df_ant[df_ant["CÓDIGO_SNIES_DEL_PROGRAMA"].isin(comunes)]

    _KEY = "CÓDIGO_SNIES_DEL_PROGRAMA"
    dups_hoy = df_com_hoy.duplicated(subset=_KEY, keep=False).sum()
    dups_ant = df_com_ant.duplicated(subset=_KEY, keep=False).sum()
    if dups_hoy:
        log.warning(f"[posgrado] Snapshot HOY tiene {dups_hoy} código(s) duplicado(s). Se conserva el primero.")
    if dups_ant:
        log.warning(f"[posgrado] Snapshot ANTERIOR tiene {dups_ant} código(s) duplicado(s). Se conserva el primero.")

    df_com_hoy = df_com_hoy.drop_duplicates(subset=_KEY, keep="first")
    df_com_ant = df_com_ant.drop_duplicates(subset=_KEY, keep="first")

    comparativa = df_com_hoy.merge(df_com_ant, on=_KEY, suffixes=("_NUEVO", "_ANTIGUO"))

    mascara = pd.Series(False, index=comparativa.index)
    for col in COLS_VIGILAR:
        col_n, col_a = f"{col}_NUEVO", f"{col}_ANTIGUO"
        if col_n in comparativa.columns and col_a in comparativa.columns:
            mascara |= (
                comparativa[col_n].fillna("").astype(str)
                != comparativa[col_a].fillna("").astype(str)
            )

    modificadosDF = comparativa[mascara].copy()

    def _que_cambio(row) -> str:
        partes = []
        for col in COLS_VIGILAR:
            col_n, col_a = f"{col}_NUEVO", f"{col}_ANTIGUO"
            if col_n in row.index and col_a in row.index:
                val_n = str(row[col_n]).strip()
                val_a = str(row[col_a]).strip()
                if val_n != val_a:
                    partes.append(f"{col}: {val_a} → {val_n}")
        return " | ".join(partes) if partes else "Cambio en otros campos"

    if not modificadosDF.empty:
        modificadosDF["QUE_CAMBIO"] = modificadosDF.apply(_que_cambio, axis=1)
        rn = {c: c[:-6] for c in modificadosDF.columns if c.endswith("_NUEVO")}
        ra = {c: c[:-8] + "_ANTERIOR" for c in modificadosDF.columns if c.endswith("_ANTIGUO")}
        modificadosDF = modificadosDF.rename(columns={**rn, **ra})

    today_str = today.strftime("%d/%m/%Y")
    for df_tmp in (nuevosDF, inactivosDF, modificadosDF):
        df_tmp["FECHA_OBTENCION"] = today_str
        df_tmp["Estado"] = df_tmp["CÓDIGO_SNIES_DEL_PROGRAMA"].apply(
            lambda x: "Activo" if x in snies_hoy else "Inactivo"
        )

    return nuevosDF, inactivosDF, modificadosDF


def merge_division(df: pd.DataFrame, cat: pd.DataFrame) -> pd.DataFrame:
    cine_col = "CINE_F_2013_AC_CAMPO_DETALLADO"
    if cine_col not in df.columns or df.empty:
        df = df.copy()
        df["DIVISIÓN UNINORTE"] = "Sin clasificar"
        return df
    df = df.merge(cat, on=cine_col, how="left")
    df["DIVISIÓN UNINORTE"] = df["DIVISIÓN UNINORTE"].fillna("Sin clasificar")
    return df


def acumular(existing_path: Path, nuevo_df: pd.DataFrame) -> pd.DataFrame:
    dedup_cols = ["CÓDIGO_SNIES_DEL_PROGRAMA", "FECHA_OBTENCION"]
    if existing_path.exists():
        existing = pd.read_excel(existing_path)
        if nuevo_df.empty:
            return existing
        combined = pd.concat([existing, nuevo_df], ignore_index=True)
        return combined.drop_duplicates(subset=dedup_cols, keep="last")
    return nuevo_df


def _guardar(df: pd.DataFrame, path: Path) -> None:
    df.to_excel(path, index=False, sheet_name="Sheet1")
    log.info(f"Guardado {path.name} ({len(df)} filas)")


def archivar_descarga(raw_file: Path, today: date) -> Path:
    PROGRAMAS_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = PROGRAMAS_DIR / f"Programas postgrado {today.strftime('%d-%m-%y')}.xlsx"
    if archive_path.exists():
        stamp = datetime.now().strftime("%H%M%S")
        archive_path = PROGRAMAS_DIR / f"Programas postgrado {today.strftime('%d-%m-%y')}__{stamp}.xlsx"
    shutil.copy2(raw_file, archive_path)
    log.info(f"Archivado {archive_path.name}")
    return archive_path


_PROG_RE = re.compile(r"Programas postgrado (\d{2}-\d{2}-\d{2})(?:__\d{6})?\.xlsx")

def get_snapshot_anterior(today: date) -> Path | None:
    candidates = []
    for f in PROGRAMAS_DIR.glob("Programas postgrado *.xlsx"):
        m = _PROG_RE.match(f.name)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%d-%m-%y").date()
        except ValueError:
            continue
        if file_date < today:
            candidates.append((file_date, f))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


# ── Pipeline de posgrado ──────────────────────────────────────────────────────
def procesar(cat: pd.DataFrame, today: date) -> dict:
    log.info("── POSGRADO ──────────────────────────────────")
    vacio = {"nuevos": pd.DataFrame(), "inactivos": pd.DataFrame(), "modificados": pd.DataFrame()}

    # 1. Descargar (o reutilizar si ya existe el archivo de hoy)
    today_archive = PROGRAMAS_DIR / f"Programas postgrado {today.strftime('%d-%m-%y')}.xlsx"
    if today_archive.exists():
        log.info(f"[posgrado] Archivo de hoy ya archivado ({today_archive.name}). Saltando descarga.")
        raw_file = today_archive
        ya_archivado = True
    else:
        download_dir = TMP_DIR / "posgrado"
        download_dir.mkdir(parents=True, exist_ok=True)
        raw_file = descargar_snies(download_dir)
        ya_archivado = False

    # 2. Archivar el Excel crudo (solo si fue descargado ahora)
    if not ya_archivado:
        archivar_descarga(raw_file, today)

    # 3. Cargar snapshot de hoy
    df_hoy = load_snapshot(raw_file)
    log.info(f"[posgrado] Snapshot HOY: {len(df_hoy)} programas")

    # 4. Cargar snapshot anterior (el más reciente en Programas/ antes de hoy)
    anterior_path = get_snapshot_anterior(today)
    if anterior_path is None:
        log.warning("[posgrado] No hay snapshot anterior en Programas/. El de hoy quedará como línea base.")
        raw_file.unlink(missing_ok=True)
        return vacio

    try:
        df_ant = load_snapshot(anterior_path)
    except Exception as e:
        log.warning(f"[posgrado] Snapshot anterior no legible ({e}). Abortando comparación.")
        raw_file.unlink(missing_ok=True)
        return vacio

    log.info(f"[posgrado] Snapshot ANTERIOR: {anterior_path.name} ({len(df_ant)} programas)")

    # Validar que ambos snapshots sean razonables (posgrado activo ≈ 8-11k programas)
    # Si alguno supera 12k, probablemente descargó sin filtro de nivel académico
    UMBRAL = 12_000
    if len(df_hoy) > UMBRAL:
        log.error(
            f"[posgrado] Snapshot HOY tiene {len(df_hoy)} programas — demasiados para ser "
            "solo posgrado activo. Probable descarga sin filtros. Abortando comparación."
        )
        raw_file.unlink(missing_ok=True)
        return vacio
    if len(df_ant) > UMBRAL:
        log.error(
            f"[posgrado] Snapshot ANTERIOR ({anterior_path.name}) tiene {len(df_ant)} programas "
            "— parece un archivo sin filtrar. Abortando comparación. "
            "Considera eliminarlo manualmente de Programas/ si es inválido."
        )
        raw_file.unlink(missing_ok=True)
        return vacio

    # 5. Detectar novedades
    nuevos, inactivos, modificados = detectar_novedades(df_hoy, df_ant, today)
    log.info(
        f"[posgrado] Nuevos={len(nuevos)} | "
        f"Inactivos={len(inactivos)} | "
        f"Modificados={len(modificados)}"
    )

    # 6. Agregar división Uninorte
    nuevos = merge_division(nuevos, cat)
    inactivos = merge_division(inactivos, cat)
    modificados = merge_division(modificados, cat)

    # 7. Acumular y guardar en data/novedades/
    _guardar(
        acumular(NOVEDADES_DIR / "Nuevos_posgrado.xlsx", nuevos),
        NOVEDADES_DIR / "Nuevos_posgrado.xlsx",
    )
    _guardar(
        acumular(NOVEDADES_DIR / "Inactivos_posgrado.xlsx", inactivos),
        NOVEDADES_DIR / "Inactivos_posgrado.xlsx",
    )
    _guardar(
        acumular(NOVEDADES_DIR / "Modificados_posgrado.xlsx", modificados),
        NOVEDADES_DIR / "Modificados_posgrado.xlsx",
    )

    if not ya_archivado:
        raw_file.unlink(missing_ok=True)

    return {"nuevos": nuevos, "inactivos": inactivos, "modificados": modificados}


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    today = date.today()
    log.info(f"╔══ Run SNIES Posgrado — {today.isoformat()} ══╗")

    cat = load_categorizacion()
    resultados: dict = {"posgrado": None}

    try:
        resultados["posgrado"] = procesar(cat, today)
    except Exception:
        log.exception("Error fatal procesando posgrado.")

    chart_paths = []
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT))
        from analisis_historico_posgrado import generar_graficos
        chart_paths = generar_graficos()
    except Exception:
        log.exception("Error generando gráficos de novedades.")

    try:
        _sys.path.insert(0, str(ROOT / "scripts"))
        from send_report_posgrado import enviar_reporte
        enviar_reporte(resultados, today, chart_paths)
    except Exception:
        log.exception("Error enviando el correo.")

    log.info("╚══ Run finalizado. ══╝")


if __name__ == "__main__":
    main()
