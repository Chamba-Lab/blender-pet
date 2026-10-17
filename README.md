# Blender Pet · ChambaLab

Proyecto de modelado y renders del mapache de ChambaLab en Blender.

- `mapache/mapache.blend`: escena principal editable.
- `mapache/scripts/`: scripts de construcción, materiales, cámaras y poses para ejecutar dentro de Blender.
- `mapache/sheet/`: hoja del personaje y vistas renderizadas.
- `mapache/poses/`: renders y configuración JSON de poses.

Para trabajar con el personaje, abre la escena principal en Blender. Los scripts contienen rutas del entorno original (`C:\APPS\Renders`); ajústalas si clonas el proyecto en otra ubicación.

Las referencias originales no se distribuyen. La reconstrucción de la cara con `build_m2_face.py` requiere la referencia local `mapache/references/highsfield3.png`. El modelo guardado puede abrirse sin reconstruirlo desde los scripts.

La configuración local, las referencias, los borradores, las capturas intermedias, los experimentos y los backups quedan fuera del repositorio.
