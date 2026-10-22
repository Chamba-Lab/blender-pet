# Capturas de blockout: frente, 3/4, perfil y espalda (Workbench, ortográfica) en una sola tira PNG.
# Uso en Blender: exec(open(bpy.path.abspath("//scripts/preview.py"), encoding="utf-8").read()); strip(out_path, center_z, ortho)
import bpy, os, math
import numpy as np
from mathutils import Vector

BG = (0.155, 0.214, 0.304)  # #6E7F95 en lineal


def _eevee_setup(sc):
    """Vista previa con materiales (EEVEE): luz principal arriba-izquierda + relleno, fondo #6E7F95."""
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng; break
        except TypeError:
            continue
    sc.eevee.taa_render_samples = 32
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = BG + (1.0,); bg.inputs['Strength'].default_value = 1.0
    coll = bpy.data.collections.get("Lights") or bpy.data.collections.new("Lights")
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    for name, loc, energy, size in (("Preview_Key", (-2.5, -3.0, 4.0), 900.0, 3.0), ("Preview_Fill", (3.0, -2.5, 2.0), 300.0, 4.0)):
        L = bpy.data.objects.get(name)
        if not L:
            L = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); coll.objects.link(L)
        L.data.energy = energy; L.data.size = size; L.location = loc
        L.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.view_settings.view_transform = 'AgX'


def _camera():
    cam = bpy.data.objects.get("Cam_Preview")
    if not cam:
        cam = bpy.data.objects.new("Cam_Preview", bpy.data.cameras.new("Cam_Preview"))
        c = bpy.data.collections.get("Cameras") or bpy.data.collections.new("Cameras")
        if c.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(c)
        c.objects.link(cam)
    cam.data.type = 'ORTHO'
    return cam


def strip(out_path, center_z=1.45, ortho=1.4, angles=(0, 35, 90, 180), size=800, center_x=0.0, center_y=0.0, engine='WORKBENCH'):
    sc = bpy.context.scene
    cam = _camera(); sc.camera = cam; cam.data.ortho_scale = ortho
    if engine == 'EEVEE':
        _eevee_setup(sc)
    else:
        sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_shadows = True; sh.show_cavity = False
    if not sc.world:
        sc.world = bpy.data.worlds.new("World")
    sc.world.color = BG
    sc.render.film_transparent = False
    sc.render.resolution_x = sc.render.resolution_y = size; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    if engine != 'EEVEE':
        sc.view_settings.view_transform = 'Standard'
    tmp = os.path.join(os.path.dirname(out_path), "_tmp_view.png")
    tiles = []
    target = Vector((center_x, center_y, center_z))
    for a in angles:
        r = math.radians(a)
        cam.location = target + Vector((math.sin(r) * 6, -math.cos(r) * 6, 0))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(tmp); im.colorspace_settings.name = 'Non-Color'
        tiles.append(np.array(im.pixels[:], dtype=np.float32).reshape(size, size, 4))
        bpy.data.images.remove(im)
    os.remove(tmp)
    arr = np.concatenate(tiles, axis=1)
    out = bpy.data.images.new("_strip", arr.shape[1], arr.shape[0], alpha=True)
    out.colorspace_settings.name = 'Non-Color'
    out.pixels.foreach_set(arr.ravel())
    out.filepath_raw = out_path; out.file_format = 'PNG'; out.save()
    bpy.data.images.remove(out)
    return out_path
