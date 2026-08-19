# -*- coding: utf-8 -*-
"""Convierte un token corto en un token de pagina que no caduca nunca.

Evita el usuario del sistema (y su rol de desarrollador) por completo:

  1. cambia tu token corto por uno largo de usuario (60 dias)
  2. pide con el los tokens de tus paginas

El token de pagina derivado de un token largo de usuario NO tiene fecha de
caducidad. Ese es el que sirve para publicar los 104 dias sin mantenimiento.

Uso, desde esta carpeta:

    IG_APP_ID=... IG_APP_SECRET=... IG_TOKEN_CORTO=... python herramientas/obtener_token_permanente.py

El token corto lo sacas del Explorador de la API de Graph. Nada se guarda en
disco: el resultado se imprime y tu decides donde pegarlo.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION = "v25.0"


def pedir(host, ruta, **params):
    url = f"https://{host}/{ruta}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(cuerpo)["error"]
            raise SystemExit(f"\nMeta respondio: {err.get('message')} "
                             f"(codigo {err.get('code')})")
        except (KeyError, json.JSONDecodeError):
            raise SystemExit(f"\nMeta respondio: {cuerpo[:400]}")


def main():
    app_id = os.environ.get("IG_APP_ID", "").strip()
    secreto = os.environ.get("IG_APP_SECRET", "").strip()
    corto = os.environ.get("IG_TOKEN_CORTO", "").strip()

    if not (app_id and secreto and corto):
        print(__doc__)
        return 1

    print("1/3 · cambiando el token corto por uno largo…")
    largo = pedir(
        "graph.facebook.com", f"{VERSION}/oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=app_id,
        client_secret=secreto,
        fb_exchange_token=corto,
    )["access_token"]
    print("      listo")

    print("2/3 · pidiendo los tokens de pagina…")
    paginas = pedir(
        "graph.facebook.com", f"{VERSION}/me/accounts",
        fields="id,name,access_token,instagram_business_account",
        access_token=largo,
    ).get("data", [])

    if not paginas:
        print("\nEl token no ve ninguna pagina. La cuenta de Instagram tiene que")
        print("estar vinculada a una pagina de Facebook que tu administres.")
        return 1

    print("3/3 · comprobando que no caduquen…\n")
    encontrados = 0
    for p in paginas:
        ig = p.get("instagram_business_account")
        if not ig:
            print(f"  · '{p.get('name')}' — sin Instagram vinculado, la salto")
            continue

        token_pagina = p["access_token"]
        info = pedir("graph.facebook.com", "debug_token",
                     input_token=token_pagina,
                     access_token=f"{app_id}|{secreto}")["data"]
        caduca = info.get("expires_at", 0)

        try:
            usuario = pedir("graph.facebook.com", f"{VERSION}/{ig['id']}",
                            fields="username", access_token=token_pagina).get("username", "?")
        except SystemExit:
            usuario = "?"

        encontrados += 1
        print("=" * 70)
        print(f"  Pagina    : {p.get('name')}")
        print(f"  Instagram : @{usuario}")
        print()
        print(f"  IG_CUENTA_ID = {ig['id']}")
        print()
        print("  IG_TOKEN =")
        print(f"  {token_pagina}")
        print()
        if caduca == 0:
            print("  ✓ Este token NO caduca. Es el que quieres.")
        else:
            fecha = datetime.fromtimestamp(caduca, timezone.utc).strftime("%d/%m/%Y")
            print(f"  ⚠ Este token caduca el {fecha}. Revisa que el paso 1 haya")
            print("    devuelto un token largo antes de pedir los de pagina.")
        print("=" * 70)

    if not encontrados:
        print("\nNinguna pagina tiene una cuenta de Instagram profesional vinculada.")
        return 1

    print("\nPega esos dos valores como secrets en el repositorio.")
    print("No los pegues en un chat ni los subas al repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
