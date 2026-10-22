# Instalación y requisitos (C0)

Comprobar todo **antes** de empezar. Si falta algo, guiar al usuario paso a paso; no instalar software del sistema sin su permiso.

## Lo que se usó con el conejo (Windows 11, verificado)

| Pieza | Versión |
|---|---|
| Blender | 5.2 LTS (funciona desde 5.1) |
| Servidor MCP de Blender (Blender Lab) | `blender-mcp` 1.0.3 (Python ≥ 3.10) |
| Complemento MCP dentro de Blender | `mcp-1.0.3.zip` |
| GPU | NVIDIA RTX con 12 GB (Cycles + OptiX) |

## Pasos

1. **Blender ≥ 5.1** desde blender.org/download.
2. **Servidor MCP de Blender Lab**: página `blender.org/lab/mcp-server`. Trae dos partes y hacen falta las dos:
   - **Complemento** (`mcp-x.y.z.zip`): en Blender, *Edit → Preferences → Add-ons → Install from Disk*. Activarlo, marcar **Auto Start**, host `localhost`, puerto `9876`. Debe decir *Server is running*.
   - **Servidor** (paquete Python `blender-mcp`): seguir las instrucciones de esa página para el cliente que se use. Si la página cambia, manda la página.
3. **Conectar el agente** (Claude Code) al servidor. Una forma que funciona: instalar el paquete en un entorno propio y registrarlo:
   ```bash
   # Windows (PowerShell); en macOS/Linux usar python3 y bin/ en vez de Scripts\
   py -m venv $HOME\.blender-mcp\venv
   & $HOME\.blender-mcp\venv\Scripts\pip install <paquete o carpeta del servidor descargado>
   claude mcp add blender --scope user -- "$HOME\.blender-mcp\venv\Scripts\blender-mcp.exe"
   ```
   En Claude Desktop basta con instalar el paquete del servidor desde la misma página.
4. **Orden de arranque:** abrir Blender primero (arranca el puente) y después iniciar o reiniciar la sesión del agente.
5. **Comprobar:** la herramienta `get_objects_summary` del MCP responde con la escena.

## Opcionales

| Qué | Para qué | Comprobar |
|---|---|---|
| Node.js | Comprobar la sintaxis del reproductor | `node --version` |
| Python del sistema | Servir el reproductor en `http://127.0.0.1` si el navegador bloquea `file://` | `py --version` / `python3 --version` |
| Navegador controlable por el agente (Playwright, Chrome) | Probar el reproductor y grabar el movimiento | — |

No hace falta Pillow: toda la composición de imágenes se hace con numpy dentro de Blender.

## Sin GPU

Funciona en CPU, pero mucho más lento: bajar a 128 muestras para pruebas y dejar las 256 para las capas finales. `setup_render()` devuelve qué dispositivo ha elegido (`OPTIX`, `CUDA`, `HIP`, `METAL`, `ONEAPI` o `CPU`).

## Desinstalar

Pedir autorización. Quitar la conexión (`claude mcp remove blender --scope user`), borrar el entorno del servidor y desactivar el complemento en Blender.
