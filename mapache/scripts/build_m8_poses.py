# M8 — Poses estáticas del mapache, definidas en poses/poses.json. Se ejecuta después de M1–M8 (pupilas).
# No toca el modelo: apply() posa y reset() vuelve al reposo. Uso en Blender:
#   exec(open(bpy.path.abspath("//scripts/build_m8_poses.py"), encoding="utf-8").read())
#   write_json(); check_all(); render_all(); compose_strip()
# Convenciones (como el conejo de Bunny Records):
#   head = [giro Z, inclinación Y, elevación m, cabeceo X (negativo = mirar arriba)], en grados, sobre el
#          origen de la cabeza (base del cuello). Giro > 0 = la cara va hacia la derecha de la pantalla.
#   arm  = [lado del personaje "L"/"R", elevación lateral desde el reposo, adelante]
#   gaze = [u, v] de set_gaze() en metros (u > 0 = derecha de la pantalla, v > 0 = arriba)
#   "left/right" = lado de la pantalla con Cam_Pose (casi frontal). El brazo R del personaje sale a la izquierda.
import bpy, math, os, json
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = bpy.path.abspath("//")
exec(open(os.path.join(ROOT, "scripts", "build_m7_sheet.py"), encoding="utf-8").read())
exec(open(os.path.join(ROOT, "scripts", "build_m8_eyes.py"), encoding="utf-8").read())

POSE_DIR = os.path.join(ROOT, "poses")
CAM = dict(yaw=-10.0, lens=70.0, dist=4.75, target=(0.0, 0.0, 0.97), lift=0.2, res=(1200, 1600))
POSES = {
    "rest": {},
    "curious-left": {"head": [-20, -9, 0.0], "gaze": [-0.03, -0.004]},
    "curious-right": {"head": [20, 9, 0.0], "gaze": [0.03, -0.004]},
    "present-left": {"head": [-12, -3, 0.0], "arm": ["R", 70, 25], "gaze": [-0.035, -0.006]},
    "present-right": {"head": [12, 3, 0.0], "arm": ["L", 70, 25], "gaze": [0.035, -0.006]},
    "look-up-left": {"head": [-15, -4, 0.0, -14], "gaze": [-0.025, 0.008]},
    "look-up-right": {"head": [15, 4, 0.0, -14], "gaze": [0.025, 0.008]},
}
NAMES = ["Raccoon_Head", "Raccoon_Arm_L", "Raccoon_Arm_R"]
O = {n: bpy.data.objects[n] for n in NAMES}
bpy.context.view_layer.update()
REST = {n: O[n].matrix_basis.copy() for n in NAMES}
PIV = REST["Raccoon_Head"].to_translation()       # base del cuello
D = math.radians


def reset():
    for n in NAMES:
        O[n].matrix_basis = REST[n].copy()
    set_gaze()
    bpy.context.view_layer.update()


def pose_arm(side, up, fwd):
    o = O[f"Raccoon_Arm_{side}"]; s = -1 if side == "L" else 1      # L está en +X: hacia fuera = giro Y negativo
    loc = REST[o.name].to_translation()
    o.matrix_basis = Matrix.Translation(loc) @ Matrix.Rotation(D(-fwd), 4, 'X') @ Matrix.Rotation(D(s * up), 4, 'Y') \
        @ Matrix.Translation(-loc) @ REST[o.name]


def apply(p):
    reset()
    if "head" in p:
        yaw, roll, lift = p["head"][:3]
        pitch = p["head"][3] if len(p["head"]) > 3 else 0
        R = Matrix.Rotation(D(yaw), 4, 'Z') @ Matrix.Rotation(D(pitch), 4, 'X') @ Matrix.Rotation(D(roll), 4, 'Y')
        O["Raccoon_Head"].matrix_basis = Matrix.Translation(PIV + Vector((0, 0, lift))) @ R @ Matrix.Translation(-PIV) \
            @ REST["Raccoon_Head"]
    if "arm" in p:
        pose_arm(*p["arm"])
    if "gaze" in p:
        set_gaze(*p["gaze"])
    bpy.context.view_layer.update()


def write_json():
    os.makedirs(POSE_DIR, exist_ok=True)
    doc = {"_nota": "Grados. head = [giro Z, inclinación Y, elevación m, cabeceo X opcional (negativo = mirar arriba)] "
                    "sobre la base del cuello. arm = [lado del personaje, elevación lateral, adelante]. gaze = [u, v] en m "
                    "(set_gaze). 'left/right' = lado de la pantalla con Cam_Pose (casi frontal, -10°).",
           "camera": CAM, "poses": POSES}
    p = os.path.join(POSE_DIR, "poses.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return p


def _bvh(objs, evaluated=True):
    dg = bpy.context.evaluated_depsgraph_get(); V, F = [], []
    for o in objs:
        e = o.evaluated_get(dg) if evaluated else o
        m = e.to_mesh(); k = len(V)
        V += [o.matrix_world @ v.co for v in m.vertices]; F += [[k + i for i in p.vertices] for p in m.polygons]
        e.to_mesh_clear()
    return BVHTree.FromPolygons(V, F)


def _head_parts():
    return [O["Raccoon_Head"]] + [c for c in O["Raccoon_Head"].children if c.type == 'MESH']


def check(name):
    """Choques: brazo posado contra cabeza y pelo; cabeza (con collar) contra cuerpo, comparada con el reposo."""
    apply(POSES[name]); r = {}
    head = _bvh(_head_parts())
    if "arm" in POSES[name]:
        arm = O[f"Raccoon_Arm_{POSES[name]['arm'][0]}"]
        r["arm_head"] = len(_bvh([arm], evaluated=False).overlap(head))
    r["head_body"] = len(head.overlap(_bvh([bpy.data.objects["Raccoon_Body"]])))
    reset()
    return r


def check_all():
    base = check("rest")["head_body"]
    return {"rest_head_body": base, **{n: check(n) for n in POSES if n != "rest"}}


def pose_camera():
    cam = _cam("Cam_Pose"); cam.data.type = 'PERSP'; cam.data.lens = CAM["lens"]; cam.data.clip_end = 50.0
    _aim(cam, Vector(CAM["target"]), CAM["yaw"], CAM["dist"], CAM["lift"])
    return cam


def render_pose(name, res=None):
    os.makedirs(POSE_DIR, exist_ok=True)
    try:
        apply(POSES[name])
        with _Turntable() as tt:
            tt.yaw(CAM["yaw"])               # la luz acompaña a la cámara, como en la hoja
            return _render(pose_camera(), os.path.join(POSE_DIR, f"mapache-{name}.png"), res or CAM["res"])
    finally:
        reset()


def render_all(names=None):
    return [render_pose(n) for n in (names or POSES)]


def compose_strip(names=None, scale=0.5):
    """Tira de poses sobre el fondo de presentación (poses/mapache-poses.png)."""
    names = names or list(POSES)
    bg = np.array([int(SHEET["bg"][i:i + 2], 16) / 255 for i in (1, 3, 5)], dtype=np.float32)
    tiles = []
    for n in names:
        a = _load(os.path.join(POSE_DIR, f"mapache-{n}.png"))
        step = int(round(1 / scale)); a = a[::step, ::step]
        tiles.append(np.dstack([a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:]), np.ones(a.shape[:2] + (1,), np.float32)]))
    return _save(np.concatenate(tiles, axis=1), os.path.join(POSE_DIR, "mapache-poses.png"))
