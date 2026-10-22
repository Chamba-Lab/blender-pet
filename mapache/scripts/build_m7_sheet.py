# M7 — hoja de personaje: frente, 3/4, perfil, 3/4 trasera y espalda (ortográfica) + primer plano de la cara (85 mm).
# Se ejecuta después de M6 (usa su luz, materiales y render). No toca el modelo. Uso en Blender:
#   exec(open(bpy.path.abspath("//scripts/build_m7_sheet.py"), encoding="utf-8").read())
#   render_views(); render_face(); compose_sheet()
import bpy, math, os
import numpy as np
from mathutils import Vector, Matrix

SHEET_DIR = bpy.path.abspath("//sheet")

SHEET = dict(
    # plató giratorio: (nombre, giro de cámara y luces alrededor de Z en grados)
    views=[("front", 0.0), ("34", 35.0), ("side", 90.0), ("34back", 135.0), ("back", 180.0)],
    height=1.88,                 # alto del personaje con las púas
    ortho_k=1.16,                # ortho_scale = alto × 1,16
    center_z=0.94, dist=9.0,
    res=(1200, 1600),
    face=dict(yaw=12.0, lens=85.0, dist=3.0, target=(0.0, -0.2, 1.38), lift=0.05, res=(1200, 1200)),
    bg="#6E7F95",
    gap=40,                      # separación entre vistas en la hoja compuesta (px)
)


def _coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def _cam(name):
    cam = bpy.data.objects.get(name)
    if not cam:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); _coll("Cameras").objects.link(cam)
    return cam


def _aim(cam, tgt, yaw, dist, lift=0.0):
    r = math.radians(yaw)
    cam.location = tgt + Vector((math.sin(r) * dist, -math.cos(r) * dist, lift))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()


def sheet_camera(yaw):
    cam = _cam("Cam_Sheet"); cam.data.type = 'ORTHO'
    cam.data.ortho_scale = SHEET["height"] * SHEET["ortho_k"]
    cam.data.clip_end = 50.0
    _aim(cam, Vector((0.0, 0.0, SHEET["center_z"])), yaw, SHEET["dist"])
    return cam


def face_camera():
    f = SHEET["face"]; cam = _cam("Cam_Face"); cam.data.type = 'PERSP'; cam.data.lens = f["lens"]
    _aim(cam, Vector(f["target"]), f["yaw"], f["dist"], f["lift"])
    return cam


class _Turntable:
    """Gira las luces con la cámara (misma luz en todas las vistas) y lo restaura todo al salir."""

    def __enter__(self):
        sc = bpy.context.scene
        self.lights = [o for o in bpy.data.collections["Lights"].objects if o.type == 'LIGHT']
        self.rest = {o.name: o.matrix_world.copy() for o in self.lights}
        self.cam, self.res = sc.camera, (sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage)
        return self

    def yaw(self, deg):
        R = Matrix.Rotation(math.radians(deg), 4, 'Z')
        for o in self.lights:
            o.matrix_world = R @ self.rest[o.name]
        bpy.context.view_layer.update()

    def __exit__(self, *a):
        sc = bpy.context.scene
        for o in self.lights:
            o.matrix_world = self.rest[o.name]
        sc.camera = self.cam
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = self.res
        bpy.context.view_layer.update()


def _render(cam, path, res):
    sc = bpy.context.scene; sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    tmp = path[:-4] + "_tmp.png"; sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    os.replace(tmp, path)               # Windows bloquea archivos abiertos en visores
    return path


def render_views(names=None):
    os.makedirs(SHEET_DIR, exist_ok=True); out = []
    with _Turntable() as tt:
        for name, yaw in SHEET["views"]:
            if names and name not in names:
                continue
            tt.yaw(yaw)
            out.append(_render(sheet_camera(yaw), os.path.join(SHEET_DIR, f"mapache-{name}.png"), SHEET["res"]))
    return out


def render_face():
    os.makedirs(SHEET_DIR, exist_ok=True)
    with _Turntable() as tt:
        tt.yaw(SHEET["face"]["yaw"])
        return _render(face_camera(), os.path.join(SHEET_DIR, "mapache-face.png"), SHEET["face"]["res"])


def _load(path):
    im = bpy.data.images.load(path, check_existing=False); im.colorspace_settings.name = 'Non-Color'
    w, h = im.size; a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


def _save(arr, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new("_sheet", w, h, alpha=True); im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(arr.ravel()); tmp = path[:-4] + "_tmp.png"
    im.filepath_raw = tmp; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
    os.replace(tmp, path)
    return path


def compose_sheet():
    """Hoja sobre el fondo de presentación: las cuatro vistas en fila + la cara a la derecha, a la altura de la vista."""
    bg = np.array([int(SHEET["bg"][i:i + 2], 16) / 255 for i in (1, 3, 5)], dtype=np.float32)
    over = lambda a: np.dstack([a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:]), np.ones(a.shape[:2] + (1,), np.float32)])
    tiles = [over(_load(os.path.join(SHEET_DIR, f"mapache-{n}.png"))) for n, _ in SHEET["views"]]
    face = over(_load(os.path.join(SHEET_DIR, "mapache-face.png")))
    h = tiles[0].shape[0]; g = SHEET["gap"]
    # la cara (cuadrada) se escala a la altura de la hoja con vecino más cercano por índice: sin dependencias extra
    idx = (np.arange(h) * face.shape[0] / h).astype(int)
    face = face[idx][:, idx]
    pad = np.dstack([np.broadcast_to(bg, (h, g, 3)), np.ones((h, g, 1), np.float32)])
    row = []
    for t in tiles + [face]:
        row += [t, pad]
    arr = np.concatenate(row[:-1], axis=1)
    return _save(arr, os.path.join(SHEET_DIR, "mapache-sheet.png"))
