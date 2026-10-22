# Personaje de vinilo en Blender

Requiere **Blender 5.1 o posterior** y el **MCP oficial de Blender (Blender Lab)**, tanto el complemento de Blender como el servidor conectado al agente. Consulta [instalación](references/instalacion.md).

## Instalación y uso

Copia esta carpeta completa a `~/.claude/skills/personaje-vinilo-blender/`. Conserva `SKILL.md`, `references/`, `scripts/` y `templates/`. Abre Blender con el complemento MCP activo y después inicia el agente.

Prompt de ejemplo: «Usa personaje-vinilo-blender para crear un mapache de vinilo mate a partir de mis referencias. Avanza fase por fase y espera mi aprobación».

## Fases

C0 requisitos → C1 brief → C2 blockout → C3 material y luz → C4 hoja de personaje → C5 poses → C6 capas → C7 reproductor web → C8 intermedios. Los criterios de aprobación están en [SKILL.md](SKILL.md#2-fases).

## Umbral de similitud de las capas

`verify_pose()` compara la imagen recompuesta por capas con el render completo sobre el mismo fondo. Exige **error medio < 0,3/255** y **percentil 99,9 ≤ 5/255**. Ambos límites se cambian en la condición `mean < 0.3 and p999 <= 5` de [scripts/layers_lib.py, línea 345](scripts/layers_lib.py#L345).

La lección del enfoque 3: verificar a la **resolución final**, porque en una previsualización pequeña los bordes pesan más y pueden hacer fallar el percentil. Este umbral comprueba la fidelidad de las capas; no mide el parecido del personaje con una referencia de diseño. Mantén coherentes los límites documentados en `SKILL.md`, `references/capas-y-web.md` y el docstring de `verify_pose()` si los cambias.

Esta es una copia de referencia de la skill compartida; no se sincroniza automáticamente.

## Licencia

Toda esta carpeta, incluidos la skill, las referencias, los scripts y las plantillas, se publica bajo [MIT](LICENSE). Conserva ese archivo al instalar o redistribuir la skill.
