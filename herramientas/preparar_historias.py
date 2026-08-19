# -*- coding: utf-8 -*-
"""Arma el material que se comparte a historias cada vez que se publica.

Instagram no deja resubir una publicacion del feed a la historia con el sticker
que enlaza al post: eso solo existe dentro de la app. Lo que si permite la API
es publicar una historia nueva con el mismo material, que es lo que se hace.

  · dias de reel      -> la historia es el propio reel
  · el resto          -> un video corto con la primera lamina y el fondo de audio

El arte del feed es 1080x1350 y la historia es 1080x1920, asi que la lamina se
centra sobre un fondo del color de la propia pieza.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image
import imageio_ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
PLAN = RAIZ / "plan.json"
PISTA = RAIZ / "audio" / "fondo-pulso.wav"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ANCHO, ALTO = 1080, 1920
SEGUNDOS = 6


def color_de_fondo(im):
    """Toma el color de las esquinas: el arte es plano, asi que da el de marca."""
    esquinas = [(2, 2), (im.width - 3, 2), (2, im.height - 3), (im.width - 3, im.height - 3)]
    pixeles = [im.getpixel(p)[:3] for p in esquinas]
    # La esquina que mas se repite; ante el empate, la superior izquierda.
    return max(set(pixeles), key=pixeles.count)


def lienzo_historia(origen, destino):
    """Centra la pieza del feed en un lienzo vertical de historia."""
    with Image.open(origen) as im:
        im = im.convert("RGB")
        fondo = Image.new("RGB", (ANCHO, ALTO), color_de_fondo(im))
        escala = min(ANCHO / im.width, (ALTO * 0.78) / im.height)
        nuevo = im.resize((int(im.width * escala), int(im.height * escala)), Image.LANCZOS)
        fondo.paste(nuevo, ((ANCHO - nuevo.width) // 2, (ALTO - nuevo.height) // 2))
        destino.parent.mkdir(parents=True, exist_ok=True)
        fondo.save(destino, "JPEG", quality=90, optimize=True)


def video_desde_imagen(imagen, destino, pista):
    """Convierte la lamina en un video corto: sin video no hay audio en historia."""
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-t", str(SEGUNDOS), "-i", str(imagen),
    ]
    if pista.exists():
        cmd += ["-stream_loop", "-1", "-i", str(pista),
                "-filter_complex",
                f"[1:a]volume=0.8,atrim=0:{SEGUNDOS},asetpts=N/SR/TB,"
                f"afade=t=in:st=0:d=1,afade=t=out:st={SEGUNDOS-1.5}:d=1.5[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    cmd += [
        "-vf", f"scale={ANCHO}:{ALTO},fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-t", str(SEGUNDOS), "-movflags", "+faststart", str(destino),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-1200:])


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if not PISTA.exists():
        print("Aviso: no hay pista de audio; las historias saldran mudas.")

    n = 0
    for item in plan["publicaciones"]:
        if not item["listo"]:
            continue
        carpeta = CONTENIDO / item["carpeta"]
        destino = RAIZ / "medios" / item["carpeta"] / "historia.mp4"
        destino.parent.mkdir(parents=True, exist_ok=True)

        if item["formato"] == "reel":
            # La historia es el reel mismo: el publicador apunta directo a su
            # video en vez de guardar una copia identica al lado.
            print(f"  -- {item['fecha']} · el reel se comparte tal cual")
            continue
        else:
            if item["formato"] == "carrusel":
                origen = sorted(carpeta.glob("lamina-*.png"))[0]
            else:
                origen = next(iter(sorted(carpeta.glob("post*.png"))))
            lienzo = destino.parent / "historia-lienzo.jpg"
            lienzo_historia(origen, lienzo)
            video_desde_imagen(lienzo, destino, PISTA)
            lienzo.unlink(missing_ok=True)

        n += 1
        print(f"  ok {item['fecha']} · {item['formato']}", flush=True)

    print(f"\n{n} historias preparadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
