# M3 — Collar de pelo bajo la cabeza (cachitos que apuntan hacia fuera y hacia abajo).
# Se diseña a un costado de la cabeza (C["offset"]) y, una vez aprobado, se une con attach_collar().
# Medidas tomadas de la cabeza: ancho 0,86 m -> collar de ~0,70 m de ancho exterior.
#   exec(open(bpy.path.abspath("//scripts/build_m3_collar.py"), encoding="utf-8").read())
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

C = dict(
    offset=(1.3, 0.0, 0.0),            # posición de diseño (a un costado); (0,0,0) = unido
    center=(0.0, 0.0, 0.99),           # centro del collar unido: bajo la cabeza, a la altura del cuello
    ring_r=(0.23, 0.21),               # radio del anillo base (x, y)
    tube=0.052,                        # grosor del anillo base
    n=12, seed=3,
    spike_len=(0.10, 0.115), spike_r=(0.058, 0.064), tip=0.36,
    down=45.0,                         # grados hacia abajo respecto a la horizontal
    voxel=0.0045, smooth=14,
)


def _cachito(bm, base, axis, length, radius, tip, curl_dir=None, curl=0.0):
    z = axis.normalized()
    ref = Vector((0, 0, 1)) if abs(z.z) < 0.95 else Vector((1, 0, 0))
    x = ref.cross(z).normalized(); y = z.cross(x)
    R = Matrix((x, y, z)).transposed()
    g = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=14, radius=1.0)
    for v in g['verts']:
        t = (v.co.z + 1) / 2
        if t < 0.92:
            k = tip + (1 - tip) * (1 - t ** 1.6) ** 0.9
        else:
            k = tip * math.sqrt(max(0.0, 1 - ((t - 0.92) / 0.08) ** 2))
        loc = Vector((v.co.x * radius * k, v.co.y * radius * k, t * length - 0.2 * length))
        p = base + R @ loc
        if curl_dir is not None:
            p += curl_dir * curl * t * t
        v.co = p


def build_collar():
    old = bpy.data.objects.get("Raccoon_Collar")
    if old:
        bpy.data.objects.remove(old)
    coll = bpy.data.collections["Raccoon"]
    rnd = random.Random(C["seed"])
    bm = bmesh.new()
    # anillo base (toro elíptico)
    tor = bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=16, radius=1.0)
    rx, ry = C["ring_r"]
    for v in tor['verts']:
        a = math.atan2(v.co.y, v.co.x); r = math.hypot(v.co.x, v.co.y)
        # esfera -> toro: el "radio" de la esfera se convierte en el tubo alrededor del anillo
        cx, cy = math.cos(a) * rx, math.sin(a) * ry
        out = Vector((math.cos(a), math.sin(a), 0))
        v.co = Vector((cx, cy, 0)) + out * (r * C["tube"]) + Vector((0, 0, v.co.z * C["tube"] * 1.2))
    # cachitos alrededor, hacia fuera y abajo, con un leve giro hacia abajo en la punta
    dn = math.radians(C["down"])
    for k in range(C["n"]):
        a = 2 * math.pi * (k + rnd.uniform(-0.12, 0.12)) / C["n"]
        out = Vector((math.cos(a), math.sin(a), 0))
        base = Vector((math.cos(a) * rx, math.sin(a) * ry, 0)) + out * C["tube"] * 0.3
        axis = out * math.cos(dn) + Vector((0, 0, -1)) * math.sin(dn)
        _cachito(bm, base, axis, rnd.uniform(*C["spike_len"]), rnd.uniform(*C["spike_r"]), C["tip"],
                 Vector((0, 0, -1)), 0.03)
    me = bpy.data.meshes.new("Raccoon_Collar"); bm.to_mesh(me); bm.free()
    me.materials.append(bpy.data.materials["Raccoon_Fur"])
    o = bpy.data.objects.new("Raccoon_Collar", me); coll.objects.link(o)
    r = o.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = C["voxel"]
    s = o.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.7; s.iterations = C["smooth"]
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); oldm = o.data; o.data = new; bpy.data.meshes.remove(oldm)
    new.shade_smooth()
    o.location = Vector(C["center"]) + Vector(C["offset"])
    return o


def attach_collar():
    """Une el collar bajo la cabeza (hijo de Raccoon_Head)."""
    o = bpy.data.objects["Raccoon_Collar"]; head = bpy.data.objects["Raccoon_Head"]
    o.parent = None
    o.location = Vector(C["center"])
    bpy.context.view_layer.update()
    o.parent = head; o.matrix_parent_inverse = head.matrix_world.inverted()
    return o


collar = build_collar()
