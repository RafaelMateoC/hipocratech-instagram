# -*- coding: utf-8 -*-
"""Incrusta una pista de audio en los videos de los reels.

Instagram no deja adjuntar musica de su biblioteca por API: tiene que venir
dentro del archivo. Esto la mete, ajustada a la duracion de cada reel, con
entrada y salida suaves.

  python herramientas/poner_audio.py --generar            # crea un fondo sintetico
  python herramientas/poner_audio.py --pista audio/x.mp3  # usa tu pista
  python herramientas/poner_audio.py --pista audio/x.mp3 --solo 2026-08-27

El original de cada carpeta (REEL.mp4) no se toca nunca: la mezcla se escribe
en medios/, que es lo que se publica.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
PLAN = RAIZ / "plan.json"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# El 19 de septiembre pide silencio de forma explicita en su guion: «es el
# chiste del reel y necesita silencio». Ponerle musica lo arruina.
SIN_AUDIO = {"2026-09-19"}

# Cinco guiones marcan cuando entra o sale la musica, con el segundo exacto.
# Se respetan: es la diferencia entre poner audio y poner el audio que pedian.
#   fecha: (entra en el segundo, sale en el segundo o None = hasta el final)
TIEMPOS = {
    "2026-08-22": (0, 13),   # «corta en seco en el segundo 13»
    "2026-08-31": (2, None),  # «los primeros dos segundos en silencio»
    "2026-09-14": (7, None),  # «nada de musica los primeros 7 segundos»
    "2026-09-28": (0, 19),   # «corta en el segundo 19»
}

VOLUMEN = 0.8


def correr(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-1500:])


def generar_fondo(destino, segundos=40):
    """Sintetiza un pulso bajo y sostenido, sin melodia ni derechos de nadie.

    Es lo que pide el guion del 27 de agosto al pie de la letra: «sin musica
    con letra, un pulso bajo y sostenido».
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    filtro = (
        "[0:a]volume=0.55,tremolo=f=1.15:d=0.55[grave];"
        "[1:a]volume=0.10,tremolo=f=0.55:d=0.40[quinta];"
        "[grave][quinta]amix=inputs=2:normalize=0,"
        "lowpass=f=320,highpass=f=35,"
        # Sin normalizar queda en -39 dB: presente para Instagram, inaudible
        # para una persona. -20 LUFS lo deja como fondo real.
        "loudnorm=I=-20:TP=-2:LRA=7,"
        # loudnorm remuestrea a 96 kHz; Instagram espera 44.1.
        "aresample=44100,"
        "aformat=channel_layouts=stereo,"
        "afade=t=in:st=0:d=2[salida]"
    )
    correr([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=44100:duration={segundos}",
        "-f", "lavfi", "-i", f"sine=frequency=82.4:sample_rate=44100:duration={segundos}",
        "-filter_complex", filtro, "-map", "[salida]",
        "-c:a", "pcm_s16le", str(destino),
    ])


def mezclar(video, pista, destino, volumen=VOLUMEN, entra=0, sale=None):
    """Pone la pista sobre el video, recortada a su duracion, con fundidos.

    entra/sale permiten dejar tramos en silencio cuando el guion lo pide.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    dur = duracion(video)
    fin = min(sale, dur) if sale else dur
    largo = max(fin - entra, 0.5)
    desvanece = min(1.5, largo / 3)
    inicio_out = max(largo - desvanece, 0.1)

    partes = [
        f"[1:a]volume={volumen}",
        f"atrim=0:{largo:.2f}",
        "asetpts=N/SR/TB",
        f"afade=t=in:st=0:d={min(1.0, largo/3):.2f}",
        f"afade=t=out:st={inicio_out:.2f}:d={desvanece:.2f}",
    ]
    if entra > 0:
        # Silencio por delante en vez de arrancar la pista antes de tiempo.
        partes.append(f"adelay={int(entra*1000)}|{int(entra*1000)}")
    if fin < dur:
        partes.append(f"apad=whole_dur={dur:.2f}")
    filtro = ",".join(partes) + "[a]"
    correr([
        FFMPEG, "-y",
        "-i", str(video),
        "-stream_loop", "-1", "-i", str(pista),
        "-filter_complex", filtro,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-t", f"{dur:.2f}", "-movflags", "+faststart",
        str(destino),
    ])


def duracion(video):
    res = subprocess.run([FFMPEG, "-i", str(video)], capture_output=True,
                         text=True, errors="replace")
    for linea in res.stderr.splitlines():
        if "Duration:" in linea:
            h, m, s = linea.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"no pude leer la duracion de {video.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pista", help="archivo de audio a incrustar")
    ap.add_argument("--generar", action="store_true", help="sintetizar un fondo")
    ap.add_argument("--solo", help="una sola fecha, para probar")
    ap.add_argument("--volumen", type=float, default=VOLUMEN)
    args = ap.parse_args()

    if args.generar:
        pista = RAIZ / "audio" / "fondo-pulso.wav"
        print("Generando fondo sintetico…")
        generar_fondo(pista)
        print(f"  {pista}")
    elif args.pista:
        pista = Path(args.pista)
        if not pista.is_absolute():
            pista = RAIZ / pista
        if not pista.exists():
            print(f"No encuentro la pista: {pista}")
            return 1
    else:
        print("Dime --pista <archivo> o --generar.")
        return 1

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    hechos = saltados = 0
    for item in plan["publicaciones"]:
        if not item["listo"] or item["formato"] != "reel":
            continue
        if args.solo and item["fecha"] != args.solo:
            continue
        if item["fecha"] in SIN_AUDIO:
            print(f"  - {item['fecha']} · su guion pide silencio, lo dejo mudo")
            saltados += 1
            continue

        origen = CONTENIDO / item["carpeta"] / "REEL.mp4"
        destino = RAIZ / item["medios"][0]
        entra, sale = TIEMPOS.get(item["fecha"], (0, None))
        mezclar(origen, pista, destino, args.volumen, entra, sale)
        marca = ""
        if entra or sale:
            marca = f"  [musica de {entra}s a {sale or 'final'}s, por guion]"
        print(f"  ok {item['fecha']} · {item['tema'][:40]}{marca}")
        hechos += 1

    print(f"\n{hechos} reels con audio · {saltados} dejados en silencio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
