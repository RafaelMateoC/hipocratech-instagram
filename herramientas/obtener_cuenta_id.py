# -*- coding: utf-8 -*-
"""Averigua el ID de tu cuenta de Instagram a partir de tu token.

Funciona con los dos flujos de autenticacion:

  · Instagram Login  — el token empieza por "IG", responde en graph.instagram.com
  · Facebook Login   — el token empieza por "EAA", responde en graph.facebook.com

Uso, desde esta carpeta:

    python herramientas/obtener_cuenta_id.py

Te pide el token de forma oculta, asi que no queda en el historial del shell.
Tampoco se guarda en disco: se usa para las consultas y ya.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from publicador.api import HOST_INSTAGRAM, VERSION, host_para  # noqa: E402


def pedir(host, ruta, token, **params):
    params["access_token"] = token
    url = f"{host}/{VERSION}/{ruta}?{urllib.parse.urlencode(params)}"
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


def por_instagram_login(token):
    yo = pedir(HOST_INSTAGRAM, "me", token, fields="user_id,username")
    # En este flujo el id que sirve para publicar es user_id.
    return [(None, yo.get("username", "?"), str(yo.get("user_id") or yo.get("id")))]


def por_facebook_login(token):
    from publicador.api import HOST_FACEBOOK
    paginas = pedir(HOST_FACEBOOK, "me/accounts", token,
                    fields="id,name,instagram_business_account").get("data", [])
    if not paginas:
        raise SystemExit(
            "\nEl token no ve ninguna pagina de Facebook.\n"
            "La cuenta de Instagram tiene que estar vinculada a una pagina que "
            "tu administres, y el token necesita el permiso pages_read_engagement."
        )
    salida = []
    for p in paginas:
        ig = p.get("instagram_business_account")
        if not ig:
            print(f"  · '{p.get('name')}' — sin Instagram vinculado, la salto")
            continue
        try:
            usuario = pedir(HOST_FACEBOOK, ig["id"], token,
                            fields="username").get("username", "?")
        except SystemExit:
            usuario = "?"
        salida.append((p.get("name"), usuario, ig["id"]))
    return salida


def main():
    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        # Se pide oculto para que no quede en el historial del shell.
        import getpass
        token = getpass.getpass("Pega tu token (no se vera al escribir): ").strip()
    if not token:
        print("Sin token no puedo consultar nada.")
        return 1

    es_ig = host_para(token) == HOST_INSTAGRAM
    print(f"\nFlujo detectado: {'Instagram Login' if es_ig else 'Facebook Login'}")

    cuentas = por_instagram_login(token) if es_ig else por_facebook_login(token)

    if not cuentas:
        print("\nNinguna pagina tiene una cuenta de Instagram profesional vinculada.")
        return 1

    for pagina, usuario, cuenta_id in cuentas:
        print()
        if pagina:
            print(f"  Pagina    : {pagina}")
        print(f"  Instagram : @{usuario}")
        print(f"  IG_CUENTA_ID = {cuenta_id}")

    print("\nPega ese IG_CUENTA_ID como secret en el repositorio.")
    print("No lo pegues en un chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
