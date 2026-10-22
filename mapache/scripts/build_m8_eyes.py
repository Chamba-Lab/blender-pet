# M8 — Pupilas del mapache (antes de las poses). Se ejecuta después de M1–M7.
# exec(open(bpy.path.abspath("//scripts/build_m8_eyes.py"), encoding="utf-8").read()); build_pupils()
# Ojo = elipsoide (eye_r, eye_ry, eye_d) en su marco local: x = lado, y = arriba, z = normal hacia fuera.
# La pupila es un botón oscuro satinado que se apoya en la superficie del ojo y se mete bajo el párpado
# (expresión de sueño). La mirada se cambia con set_gaze(u, v) sin tocar el modelo.
import bpy, bmesh, math
from mathutils import Vector, Matrix

EYE = dict(r=0.118, ry=0.092, d=0.05)            # = build_m1_head.P eye_r, eye_ry, eye_d
PUP = dict(r=0.036, ry=0.040, depth=0.012, out=0.0035)
GAZE_REST = (0.0, -0.006)                        # (u, v) en metros sobre el ojo; v > 0 = arriba (bajo el párpado)
CONVERGE = 0.022                                 # pupilas desplazadas hacia la nariz: centradas parecían bizcas hacia fuera


def _surface(u, v):
    """Punto y normal de la superficie frontal del ojo en (u, v), marco local del ojo."""
    e = EYE
    k = max(1e-6, 1 - (u / e["r"]) ** 2 - (v / e["ry"]) ** 2)
    p = Vector((u, v, e["d"] * math.sqrt(k)))
    n = Vector((u / e["r"] ** 2, v / e["ry"] ** 2, p.z / e["d"] ** 2)).normalized()
    return p, n


def _frame(n):
    up = Vector((0, 1, 0)); y = (up - n * n.dot(up)).normalized(); x = y.cross(n)
    return Matrix((x, y, n)).transposed()


def set_gaze(u=None, v=None, sides=("L", "R")):
    """Mueve las pupilas. u > 0 = hacia el lado izquierdo del personaje (+X mundial) en ambos ojos."""
    if u is None:
        u, v = GAZE_REST
    for side in sides:
        eye = bpy.data.objects[f"Raccoon_Eye_{side}"]
        pup = bpy.data.objects[f"Raccoon_Pupil_{side}"]
        inward = -CONVERGE if side == "L" else CONVERGE  # x local de ambos ojos = +X mundial
        p, n = _surface(u + inward, v)
        R = _frame(n)
        p = p + n * (PUP["out"] - PUP["depth"])
        pup.matrix_basis = Matrix.Translation(p) @ R.to_4x4()
        pup["gaze"] = (u, v)


def build_pupils():
    ink = bpy.data.materials["Raccoon_Ink"]
    coll = bpy.data.collections["Raccoon"]
    for side in ("L", "R"):
        name = f"Raccoon_Pupil_{side}"
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)
        for vt in bm.verts:
            vt.co = Vector((vt.co.x * PUP["r"], vt.co.y * PUP["ry"], vt.co.z * PUP["depth"]))
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        me.materials.append(ink)
        o = bpy.data.objects.new(name, me); coll.objects.link(o)
        o.parent = bpy.data.objects[f"Raccoon_Eye_{side}"]
        o.matrix_parent_inverse = Matrix.Identity(4)     # pupila en el marco local del ojo
    set_gaze()
    bpy.context.view_layer.update()
