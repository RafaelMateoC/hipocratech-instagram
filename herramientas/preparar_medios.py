# -*- coding: utf-8 -*-
"""Convierte las artes al formato que exige la API y arma los videos de los reels.

Instagram solo acepta JPEG por image_url, asi que las PNG se convierten. Los reels
necesitan un MP4 real: se arma desde los frames del guion, con cortes secos y los
tiempos que el propio guion define.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image
import imageio_ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
MEDIOS = RAIZ / "medios"
PLAN = RAIZ / "plan.json"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

CALIDAD = 88
# Instagram rechaza el contenedor fuera de este rango de proporcion.
RATIO_MIN, RATIO_MAX = 0.8, 1.91


def a_jpeg(origen, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(origen) as im:
        ancho, alto = im.size
        if im.mode in ("RGBA", "LA", "P"):
            fondo = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            fondo.paste(im, mask=im.split()[-1])
            im = fondo
        else:
            im = im.convert("RGB")
        im.save(destino, "JPEG", quality=CALIDAD, optimize=True, progressive=True)
    return ancho, alto


def construir_video(carpeta, destino, total, fin_gancho, inicio_cierre):
    """Arma el MP4 vertical desde los frames, respetando los tiempos del guion."""
    frames = sorted(carpeta.glob("frame-*.png"))
    destino.parent.mkdir(parents=True, exist_ok=True)

    if fin_gancho is None or inicio_cierre is None or len(frames) != 3:
        # Sin tiempos utiles, se reparte parejo.
        duraciones = [total / len(frames)] * len(frames)
    else:
        duraciones = [
            fin_gancho,
            max(inicio_cierre - fin_gancho, 1),
            max(total - inicio_cierre, 1),
        ]

    lista = destino.parent / "_concat.txt"
    lineas = []
    for frame, dur in zip(frames, duraciones):
        lineas.append(f"file '{frame.as_posix()}'")
        lineas.append(f"duration {dur:.3f}")
    # El demuxer concat exige repetir el ultimo archivo sin duracion.
    lineas.append(f"file '{frames[-1].as_posix()}'")
    lista.write_text("\n".join(lineas), encoding="utf-8")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(lista),
        # Pista de audio silenciosa: sin ella hay reels que Instagram rechaza.
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total}",
        "-movflags", "+faststart",
        str(destino),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    lista.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg fallo en {carpeta.name}:\n{res.stderr[-1500:]}")
    return duraciones


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    avisos = []
    n_img = n_vid = 0

    for item in plan["publicaciones"]:
        if not item["listo"]:
            continue
        carpeta = CONTENIDO / item["carpeta"]

        if item["formato"] == "reel":
            destino = RAIZ / item["medios"][0]
            cortes = item.get("cortes", {})
            construir_video(
                carpeta, destino, item["duracion"],
                cortes.get("gancho"), cortes.get("cierre"),
            )
            n_vid += 1
            if item.get("portada"):
                origen = carpeta / "portada-reel.png"
                a_jpeg(origen, RAIZ / item["portada"])
                n_img += 1
        else:
            for rel in item["medios"]:
                nombre = Path(rel).stem
                origen = carpeta / f"{nombre}.png"
                ancho, alto = a_jpeg(origen, RAIZ / rel)
                ratio = ancho / alto
                if not RATIO_MIN <= ratio <= RATIO_MAX:
                    avisos.append(
                        f"{item['fecha']} {nombre}: proporcion {ratio:.3f} "
                        f"({ancho}x{alto}) fuera del rango que acepta Instagram"
                    )
                n_img += 1

        print(f"  ok {item['fecha']} · {item['formato']}", flush=True)

    print(f"\n{n_img} imagenes convertidas a JPEG · {n_vid} videos generados")
    for a in avisos:
        print(f"  AVISO · {a}")
    return 1 if avisos else 0


if __name__ == "__main__":
    sys.exit(main())
