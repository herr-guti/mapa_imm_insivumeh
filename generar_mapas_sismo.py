# Descripción
# El programa que toma una base de datos SQLite con los reportes de usuarios de la app
# 'INSIVUMEH Alerta temprana de terremotos' y crea dos mapas en formato html.
# ejemplos mínimos:
# python generar_mapas_sismo.py sismo_insi2025otmk.db
# python generar_mapas_sismo.py sismo_insi2025otmk.db --event-id insi2025otmk 
# python generar_mapas_sismo.py sismo_insi2025otmk.db --zoom 9 
# python generar_mapas_sismo.py sismo_insi2025otmk.db --output-prefix demo

import argparse
import sqlite3
from datetime import datetime
from typing import Tuple, Dict

import numpy as np
import pandas as pd
import folium
from folium.features import DivIcon

# ---------- Conexión a la base de datos ---------- #
def abrir_conexion(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def leer_evento(conn: sqlite3.Connection, event_id: str | None) -> Dict:
    cur = conn.cursor()
    if event_id is None:
        row = cur.execute(
            "SELECT eventid, origintime, latitude, longitude, magnitude FROM eventinfo LIMIT 1"
        ).fetchone()
    else:
        row = cur.execute(
            "SELECT eventid, origintime, latitude, longitude, magnitude "
            "FROM eventinfo WHERE eventid = ?",
            (event_id,),
        ).fetchone()
    if row is None:
        raise ValueError("No se encontró el evento solicitado en eventinfo.")
    return dict(row)

def leer_reportes(conn: sqlite3.Connection, event_id: str) -> pd.DataFrame:
    # Cargar datos de identificación del sismo
    q = """
        SELECT userid, lat, lon, intensity
        FROM intensityreports
        WHERE eventid = ? AND lat IS NOT NULL AND lon IS NOT NULL
    """
    return pd.read_sql_query(q, conn, params=(event_id,))

# ---------- Cálculos (distancias e IMM teórica) ---------- #
def calcular_distancias(df: pd.DataFrame, lat_sis: float, lon_sis: float) -> pd.Series:
    # Aproximación: 1° ~ 110 km (válida para distancias cortas)
    return np.sqrt((df["lat"] - lat_sis) ** 2 + (df["lon"] - lon_sis) ** 2) * 110.0

def imm_teorica_por_tramos(R_km: np.ndarray, M: float, imm_obs: np.ndarray) -> np.ndarray:
    # Evitar log(0)
    R_safe = np.where(R_km > 0, R_km, 1e-6)

    # Elegir recta según IMM observada a partir del umbral IMM_o = 4.22, el umbral es el 
    # dado por C. B. Worden, M. C. Gerstenberger, D. A. Rhoades, y D. J. Wald (2012)
    tramo1 = imm_obs <= 4.22
    # La función es la composición entre los modelos de Worden et al (2012) y el 
    # modelo de Ordaz, Jara y Singh descrito en Moncayo Theurer et al (2016) 
    val1 = 3.598 - 0.004805 * R_safe - 0.53 * np.log10(R_safe) + 0.295 * M
    val2 = 4.002 - 0.011470 * R_safe - 2.68 * np.log10(R_safe) + 0.940 * M

    imm_t = np.where(tramo1, val1, val2)
    imm_t = np.floor(imm_t)  # aplicar función piso 'floor' para obtener un entero
    imm_t = np.clip(imm_t, 1, None)  # IMM mínima 1
    return imm_t.astype(int)

# ---------- Construcción de los mapas ---------- #
# Colores utilizados para los niveles de la Intensidad de Mercalli modificada
# códigos dados por el departamento de sismología del INSIVUMEH
COLOR_MAP = {
    1: "#0000A6", 2: "#49FE03", 3: "#FFFF01", 4: "#FFC800", 5: "#FFDE01",
    6: "#FFBD01", 7: "#FF9C01", 8: "#FF7C01", 9: "#C73E10", 10: "#90001F"
}

# Intensidad de Mercalli modificada (IMM)
# según Worden et al (2012) es común recibir reportes hasta el 10
CAPA_INTENSIDAD = {
    1: "No sentido", 2: "Muy débil", 3: "Leve", 4: "Moderado", 5: "Poco fuerte",
    6: "Fuerte", 7: "Muy fuerte", 8: "Destructivo", 9: "Muy destructivo", 10: "Desastroso"
}

def color_por_intensidad(i: int) -> str:
    k = max(1, min(10, int(i)))
    return COLOR_MAP[k]

def construir_tiles(mapa: folium.Map) -> None:
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name="Sin lugares poblados",
        control=True
    ).add_to(mapa)
    folium.TileLayer(
        tiles="CartoDB positron",
        name="Lugares poblados",
        control=True
    ).add_to(mapa)

def cuadrado_marker(lat: float, lon: float, size: int, fill: str, tooltip: str) -> folium.Marker:
    return folium.Marker(
        location=[lat, lon],
        tooltip=tooltip,
        icon=DivIcon(
            icon_size=(size, size),
            icon_anchor=(size // 2, size // 2),
            html=f'<div style="width:{size}px;height:{size}px;background:{fill};opacity:0.75;"></div>'
        )
    )

def leyenda_evento_html(evento: Dict, titulo_colores: str, items_colores: list[Tuple[str, str]]) -> str:
    dt = datetime.fromisoformat(evento["origintime"].replace("Z", "+00:00"))
    fecha_str = dt.strftime("%Y-%m-%d")
    hora_str = dt.strftime("%H:%M:%S")

    colores_html = "\n".join(
        f'<div><span style="background:{c}; width:12px; height:12px; display:inline-block;"></span> {et}</div>'
        for c, et in items_colores
    )
    return f"""
<div style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: white; padding: 10px 12px;
            border: 1px solid #ccc; border-radius: 6px; font-size: 14px; max-width: 320px;">
  <h2 style="margin: 0 0 6px 0; font-size: 18px;">Leyenda</h2>

  <div style="display:flex; align-items:center; margin: 6px 0 8px 0;">
    <span style="display:inline-block; width:16px; height:16px; border-radius:50%;
                 background:#00008B; margin-right:6px;"></span>
    <span><b>Epicentro</b></span>
  </div>

  <div style="margin-left:22px; font-size: 13px;">
    <div><b>Evento:</b> {evento['eventid']}</div>
    <div><b>Fecha:</b> {fecha_str}</div>
    <div><b>Hora (UTC):</b> {hora_str}</div>
    <div><b>Latitud:</b> {evento['latitude']:.6f}</div>
    <div><b>Longitud:</b> {evento['longitude']:.6f}</div>
    <div><b>Magnitud:</b> {evento['magnitude']:.2f}</div>
  </div>

  <hr style="margin:10px 0;">
  <h4 style="margin: 0 0 6px 0;">{titulo_colores}</h4>
  {colores_html}
</div>
"""

def mapa_intensidades(df: pd.DataFrame, evento: Dict, zoom: int) -> folium.Map:
    lat_sis, lon_sis = float(evento["latitude"]), float(evento["longitude"])
    m = folium.Map(location=[lat_sis, lon_sis], zoom_start=zoom, tiles=None, control_scale=True)
    construir_tiles(m)

    # Epicentro
    folium.CircleMarker(
        location=[lat_sis, lon_sis],
        radius=10,
        color="darkblue",
        fill=True,
        fill_color="darkblue",
        fill_opacity=0.9,
        tooltip=f"Evento: {evento['eventid']} | M={evento['magnitude']:.2f}"
    ).add_to(m)

    # Capas por intensidad
    capas = {k: folium.FeatureGroup(name=v, show=True) for k, v in CAPA_INTENSIDAD.items()}
    for r in df.itertuples(index=False):
        k = max(1, min(10, int(r.intensity)))
        size = int(2 * (3 + max(0, min(5, int(r.intensity) - 3))))
        cuadrado_marker(
            lat=r.lat,
            lon=r.lon,
            size=size,
            fill=color_por_intensidad(k),
            tooltip=f"R = {r.R_km:.1f} km | IMM_o = {int(r.intensity)}"
        ).add_to(capas[k])

    for fg in capas.values():
        fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    items = [(COLOR_MAP[k], CAPA_INTENSIDAD[k]) for k in range(1, 11)]
    legend_html = leyenda_evento_html(evento, "Intensidad reportada", items)
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

def mapa_diferencias(df: pd.DataFrame, evento: Dict, zoom: int) -> folium.Map:
    lat_sis, lon_sis = float(evento["latitude"]), float(evento["longitude"])
    m = folium.Map(location=[lat_sis, lon_sis], zoom_start=zoom, tiles=None, control_scale=True)
    construir_tiles(m)

    # Epicentro
    folium.CircleMarker(
        location=[lat_sis, lon_sis],
        radius=10,
        color="darkblue",
        fill=True,
        fill_color="darkblue",
        fill_opacity=0.9,
        tooltip=f"Evento: {evento['eventid']} | M={evento['magnitude']:.2f}"
    ).add_to(m)

    # Capas por diferencia
    capas_diff = {
        "dif = 0": folium.FeatureGroup(name="diferencia = 0", show=True),
        "dif = 1": folium.FeatureGroup(name="diferencia = 1", show=True),
        "dif ≥ 2": folium.FeatureGroup(name="diferencia ≥ 2", show=True),
    }

    def color_por_diferencia(d: int) -> str:
        # Propuesta de un semáforo común
        if d == 0:
            return "#00A600"  # verde
        elif d == 1:
            return "#FF9A00"  # naranja
        else:
            return "#C00000"  # rojo

    for r in df.itertuples(index=False):
        d = int(r.Diferencia) if r.Diferencia is not None else 0
        capa = "dif = 0" if d == 0 else ("dif = 1" if d == 1 else "dif ≥ 2")
        size = int(2 * (3 + max(0, min(5, int(r.intensity) - 3))))
        cuadrado_marker(
            lat=r.lat,
            lon=r.lon,
            size=size,
            fill=color_por_diferencia(d),
            tooltip=f"IMM_o = {int(r.intensity)} | IMM_t = {int(r.IMM_t)} | dif = {d}"
        ).add_to(capas_diff[capa])

    for fg in capas_diff.values():
        fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    items = [
        ("#00A600", "diferencia = 0"),
        ("#FF9A00", "diferencia = 1"),
        ("#C00000", "diferencia ≥ 2"),
    ]
    legend_html = leyenda_evento_html(evento, "Nivel de diferencia", items)
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

# ---------- Llamada en la terminal ---------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera dos mapas HTML (intensidades y diferencias) a partir de una base SQLite INSIVUMEH."
    )
    parser.add_argument("db", help="Ruta al archivo .db (sqlite).")
    parser.add_argument("--event-id", help="eventid específico (por defecto: primero en eventinfo).", default=None)
    parser.add_argument("--zoom", help="Nivel de zoom inicial del mapa.", type=int, default=9)
    parser.add_argument("--output-prefix", help="Prefijo de nombre de archivos de salida.", default="")
    args = parser.parse_args()

    conn = abrir_conexion(args.db)
    try:
        evento = leer_evento(conn, args.event_id)
        df = leer_reportes(conn, evento["eventid"])
        if df.empty:
            raise ValueError("No hay reportes de intensidad con lat/lon para este evento.")

        # Cálculos
        df["R_km"] = calcular_distancias(df, float(evento["latitude"]), float(evento["longitude"]))
        imm_t = imm_teorica_por_tramos(df["R_km"].to_numpy(), float(evento["magnitude"]), df["intensity"].to_numpy())
        df["IMM_t"] = imm_t
        # Diferencia absoluta; entera para categorías (0,1,≥2) y conservamos valor para tooltip
        df["Diferencia"] = np.abs(df["intensity"] - df["IMM_t"]).astype(int)

        # Mapas
        m_int = mapa_intensidades(df, evento, args.zoom)
        m_dif = mapa_diferencias(df, evento, args.zoom)

        # Salida
        prefix = (args.output_prefix + "_") if args.output_prefix else ""
        out1 = f"{prefix}mapa_{evento['eventid']}.html"
        out2 = f"{prefix}mapa_diferencia_{evento['eventid']}.html"
        m_int.save(out1)
        m_dif.save(out2)

        # Mensaje de cierre
        print(f"Archivos generados:\n- {out1}\n- {out2}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()