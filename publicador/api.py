# -*- coding: utf-8 -*-
"""Cliente minimo de la API de publicacion de contenido de Instagram.

Publicar es siempre en dos tiempos: se crea un contenedor con el medio y luego
se publica ese contenedor. Los reels ademas hay que esperarlos, porque Meta
procesa el video de forma asincrona.
"""
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "v25.0"

# Hay dos flujos de autenticacion y cada uno vive en su host. Los tokens de
# Instagram Login empiezan por "IG" y solo responden en graph.instagram.com;
# los de Facebook Login empiezan por "EAA" y van a graph.facebook.com.
HOST_INSTAGRAM = "https://graph.instagram.com"
HOST_FACEBOOK = "https://graph.facebook.com"


def host_para(token):
    return HOST_INSTAGRAM if token.startswith("IG") else HOST_FACEBOOK


class ErrorInstagram(RuntimeError):
    pass


class Instagram:
    def __init__(self, cuenta_id, token, version=VERSION, reintentos=3):
        self.cuenta_id = cuenta_id
        self.token = token
        self.version = version
        self.reintentos = reintentos
        self.base = host_para(token)

    @property
    def flujo(self):
        return "Instagram Login" if self.base == HOST_INSTAGRAM else "Facebook Login"

    # -- transporte ---------------------------------------------------------

    def _pedir(self, metodo, ruta, **params):
        url = f"{self.base}/{self.version}/{ruta}"
        params["access_token"] = self.token
        datos = urllib.parse.urlencode(params).encode()

        ultimo = None
        for intento in range(1, self.reintentos + 1):
            try:
                if metodo == "POST":
                    req = urllib.request.Request(url, data=datos, method="POST")
                else:
                    req = urllib.request.Request(f"{url}?{datos.decode()}", method="GET")
                with urllib.request.urlopen(req, timeout=120) as r:
                    import json
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                import json
                cuerpo = e.read().decode("utf-8", "replace")
                try:
                    err = json.loads(cuerpo)["error"]
                    mensaje = f"{err.get('message')} (codigo {err.get('code')}"
                    if err.get("error_subcode"):
                        mensaje += f"/{err['error_subcode']}"
                    mensaje += ")"
                except Exception:
                    mensaje = cuerpo[:500]
                # 4xx de validacion no se reintenta: el error no se va a curar solo.
                if e.code < 500 and e.code != 429:
                    raise ErrorInstagram(mensaje) from None
                ultimo = ErrorInstagram(mensaje)
            except urllib.error.URLError as e:
                ultimo = ErrorInstagram(f"fallo de red: {e.reason}")

            if intento < self.reintentos:
                time.sleep(5 * intento)
        raise ultimo

    # -- contenedores -------------------------------------------------------

    def contenedor_imagen(self, image_url, caption=None, alt_text=None, hijo=False):
        p = {"image_url": image_url}
        if hijo:
            p["is_carousel_item"] = "true"
        if caption:
            p["caption"] = caption
        # alt_text solo lo acepta Instagram en publicaciones de imagen.
        if alt_text:
            p["alt_text"] = alt_text
        return self._pedir("POST", f"{self.cuenta_id}/media", **p)["id"]

    def contenedor_carrusel(self, hijos, caption=None):
        p = {"media_type": "CAROUSEL", "children": ",".join(hijos)}
        if caption:
            p["caption"] = caption
        return self._pedir("POST", f"{self.cuenta_id}/media", **p)["id"]

    def contenedor_reel(self, video_url, caption=None, cover_url=None):
        p = {"media_type": "REELS", "video_url": video_url}
        if caption:
            p["caption"] = caption
        if cover_url:
            p["cover_url"] = cover_url
        return self._pedir("POST", f"{self.cuenta_id}/media", **p)["id"]

    def contenedor_historia(self, video_url=None, image_url=None):
        """Historia nueva con el mismo material.

        Ojo: la API no puede resubir una publicacion del feed a la historia con
        el sticker que enlaza al post. Eso solo existe dentro de la app.
        """
        p = {"media_type": "STORIES"}
        if video_url:
            p["video_url"] = video_url
        else:
            p["image_url"] = image_url
        return self._pedir("POST", f"{self.cuenta_id}/media", **p)["id"]

    # -- publicacion --------------------------------------------------------

    def estado(self, contenedor):
        r = self._pedir("GET", contenedor, fields="status_code,status")
        return r.get("status_code"), r.get("status")

    def esperar(self, contenedor, limite=600, intervalo=15, log=print):
        """Espera a que Meta termine de procesar el medio."""
        agotado = time.monotonic() + limite
        while time.monotonic() < agotado:
            codigo, detalle = self.estado(contenedor)
            if codigo == "FINISHED":
                return
            if codigo in ("ERROR", "EXPIRED"):
                raise ErrorInstagram(f"el contenedor quedo en {codigo}: {detalle}")
            log(f"    procesando… ({codigo})")
            time.sleep(intervalo)
        raise ErrorInstagram(f"el contenedor sigue sin procesarse tras {limite}s")

    def publicar(self, contenedor):
        return self._pedir("POST", f"{self.cuenta_id}/media_publish",
                           creation_id=contenedor)["id"]

    def permalink(self, media_id):
        try:
            return self._pedir("GET", media_id, fields="permalink").get("permalink")
        except ErrorInstagram:
            return None

    def limite(self):
        r = self._pedir("GET", f"{self.cuenta_id}/content_publishing_limit",
                        fields="quota_usage,config")
        d = (r.get("data") or [{}])[0]
        return d.get("quota_usage"), (d.get("config") or {}).get("quota_total")
