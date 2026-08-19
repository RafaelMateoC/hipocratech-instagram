# -*- coding: utf-8 -*-
"""Publica en Instagram la pieza que toca hoy segun el plan.

Se ejecuta una vez al dia. Busca la fecha de hoy en plan.json, verifica que no
se haya publicado ya, sube el medio y deja constancia en estado.json.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from publicador.api import ErrorInstagram, Instagram  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PLAN = RAIZ / "plan.json"
ESTADO = RAIZ / "estado.json"

ZONA = "America/Santo_Domingo"


def hoy():
    if os.environ.get("FECHA"):
        return os.environ["FECHA"]
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(ZONA)).strftime("%Y-%m-%d")
    except Exception:
        # RD no cambia de hora: UTC-4 todo el ano.
        from datetime import timedelta, timezone
        return datetime.now(timezone(timedelta(hours=-4))).strftime("%Y-%m-%d")


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {}


def guardar_estado(estado):
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def url_de(base, relativo):
    return f"{base.rstrip('/')}/{relativo.lstrip('/')}"


def alcanzable(url):
    """Instagram descarga el medio por su cuenta: si el no lo alcanza, falla."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200, r.headers.get("Content-Type", "")
    except Exception as e:
        return False, str(e)


def verificar_medios(urls):
    """Separa lo que impide publicar de lo que solo conviene mirar."""
    problemas, avisos = [], []
    for u in urls:
        ok, detalle = alcanzable(u)
        if not ok:
            problemas.append(f"{u} -> no accesible ({detalle})")
        elif u.endswith(".jpg") and "image" not in detalle:
            problemas.append(f"{u} -> se sirve como '{detalle}', Instagram espera una imagen")
        elif u.endswith(".mp4") and "video" not in detalle:
            # raw.githubusercontent sirve los mp4 como octet-stream. A veces pasa,
            # pero es la causa tipica de un reel que se queda en ERROR. Con
            # GitHub Pages el tipo llega correcto.
            avisos.append(
                f"{u} -> se sirve como '{detalle}' en vez de 'video/mp4'. "
                f"Si el reel falla al procesarse, es por aqui."
            )
    return problemas, avisos


def publicar_item(ig, item, base, simular):
    caption = item["caption"]
    urls = [url_de(base, m) for m in item["medios"]]
    portada = url_de(base, item["portada"]) if item.get("portada") else None

    print(f"  medios: {len(urls)}")
    problemas, avisos = verificar_medios(urls + ([portada] if portada else []))
    if problemas:
        sangria = chr(10) + '    '
        raise ErrorInstagram('los medios no estan servibles:' + sangria
                             + sangria.join(problemas))
    for a in avisos:
        print(f"  AVISO · {a}")
    print("  medios verificados y accesibles")

    if simular:
        print("  SIMULACION · no se llama a la API")
        print(f"  formato   : {item['formato']}")
        print(f"  caption   : {len(caption)} caracteres")
        print(f"  alt text  : {'si' if item.get('alt_text') else 'no'}")
        for u in urls:
            print(f"    - {u}")
        if portada:
            print(f"    portada: {portada}")
        return None, None

    if item["formato"] == "carrusel":
        hijos = []
        for i, u in enumerate(urls, 1):
            # El alt text del carrusel va en la primera lamina.
            alt = item.get("alt_text") if i == 1 else None
            hijos.append(ig.contenedor_imagen(u, alt_text=alt, hijo=True))
            print(f"    lamina {i}/{len(urls)} lista")
        for h in hijos:
            ig.esperar(h, limite=180, intervalo=5, log=lambda m: None)
        contenedor = ig.contenedor_carrusel(hijos, caption=caption)
    elif item["formato"] == "reel":
        contenedor = ig.contenedor_reel(urls[0], caption=caption, cover_url=portada)
    else:
        contenedor = ig.contenedor_imagen(urls[0], caption=caption,
                                          alt_text=item.get("alt_text"))

    print(f"  contenedor {contenedor}")
    ig.esperar(contenedor, log=lambda m: print(m, flush=True))
    media_id = ig.publicar(contenedor)
    return media_id, ig.permalink(media_id)


def main():
    fecha = hoy()
    simular = os.environ.get("SIMULAR") == "1"
    base = os.environ.get("URL_MEDIOS", "").strip()
    cuenta = os.environ.get("IG_CUENTA_ID", "").strip()
    token = os.environ.get("IG_TOKEN", "").strip()

    print(f"=== {fecha} · Hipocratech Instagram ===")
    if simular:
        print("MODO SIMULACION")

    if not base:
        print("ERROR: falta URL_MEDIOS")
        return 1
    if not simular and not (cuenta and token):
        print("ERROR: faltan IG_CUENTA_ID o IG_TOKEN")
        return 1

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    item = next((p for p in plan["publicaciones"] if p["fecha"] == fecha), None)

    if item is None:
        print(f"No hay nada agendado para {fecha}. El bloque va del "
              f"{plan['publicaciones'][0]['fecha']} al {plan['publicaciones'][-1]['fecha']}.")
        return 0

    print(f"Tema    : {item['tema']}")
    print(f"Formato : {item['formato']}")

    if not item["listo"]:
        print(f"\nNO PUBLICADO · {item['motivo']}")
        print("La agenda contempla este dia pero el material no esta producido.")
        return 78  # sin material: ni exito ni fallo tecnico

    estado = cargar_estado()
    if fecha in estado and estado[fecha].get("media_id"):
        print(f"\nYa se publico el {estado[fecha]['publicado_en']} "
              f"(media {estado[fecha]['media_id']}). No se repite.")
        return 0

    ig = Instagram(cuenta, token) if not simular else None
    if ig:
        print(f"Acceso  : {ig.flujo} ({ig.base})")
        try:
            usado, total = ig.limite()
            print(f"Cuota   : {usado}/{total} publicaciones en 24h")
        except ErrorInstagram as e:
            print(f"Aviso: no pude leer la cuota ({e})")

    try:
        media_id, permalink = publicar_item(ig, item, base, simular)
    except ErrorInstagram as e:
        print(f"\nFALLO · {e}")
        return 1

    if simular:
        print("\nSimulacion completa. No se publico nada.")
        return 0

    estado[fecha] = {
        "tema": item["tema"],
        "formato": item["formato"],
        "media_id": media_id,
        "permalink": permalink,
        "publicado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    guardar_estado(estado)

    print(f"\nPUBLICADO · media {media_id}")
    if permalink:
        print(f"  {permalink}")
    print("\nRecordatorio del protocolo:")
    print("  · primeros 15 min: compartir a stories con encuesta o pregunta")
    print("  · primeros 60 min: responder todos los comentarios con una pregunta")
    print("  · primeras 2 horas: enviar por DM a 5-10 contactos del sector")
    return 0


if __name__ == "__main__":
    sys.exit(main())
