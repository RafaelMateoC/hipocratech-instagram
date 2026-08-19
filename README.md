# Hipocratech · Publicador automático de Instagram

Publica una pieza al día, sola, a las **7:00 PM hora de República Dominicana**,
siguiendo la agenda del 19 de agosto al 30 de noviembre de 2026.

---

## Estado real del material

| | |
|---|---|
| Días en la agenda | **104** (19 ago → 30 nov) |
| Con arte producida | **43** (19 ago → 30 sep) |
| Publicables automáticamente hoy | **43** — 21 carruseles, 21 reels, 1 post único |
| Sin arte | **61** (todo octubre y noviembre) |

Los 21 reels **no traían video**: solo los frames PNG y el guion. Los MP4 se
generaron desde esos frames respetando la duración y los cortes que define cada
guion. Son un sustituto funcional, no el reel que el guion describe — varios
piden *screen recordings* del producto que no existen como material.

Octubre y noviembre están marcados «✕ no producido» en la propia agenda. Esos
61 días se publicarán solos en cuanto exista el arte: basta con dejar la carpeta
con el mismo formato y volver a construir el plan.

---

## Qué hace cada pieza

```
plan.json                      los 104 días normalizados: caption, alt text y medios
estado.json                    qué se publicó y cuándo (evita republicar)
medios/                        JPEG y MP4 servidos públicamente a Instagram
contenido/                     material fuente (no se sube al repo)

herramientas/construir_plan.py  agenda .xlsx + carpetas  →  plan.json
herramientas/preparar_medios.py PNG → JPEG y frames → MP4
herramientas/revisar_token.py   avisa si el token está por caducar
herramientas/obtener_cuenta_id.py  averigua tu IG_CUENTA_ID desde el token
herramientas/obtener_token_permanente.py  token de pagina que no caduca

publicador/api.py               cliente de la API de Instagram
publicador/publicar.py          publica lo que toca hoy

.github/workflows/publicar.yml  el cron diario
```

---

## Puesta en marcha

### 1. Requisitos de la cuenta

- Cuenta de Instagram **Professional** (Business o Creator) vinculada a una
  página de Facebook.
- Una app en [developers.facebook.com](https://developers.facebook.com) con el
  producto **Instagram** añadido.
- Permisos: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`.

### 2. Credenciales

**Estas las generas y las pegas tú. Yo no las manejo ni deben pasar por el chat.**

Necesitas dos valores:

- `IG_TOKEN` — el token de acceso.
- `IG_CUENTA_ID` — el ID numérico de tu cuenta de Instagram. No lo busques a
  mano; con el token ya en tu poder, ejecuta desde esta carpeta:

  ```bash
  IG_TOKEN=tu_token python herramientas/obtener_cuenta_id.py
  ```

  Te imprime el ID de cada cuenta de Instagram vinculada a tus páginas. El
  token solo se usa para esas dos consultas: no se guarda en ningún sitio.

> **Importante sobre el token.** Un token largo normal **caduca a los 60 días**
> y la campaña dura 104: se apagaría a mediados de octubre, en silencio, justo
> antes del 15 de noviembre.
>
> El usuario del sistema resuelve eso, pero exige el rol **Desarrollador** en el
> negocio; sin él Meta responde *«Rol de desarrollador insuficiente»*.

### Los dos tipos de token

Meta tiene dos flujos y el publicador acepta ambos: detecta cuál es por el
prefijo del token y habla con el host que corresponde.

| Prefijo | Flujo | Host | Requiere |
|---|---|---|---|
| `IGA…` | Instagram Login | `graph.instagram.com` | cuenta profesional |
| `EAA…` | Facebook Login | `graph.facebook.com` | cuenta vinculada a una página |

Con `IGA…` los permisos son `instagram_business_basic` e
`instagram_business_content_publish`. Con `EAA…` son `instagram_basic`,
`instagram_content_publish` y `pages_read_engagement`.

Si te equivocas de host, Meta responde con un error de token inválido aunque el
token esté perfectamente bien. Por eso conviene dejar que el publicador lo
resuelva solo.

Hay una vía que no necesita usuario del sistema ni ese rol. Un **token de página
derivado de un token largo de usuario no caduca nunca**. Se obtiene así:

1. En el [Explorador de la API de Graph](https://developers.facebook.com/tools/explorer/),
   elige tu app, marca `instagram_basic`, `instagram_content_publish` y
   `pages_read_engagement`, y pulsa *Generar token de acceso*. Ese token dura
   una hora: da igual, es la materia prima.
2. Copia el **ID de la app** y la **clave secreta** desde
   *Configuración → Básica* en el panel de la app.
3. Ejecuta desde esta carpeta:

   ```bash
   IG_APP_ID=... IG_APP_SECRET=... IG_TOKEN_CORTO=... python herramientas/obtener_token_permanente.py
   ```

Te imprime el `IG_TOKEN` definitivo y el `IG_CUENTA_ID`, y comprueba contra
Meta que el token efectivamente no tenga fecha de caducidad.

En GitHub, en el repositorio: **Settings → Secrets and variables → Actions**

| Tipo | Nombre | Valor |
|---|---|---|
| Secret | `IG_CUENTA_ID` | tu ID de cuenta |
| Secret | `IG_TOKEN` | tu token |
| Secret | `IG_APP_ID` | *(opcional)* para el aviso de caducidad |
| Secret | `IG_APP_SECRET` | *(opcional)* para el aviso de caducidad |
| Variable | `URL_MEDIOS` | `https://USUARIO.github.io/REPO` |

### 3. Activar GitHub Pages

**Settings → Pages → Source: Deploy from a branch → `main` / `/ (root)`**

Instagram no recibe los archivos: los **descarga** de una URL publica. Pages es
la que sirve los `.mp4` con el tipo `video/mp4` correcto.

> No uses `raw.githubusercontent.com` para los reels. Lo comprobe: sirve los
> videos como `application/octet-stream`, y ese es el motivo tipico de un reel
> que se queda atascado en `ERROR` al procesarse. Para las imagenes si funciona
> (`image/jpeg`), pero conviene una sola URL para todo.

### 4. Primera prueba, sin publicar nada

En la pestaña **Actions → Publicar en Instagram → Run workflow**, deja
`simular` en `true` y pon una fecha. Verifica que las URLs de los medios
salgan accesibles. Cuando eso pase, ya puedes desmarcar `simular`.

---

## Uso diario

No hay uso diario: corre solo. Lo que sí queda en tus manos es el protocolo que
la propia estrategia define, y que ninguna API puede hacer por ti:

- **primeros 15 min** — compartir a stories con encuesta o pregunta
- **primeros 60 min** — responder todos los comentarios, con una pregunta
- **primeras 2 horas** — enviar por DM a 5-10 contactos del sector

El resumen de cada ejecución en Actions te recuerda los tres puntos.

---

## Cuando produzcas el arte de octubre y noviembre

1. Crea la carpeta en `contenido/` con el patrón `AAAA-MM-DD_Formato_Tema`.
2. Dentro: las artes (`lamina-01.png`… para carrusel, `post.png` para imagen,
   `frame-01/02/03` + `portada-reel.png` para reel) y el `caption.txt` con el
   mismo formato que las 43 existentes.
3. Ejecuta:

```bash
python herramientas/construir_plan.py && python herramientas/preparar_medios.py
```

4. Haz commit de `plan.json` y de `medios/`.

---

## Notas técnicas

- Instagram **solo acepta JPEG** por `image_url`; por eso las PNG se convierten.
- Los medios se sirven por GitHub Pages, no por `raw.githubusercontent.com`:
  este ultimo entrega los `.mp4` como `application/octet-stream`. El publicador
  avisa si detecta ese caso antes de intentar el reel.
- La proporción del arte debe quedar entre 4:5 y 1.91:1. Las 1080×1350 dan
  exactamente 4:5, el límite del rango: no las recortes más.
- Límite de la API: 100 publicaciones por 24 horas. Aquí se usa 1.
- Antes de crear el contenedor, el publicador **verifica que Instagram pueda
  descargar el medio**. Si la URL no responde, falla ahí y no a medias.
- Si un día ya se publicó, no se repite aunque el workflow corra dos veces.
- El cron de GitHub puede retrasarse algunos minutos bajo carga. No es una hora
  exacta.
- Versión de la API: **v25.0**. Cada versión vive unos dos años; conviene subirla
  una vez al año en `publicador/api.py`.
