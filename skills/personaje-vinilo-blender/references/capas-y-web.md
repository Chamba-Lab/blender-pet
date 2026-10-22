# Capas, reproductor web y fotogramas intermedios (C6–C8)

## Por qué capas y no 3D en tiempo real

El aspecto de juguete sale del render de Cycles (subsurface, sombras suaves, contraluces). En el navegador se montan imágenes ya renderizadas y se cambian con corte limpio. Three.js daría fluidez total, pero con peor material y más peso; Rive, Spline o Lottie no hacen falta.

## Nombres de capa (los genera `layers_lib.py`)

| Capa | Contenido |
|---|---|
| `{prefix}-shadow` | Solo la sombra en el suelo (reposo) |
| `{prefix}-body-{pose}` | Cuerpo (con brazos fundidos y la sombra que le hace su cabeza) |
| `{prefix}-head-{pose}-open` / `-blink` | Cabeza completa con rasgos; fuera del reposo incluye las orejas |
| `{prefix}-ear-left` / `-right` | Orejas sueltas, solo en reposo (se mueven en CSS) |
| `{prefix}-full-rest` | Imagen fija completa (movimiento reducido y primera carga) |
| `{prefix}-body-{pose}-t25/t50/t75`, `{prefix}-head-{pose}-t50-open` | Intermedios reposo → pose |
| `{prefix}-body-{a}--{b}-t50`, `{prefix}-head-{a}--{b}-t50-open` | Transición directa a → b |

Orden de dibujo: sombra → cuerpo → orejas (solo reposo) → cabeza.

## C6 · Capas

- Mismo lienzo y cámara para todas. Cada capa se renderiza con las demás piezas **invisibles para la cámara pero proyectando sombras** (`visible_camera=False`): las sombras entre piezas quedan horneadas.
- **Un cuerpo por pose de cabeza** (lleva la sombra de su cabeza). Con brazos fundidos, el cuerpo se renderiza entero por cada pose de brazo.
- **Cuello delante de la cabeza** (cámara algo baja): la cabeza se renderiza dos veces → color del render normal + alfa del render con el cuerpo como `is_holdout`, alfa = mínimo. Solo con holdout los reflejos salen negros. `render_head` ya lo hace.
- Limpieza (automática): alfa a 0 en un borde de 6 px (restos del denoiser) y RGB a 0 donde alfa < 1/255 (≈ −50 % de peso).
- Se escribe en un temporal y luego `os.replace` (Windows bloquea archivos abiertos en visores).
- **Verificar** cada pose con `verify_pose(nombre)`: monta las capas (operador *over*, alfa directo) y las compara con su render completo sobre el fondo real. Aprobado si media < 0,3/255 y p99,9 ≤ 5. Revisar el mapa `_diff_<pose>.png` (diferencias ×8). Solo vale a la resolución final: en previsualizaciones pequeñas los bordes disparan el p99,9.
- Tiempo orientativo con RTX: 1200 × 1600 a 256 muestras ≈ 10–15 s por render; una pose con parpadeo son 5 renders.

## C7 · Reproductor

- `export_web(carpeta)`: recorta cada capa a su recuadro (+2 px), la guarda en WebP calidad 88 y escribe `layers.web.json` y `layers.web.js` (`window.CHARACTER = {...}`, para abrir el HTML con doble clic). Calcula los pivotes en píxeles desde `rig.json → pivots_world`.
- Copiar `templates/player.html` a `web/index.html`. Incluye: respiración, parpadeo cada 4–7 s, mirar al puntero, curiosidad al pasar por tarjetas, presentación al hacer clic, baile al pulsar el personaje, `prefers-reduced-motion` (imagen fija) y precarga (primero el reposo, el resto después).
- Probar con un servidor local si el navegador bloquea `file://`: `py -m http.server 8765 --bind 127.0.0.1` (o `python3 -m http.server` en macOS/Linux) desde `web/`. Cerrar la pestaña y parar el servidor al terminar.
- **Las animaciones CSS se pausan con la pestaña en segundo plano**: no medir opacidades por script ahí; mirar con la pestaña al frente.
- Peso orientativo: reposo ≈ 100 KB; ~100 capas ≈ 2 MB en WebP.

## C8 · Fotogramas intermedios

- Las imágenes no "giran": para un giro fluido hacen falta intermedios. `render_tween(pose, t)` interpola desde el reposo (el brazo parte de `arm_rest_up`). Renderizar t = 0,25 / 0,5 / 0,75 (cuerpo + cabeza, sin parpadeo); `render_tween` comprueba choques en cada uno.
- **Grafo de poses, no estrella:** si todas las poses solo se conectan por el reposo, ir de "arriba-izquierda" a "izquierda" pasa por el centro y se nota. Renderizar transiciones directas entre vecinas (`render_tween(a, t, to=b)`) y listarlas en `rig.json → transitions`. Pares útiles: arriba↔lado, lado↔señalar, arriba↔señalar, en cada lado.
- El reproductor recorre el **camino más corto** (Dijkstra en número de fotogramas), ~22 ms por fotograma, y da la vuelta si el objetivo cambia a mitad de una arista. Si faltan intermedios, corta directamente a la pose.
- **Una sola decisión de mirada:** `desired()` (tarjeta bajo el puntero > dirección del puntero > reposo) + **histéresis** (~90 px de margen para salir de la pose actual) + **confirmación con espera** (60 ms al entrar en una tarjeta, 140 ms siguiendo el puntero).
- Prueba recomendada: registrar cada fotograma con un `MutationObserver` sobre las clases `.on` y recorrer tarjeta → fuera → tarjeta vecina → fuera. Entre poses vecinas, el registro no debe pasar por el reposo.
- Comprobar la sintaxis del JS si se edita el reproductor: `node -e "new Function(js)"` (una constante redeclarada rompe todo el script).
