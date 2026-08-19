# -*- coding: utf-8 -*-
"""Averigua el ID de tu cuenta de Instagram a partir de tu token.

Uso, desde tu maquina:

    python herramientas/obtener_cuenta_id.py

Te pide el token de forma oculta, asi que no queda en el historial del shell.
Tampoco se guarda en disco: se usa para las consultas y ya.
Pega el ID que imprima como secret IG_CUENTA_ID en GitHub.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

VERSION = "v25.0"


def pedir(ruta, token, **params):
    params["access_token"] = token
    url = f"https://graph.facebook.com/{VERSION}/{ruta}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def main():
    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        # Se pide oculto para que no quede en el historial del shell.
        import getpass
        token = getpass.getpass("Pega tu token (no se vera al escribir): ").strip()
    if not token:
        print("Sin token no puedo consultar nada.")
        return 1

    try:
        paginas = pedir("me/accounts", token, fields="id,name,instagram_business_account").get("data", [])
    except Exception as e:
        print(f"No pude consultar tus paginas: {e}")
        print("Revisa que el token tenga los permisos instagram_basic y pages_read_engagement.")
        return 1

    if not paginas:
        print("El token no ve ninguna pagina de Facebook.")
        print("La cuenta de Instagram tiene que estar vinculada a una pagina.")
        return 1

    encontrados = 0
    for p in paginas:
        ig = p.get("instagram_business_account")
        if not ig:
            print(f"  pagina '{p.get('name')}' · sin cuenta de Instagram vinculada")
            continue
        encontrados += 1
        try:
            datos = pedir(ig["id"], token, fields="username,followers_count")
            usuario = datos.get("username", "?")
        except Exception:
            usuario = "?"
        print()
        print(f"  Pagina    : {p.get('name')}")
        print(f"  Instagram : @{usuario}")
        print(f"  IG_CUENTA_ID = {ig['id']}")

    if not encontrados:
        print("\nNinguna de tus paginas tiene una cuenta de Instagram profesional vinculada.")
        return 1

    print("\nPega ese IG_CUENTA_ID como secret en el repositorio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
