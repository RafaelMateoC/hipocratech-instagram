# -*- coding: utf-8 -*-
"""Avisa cuando el token esta por caducar.

El token largo de Meta dura 60 dias y el bloque de publicaciones dura 104. Si
caduca a mitad de campana, las publicaciones dejan de salir en silencio. Esto
lo dice a tiempo. Solo corre si estan configurados IG_APP_ID e IG_APP_SECRET.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

AVISO_DIAS = 14


def main():
    token = os.environ.get("IG_TOKEN", "").strip()
    app_id = os.environ.get("IG_APP_ID", "").strip()
    secreto = os.environ.get("IG_APP_SECRET", "").strip()

    if not token:
        print("Sin IG_TOKEN: nada que revisar.")
        return 0
    if not (app_id and secreto):
        print("Sin IG_APP_ID/IG_APP_SECRET: no puedo revisar la vigencia del token.")
        print("Configuralos como secrets si quieres el aviso de caducidad.")
        return 0

    params = urllib.parse.urlencode({
        "input_token": token,
        "access_token": f"{app_id}|{secreto}",
    })
    url = f"https://graph.facebook.com/debug_token?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            datos = json.loads(r.read())["data"]
    except Exception as e:
        print(f"No pude consultar la vigencia: {e}")
        return 0

    if not datos.get("is_valid"):
        print("TOKEN INVALIDO. Las publicaciones van a fallar hasta que lo renueves.")
        return 1

    caduca = datos.get("expires_at", 0)
    if not caduca:
        print("Token sin fecha de caducidad (System User). Nada que renovar.")
        return 0

    faltan = (datetime.fromtimestamp(caduca, timezone.utc) - datetime.now(timezone.utc)).days
    fecha = datetime.fromtimestamp(caduca, timezone.utc).strftime("%d/%m/%Y")
    if faltan <= AVISO_DIAS:
        print(f"AVISO: el token caduca el {fecha} (faltan {faltan} dias). Renuevalo ya.")
    else:
        print(f"Token vigente hasta el {fecha} ({faltan} dias).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
