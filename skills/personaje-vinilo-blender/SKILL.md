---
name: personaje-vinilo-blender
description: Crear un personaje 3D estilo juguete de vinilo (chibi, mate, sin contorno) en Blender controlado por el agente vía MCP, y sacar de él hoja de personaje, poses, capas PNG/WebP y fotogramas intermedios para animarlo en una web con CSS/JS (sin Three.js). Usar cuando el usuario quiera diseñar, modelar, renderizar o animar su propio personaje o mascota en Blender, hacer un "turnaround" u hoja de personaje, poses, capas para la web, un avatar animado que mire al puntero, o seguir "el método del conejo / Bunny Studio".
---

# Personaje de vinilo en Blender → hoja, poses, capas y animación web

Método con el que se hizo el conejo de **Bunny Records**: un juguete de vinilo renderizado en Blender y animado en la web por capas (cuerpo, cabeza, orejas) con corte limpio entre imágenes y fotogramas intermedios. Funciona con cualquier personaje que se pueda dividir en piezas rígidas.

Archivos de este skill (rutas relativas a esta carpeta):

| Archivo | Para qué |
|---|---|
| `references/instalacion.md` | Requisitos e instalación de Blender + MCP. **Leer en la fase C0** |
| `references/capas-y-web.md` | Detalle de las fases C6–C8 (capas, verificación, reproductor, intermedios). Leer al llegar a C6 |
| `scripts/modeling_lib.py` | Formas (cabeza "bollo", cápsulas, píldoras, ojos `+`), rasgos por ray_cast, fusiones, medidas, materiales, luces, cámaras, plató giratorio |
| `scripts/layers_lib.py` | Poses, choques, capas, intermedios, verificación y exportación WebP. Se configura con `rig.json`; no se edita |
| `templates/brief.md` · `rig.json` · `poses.json` · `player.html` | Plantillas a copiar a la carpeta del personaje |

Cargar una librería en Blender: `exec(open(r"<ruta del skill>/scripts/modeling_lib.py", encoding="utf-8").read())`.

## 1. Forma de trabajar

- **Fase por fase, con aprobación del usuario** y capturas en cada paso. Nunca encadenar fases sin su visto bueno: el diseño es suyo.
- Revisar las uniones (cuello, hombros, manos) en primeros planos y, en la web, **el instante de cada transición**, no solo los estados finales.
- **Original + clon:** `personaje.blend` = solo lo aprobado; las pruebas en `lab/personaje-lab.blend`. Copia de seguridad en `backup/` antes de pasar cambios al original. Para traer objetos del clon: `bpy.data.libraries.load(..., link=False)` y después `bpy.data.libraries.remove(...)` (si no, el clon queda bloqueado).
- Estructura de la carpeta del personaje: `personaje.blend`, `brief.md`, `rig.json`, `poses/poses.json`, `sheet/`, `layers/`, `web/`, `scripts/` (guardar ahí los scripts útiles, no solo en temporales), `lab/`, `backup/`.
- Blender puede estar en otro idioma: buscar nodos por `type` (`BSDF_PRINCIPLED`), nunca por nombre.
- `result` del MCP debe ser un **dict**. Llamadas de más de ~120 s pasan a segundo plano: renderizar en tandas de 6–9 imágenes y no tocar Blender mientras tanto.
- Abrir otro archivo desde el MCP: `bpy.app.timers.register(lambda: (bpy.ops.wm.open_mainfile(filepath=p), None)[1], first_interval=0.5)` y esperar en otra llamada a que `bpy.data.filepath` sea el nuevo antes de seguir.
- Tras mover algo: `bpy.context.view_layer.update()` **antes** de leer `matrix_world`.
- No borrar renders ni archivos del usuario sin su permiso; al terminar, conservar solo la última versión de cada cosa si lo autoriza.

## 2. Fases

| Fase | Qué | Entregable | Aprobación |
|---|---|---|---|
| C0 | Requisitos (`references/instalacion.md`) + `.blend` vacío guardado | `personaje.blend` | MCP responde |
| C1 | Brief: referencias, proporciones medidas, cara, paleta, accesorio, decisiones abiertas | `brief.md` | Sí |
| C2 | Blockout: cada pieza un objeto con **el origen en su articulación** | capturas frente / 3/4 / perfil / espalda | Sí |
| C3 | Material, luz, fondo transparente | render sobre el fondo real de la web | Sí |
| C4 | Hoja de personaje (aprueba la identidad) | `sheet/` | Sí |
| C5 | Poses en JSON | `poses/poses.json` + renders | Sí |
| C6 | Capas para la web | `layers/` | Verificación numérica |
| C7 | Reproductor HTML/CSS/JS + WebP | `web/` | Sí, en el navegador |
| C8 | Fotogramas intermedios y transiciones directas | capas `-t25/-t50/-t75` | Sí, mirando el movimiento |

## 3. Brief (C1)

Copiar `templates/brief.md`. Preguntar al usuario, en una sola tanda: qué personaje es, referencias (2–4 imágenes; anotar qué se toma y qué **no** de cada una), paleta (hex), color del fondo donde vivirá, un único accesorio y qué tiene que transmitir. Si hay un logo o dibujo, **medir sobre él** las proporciones (ancho/alto de la cabeza, línea de ojos, separación y tamaño de los ojos, nariz) y ajustarlas para 3D (el volumen ensancha: ~0,95 del ancho medido; la curvatura separa los ojos: ~0,95 de la separación).

Estilo de partida (el usuario puede cambiarlo):
- Proporción **chibi**: cabeza ≈ 45–50 % de la altura sin orejas; altura de trabajo **2 m**.
- Formas simples y redondas, **sin contorno**, ojos gráficos sin pupila (en el conejo, `+` que parpadea a `−`), nariz píldora, **sin boca ni mejillas**: la expresión sale de la cabeza y los apéndices.
- **Un solo accesorio** fuerte que defina al personaje.
- Vinilo mate; colores solo de la paleta (sombras cálidas, nunca grises).

## 4. Modelado (C2) — `modeling_lib.py`

```python
head = bun_head("Char_Head", w=1.30, h=0.90, d=0.74, loc=(0, 0, 1.62))      # superelipse p≈2,4
torso = ellipsoid("t", 0.30, 0.26, 0.36, loc=(0, 0, 0.78))
legs = [capsule(f"leg{i}", 0.11, 0.2, loc=(s * 0.13, 0, 0.3)) for i, s in enumerate((1, -1))]
body = voxel_union([torso, *legs], "Char_Body", voxel=0.007, smooth=25)      # cuerpo de una pieza
arm = capsule("Char_Arm_L", 0.075, 0.30, loc=(0.30, 0, 0.82)); set_origin(arm, (0.30, 0, 1.0))
ear = capsule("Char_Ear_L", 0.10, 0.55, flatten=0.45, belly=0.15, taper=0.2, loc=(0.3, 0.05, 2.35))
eye = plus_sign("Char_Eye_L", 0.13, depth=0.03); place_on_surface(eye, head, 0.36, 1.60)
live_fusion(body, [arm_l, arm_r])                                              # brazos fundidos en vivo
```

- Cabeza tipo "bollo": esfera normalizada a superelipse, base algo más ancha y plana. Un pliegue o "cintura" = parámetros mal planteados: **rehacer, no parchear**.
- **Origen de cada pieza en su articulación** (hombro, base de la oreja, pivote del cuello): las poses giran objetos, no deforman mallas.
- Orejas, antenas o cola: **hijas de la cabeza** (o del cuerpo), con el padre asignado conservando `matrix_world`.
- Rasgos de la cara: `place_on_surface` (ray_cast desde delante, alineado con la normal), relieve sutil (~1 % del ancho de la cabeza) con la mitad hundida. El parpadeo es un objeto aparte (`Char_Blink_*`).
- **Cuerpo de una pieza:** torso + cuello + piernas + pies con `voxel_union` (vóxel 0,007, suavizado 25–30).
- **Brazos fundidos en vivo** (`live_fusion`): siguen siendo objetos para posar (ocultos), y el cuerpo los incorpora con Geometry Nodes → Remesh → Smooth. Sin casquetes de hombro (parecen hombreras).
- Lo que esté a menos de ~1 cm se funde en el render: medir con `gap(a, b)` (distancia real entre superficies), nunca a ojo ni desde el eje sin restar el radio. Choques: `overlaps(a, b)` debe dar 0.
- Accesorios: separarlos de la superficie por iteración hasta que el borde no toque; cintas como curva NURBS con `bevel_depth` apoyada con ray_cast.
- Capturas de aprobación: Workbench, cámara ortográfica, frente / 3/4 / perfil / espalda.

## 5. Material y luz (C3)

```python
setup_render((1200, 1600), samples=256)      # Cycles, GPU (OptiX/CUDA/HIP/Metal), denoise, AgX, exposición +0,35
assign(body, vinyl("Ivory", "#F4F4F2", roughness=0.5)); assign(eye, vinyl("Ink", "#080A0D", 0.35, 0))
shadow_floor(); studio_lights(accent_hex="#329DA8"); camera("Cam_Main", lens=85, yaw=-10, height=1.0)
```

- Vinilo mate: rugosidad ~0,5 y subsurface leve. Materiales de gomita: `gummy()` (sin volumen: oscurece hasta el negro sobre fondo oscuro).
- Luces: principal arriba-izquierda, relleno, cenital suave (sombra de contacto) y **dos contraluces del color de acento**. Sobre fondo oscuro, sin contraluz el personaje parece un recorte pegado.
- `film_transparent` + suelo `is_shadow_catcher`. Sobre fondos casi negros la sombra no se ve: el reproductor añade un halo de color bajo los pies.
- Comprobar el quemado con numpy: p99 de luminancia < color base.
- Vistas previas sobre el fondo real: cargar el PNG como `Non-Color`, alfa directo, `rgb*a + fondo*(1-a)`.
- **Cámara de la web casi frontal (~10°)**, teleobjetivo, algo baja. En 3/4 (30°), al mirar hacia un lado la cara queda de espaldas.

## 6. Hoja de personaje (C4)

- `camera("Cam_Sheet", ortho_scale=alto * 1.16, yaw=0, ...)` + primer plano de la cara a 85 mm.
- `turntable([0, 45, 90, 180], fn)`: gira **cámara y luces juntas** alrededor de Z, no el personaje → la misma luz en todas las vistas; se restaura sola.

## 7. Poses (C5)

Copiar `templates/rig.json` (nombres de objetos, pivote de la cabeza, pares de choque) y `templates/poses.json` a la carpeta del personaje.

```python
exec(open(r"<skill>/scripts/layers_lib.py", encoding="utf-8").read()); init(r"<carpeta-personaje>")
apply(POSES["curious-left"]); clashes()       # 0 = sin choques
min_clear("curious-left", ("head", 2), 0.0, 0.06, 0.005)   # elevación mínima sin choques
reset()
```

- `head = [giro Z, inclinación Y, elevación, cabeceo X]` sobre `head_pivot`; `ears`/`ears_x` = giros extra por objeto; `arm = [lado, elevación, adelante]`. Se aplican por script y se resetean: **nunca tocan el modelo**. Guardar el `.blend` siempre en reposo.
- **"left/right" en los nombres = lado de la pantalla** (la oreja izquierda del personaje sale a la derecha). En `rig.json`, `ears` va en orden de pantalla; `arms` L/R es el lado del personaje.
- Buscar por fuerza bruta el ángulo o la elevación mínimos sin choques antes de renderizar.
- Poses útiles: reposo, curiosidad izq./der., presentación (señalar) izq./der., mirar arriba izq./der.

## 8. Capas, web e intermedios (C6–C8)

Leer `references/capas-y-web.md`. Resumen:

```python
render_shadow(); render_pose("rest"); render_pose("curious-left")        # tandas de 6–9 renders
for t in STEPS: render_tween("curious-left", t)                             # reposo → pose
for t in STEPS: render_tween("look-up-left", t, to="curious-left")          # transición directa
verify_pose("curious-left")      # {"ok": True} con media < 0,3/255 y p99,9 ≤ 5 (a resolución real)
export_web(r"<carpeta-personaje>/web")     # WebP recortados + layers.web.js
```

Después copiar `templates/player.html` a `web/index.html` y probarlo en el navegador.

## 9. Errores que ya se cometieron (no repetir)

- Leer `matrix_world` sin `view_layer.update()` → cámaras en el origen y renders vacíos.
- Reconstruir el reposo de piezas hijas con coordenadas del mundo → orejas 90 cm más abajo. Guardar y reponer `matrix_basis`.
- Medir separaciones desde el eje sin restar radios → "3 cm" que eran −1 cm.
- Capas de ojos sueltas sobre ojos hundidos → no encajan. Una **cabeza completa por estado** (`-open` / `-blink`).
- Fundido cruzado entre poses → parpadeo (a mitad, las dos capas al 50 % dejan ver el fondo). **Corte limpio** e `img.decode()` antes de mostrar.
- Conectar todas las poses solo a través del reposo → giros innecesarios por el centro. Transiciones directas entre poses vecinas.
- Dos manejadores decidiendo la pose a la vez → el personaje rebota. Una sola función `desired()` con histéresis.
- Dar por buena una prueba de navegador sin mirar la transición en movimiento.
- Verificar capas con previsualizaciones de baja resolución: los bordes pesan más y el umbral p99,9 falla aunque esté bien. Verificar a la resolución final.
