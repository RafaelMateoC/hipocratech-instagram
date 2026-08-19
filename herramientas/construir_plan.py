# -*- coding: utf-8 -*-
"""Construye plan.json a partir de la agenda (xlsx) y las carpetas de contenido.

El xlsx manda: define los 104 dias del bloque. Las carpetas aportan el caption,
el texto alternativo y las artes. Un dia sin carpeta queda como no publicable,
con el motivo escrito, para que el reporte diario lo diga en voz alta.
"""
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
AGENDA = next(RAIZ.glob("*Agenda Instagram*.xlsx"), None)
SALIDA = RAIZ / "plan.json"

RE_CAPTION = re.compile(
    r"CAPTION\s*·\s*copiar desde la siguiente linea\s*\n-+\n(.*?)\n-+\nFIN DEL CAPTION",
    re.S,
)
RE_ALT = re.compile(
    r"TEXTO ALTERNATIVO[^\n]*:\s*\n(.*?)(?:\n\s*\n|\Z)",
    re.S,
)
RE_DURACION = re.compile(r"^GUION\s*·\s*(\d+)\s*segundos", re.M)
RE_BLOQUE = re.compile(r"^(\d+):(\d{2})-(\d+):(\d{2})", re.M)


def sin_tildes(txt):
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )


def leer_caption(carpeta):
    """Extrae caption y texto alternativo de caption.txt."""
    ruta = carpeta / "caption.txt"
    texto = ruta.read_text(encoding="utf-8")

    m = RE_CAPTION.search(texto)
    if not m:
        raise ValueError(f"{ruta.name}: no encuentro el bloque CAPTION")
    caption = m.group(1).strip()

    alt = None
    m = RE_ALT.search(texto)
    if m:
        alt = " ".join(l.strip() for l in m.group(1).strip().splitlines() if l.strip())

    return caption, alt


def leer_guion(carpeta):
    """Devuelve (duracion_total, corte_gancho, corte_cierre) en segundos.

    Los tiempos salen del guion real: el gancho dura lo que dura su primer
    bloque, el cierre lo que dura el ultimo, y el nudo ocupa todo el medio.
    """
    texto = (carpeta / "caption.txt").read_text(encoding="utf-8")

    m = RE_DURACION.search(texto)
    duracion = int(m.group(1)) if m else None

    bloques = [
        (int(a) * 60 + int(b), int(c) * 60 + int(d))
        for a, b, c, d in RE_BLOQUE.findall(texto)
    ]
    if not bloques:
        return duracion or 15, None, None

    total = duracion or bloques[-1][1]
    fin_gancho = bloques[0][1]
    inicio_cierre = bloques[-1][0] if len(bloques) > 1 else total
    return total, fin_gancho, inicio_cierre


def formato_normalizado(txt):
    t = sin_tildes(str(txt)).lower()
    if "reel" in t:
        return "reel"
    if "carrusel" in t:
        return "carrusel"
    return "imagen"


def main():
    if AGENDA is None:
        raise SystemExit("No encuentro el xlsx de la agenda en la raiz del proyecto.")

    import openpyxl

    wb = openpyxl.load_workbook(AGENDA, data_only=True)
    hoja = next(h for h in wb.worksheets if sin_tildes(h.title).lower().startswith("calendario"))

    carpetas = {c.name[:10]: c for c in CONTENIDO.iterdir() if c.is_dir()}

    publicaciones = []
    for fila in hoja.iter_rows(min_row=5, values_only=True):
        if not fila[2]:
            continue
        fecha = fila[2].strftime("%Y-%m-%d")
        formato = formato_normalizado(fila[5])

        item = {
            "fecha": fecha,
            "dia": fila[3],
            "formato": formato,
            "pilar": fila[4],
            "senal": fila[6],
            "tema": fila[7],
            "carpeta": None,
            "caption": None,
            "alt_text": None,
            "medios": [],
            "portada": None,
            "listo": False,
            "motivo": None,
        }

        carpeta = carpetas.get(fecha)
        if carpeta is None:
            item["motivo"] = "sin arte producida"
            publicaciones.append(item)
            continue

        item["carpeta"] = carpeta.name
        item["caption"], item["alt_text"] = leer_caption(carpeta)

        base = f"medios/{carpeta.name}"
        if formato == "carrusel":
            laminas = sorted(carpeta.glob("lamina-*.png"))
            if not 2 <= len(laminas) <= 10:
                item["motivo"] = f"un carrusel necesita entre 2 y 10 laminas, hay {len(laminas)}"
            else:
                item["medios"] = [f"{base}/{l.stem}.jpg" for l in laminas]
                item["listo"] = True
        elif formato == "reel":
            frames = sorted(carpeta.glob("frame-*.png"))
            if len(frames) < 2:
                item["motivo"] = f"un reel necesita al menos 2 frames, hay {len(frames)}"
            else:
                total, gancho, cierre = leer_guion(carpeta)
                item["medios"] = [f"{base}/video.mp4"]
                item["duracion"] = total
                item["cortes"] = {"gancho": gancho, "cierre": cierre}
                if (carpeta / "portada-reel.png").exists():
                    item["portada"] = f"{base}/portada-reel.jpg"
                item["listo"] = True
        else:
            unica = next(iter(sorted(carpeta.glob("post*.png"))), None)
            if unica is None:
                item["motivo"] = "no encuentro post.png"
            else:
                item["medios"] = [f"{base}/{unica.stem}.jpg"]
                item["listo"] = True

        publicaciones.append(item)

    plan = {
        "zona": "America/Santo_Domingo",
        "hora": "19:00",
        "total": len(publicaciones),
        "listas": sum(1 for p in publicaciones if p["listo"]),
        "publicaciones": publicaciones,
    }
    SALIDA.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"plan.json escrito · {plan['total']} dias · {plan['listas']} publicables")
    faltan = {}
    for p in publicaciones:
        if not p["listo"]:
            faltan[p["motivo"]] = faltan.get(p["motivo"], 0) + 1
    for motivo, n in sorted(faltan.items(), key=lambda x: -x[1]):
        print(f"  {n:3d} sin publicar · {motivo}")


if __name__ == "__main__":
    main()
