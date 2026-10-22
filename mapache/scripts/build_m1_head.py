# M1 — Cabeza base del mapache (bola + hocico, ojos sin pupila, párpados, nariz, orejas).
# Ejecutar dentro de Blender: exec(open(bpy.path.abspath("//scripts/build_m1_head.py"), encoding="utf-8").read())
# Unidades: altura total 2,0 m. Frente del personaje = -Y. "_L" = lado izquierdo del personaje (+X).
import bpy, bmesh, math
from mathutils import Vector, Matrix

P = dict(
    neck=(0.0, 0.0, 0.95),          # origen de la cabeza (base del cuello)
    head_c=(0.0, 0.0, 1.38), head_r=(0.43, 0.37, 0.40),
    # Hocico = colina triangular: estrecha entre los ojos, ancha y adelantada en la nariz, cae hacia la barba
    muz_z=1.235, muz_top=1.37, muz_drop=0.13, muz_h=0.135, muz_w_nose=0.17, muz_w_top=0.07, muz_lift=0.04,
    cheek_z=1.19, cheek_sigma=0.11, cheek_w=0.13,     # mejillas: la cara se ensancha a los lados
    eye_x=0.205, eye_z=1.345, eye_r=0.118, eye_ry=0.092, eye_d=0.05, eye_out=0.035,
    lid_cut=0.22, lid_tilt=8.0, lid_scale=1.06,
    # Nariz = botón ovalado plano y pequeño
    nose_z=1.235, nose_r=(0.052, 0.042, 0.024), nose_out=0.019, nose_up=14.0, nose_low=0.65,
    # Oreja = triángulo redondeado con grosor; base enterrada en la cabeza; interior cóncavo con borde
    ear_base=(0.27, 0.0, 1.64), ear_w=0.32, ear_h=0.38, ear_bury=0.10, ear_round=0.064, ear_t=0.10,
    ear_pad=0.035, ear_rim_from=0.02, ear_cup=0.02, ear_bowl=0.08, ear_bend=0.06, ear_tilt=35.0, ear_back=12.0, ear_yaw=15.0,
    voxel=0.006,
)

COL = dict(fur="#2E3044", cream="#D9CEC0", slate="#5D6F87", ink="#1A1C26")


def hex_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def material(name, hexc, rough=0.55):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = hex_lin(hexc)
    bsdf.inputs['Roughness'].default_value = rough
    m.diffuse_color = hex_lin(hexc)
    return m


def collection(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def remove_prefix(prefix):
    for o in [o for o in bpy.data.objects if o.name.startswith(prefix)]:
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


def ellipsoid(bm, radii, center=(0, 0, 0), seg=64, rings=40):
    g = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in g['verts']:
        v.co = Vector((v.co.x * radii[0] + center[0], v.co.y * radii[1] + center[1], v.co.z * radii[2] + center[2]))
    return g['verts']


def new_obj(name, bm, coll, mat, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    coll.objects.link(o)
    me.shade_smooth()
    return o


def bake_modifiers(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    old = o.data
    o.modifiers.clear()
    o.data = me
    bpy.data.meshes.remove(old)
    me.shade_smooth()


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def rounded_triangle(W, H, base_z, rr, n_arc=20):
    """Contorno (x, z) de un triángulo de base W y vértice a altura H, esquinas redondeadas de radio rr."""
    A, B, C = Vector((-W / 2, base_z)), Vector((W / 2, base_z)), Vector((0, H))
    pts = [A, B, C]                                   # antihorario
    def inward(p, q):
        d = (q - p).normalized(); return Vector((-d.y, d.x))
    lines = [(pts[i] + inward(pts[i], pts[(i + 1) % 3]) * rr, (pts[(i + 1) % 3] - pts[i]).normalized()) for i in range(3)]
    def cross2(a, b): return a.x * b.y - a.y * b.x
    inner = []
    for i in range(3):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        t = cross2(p2 - p1, d2) / cross2(d1, d2)
        inner.append(p1 + d1 * t)
    out = []
    for i in range(3):
        n0 = -inward(pts[i - 1], pts[i]); n1 = -inward(pts[i], pts[(i + 1) % 3])
        a0, a1 = math.atan2(n0.y, n0.x), math.atan2(n1.y, n1.x)
        while a1 < a0:
            a1 += 2 * math.pi
        for k in range(n_arc + 1):
            a = a0 + (a1 - a0) * k / n_arc
            out.append((inner[i].x + rr * math.cos(a), inner[i].y + rr * math.sin(a)))
    return out


def polygon_sdf(poly, pts):
    """Distancia con signo (negativa dentro) de los puntos 2D al polígono."""
    import numpy as np
    P_ = np.array(poly); Q = np.array(pts)
    A = P_; B = np.roll(P_, -1, axis=0); AB = B - A
    AQ = Q[:, None, :] - A[None]
    t = np.clip((AQ * AB[None]).sum(2) / (AB * AB).sum(1)[None], 0, 1)
    dist = np.linalg.norm(AQ - t[..., None] * AB[None], axis=2).min(1)
    yi, yj = A[:, 1][None], B[:, 1][None]; xi, xj = A[:, 0][None], B[:, 0][None]
    qx, qy = Q[:, 0][:, None], Q[:, 1][:, None]
    cross = ((yi > qy) != (yj > qy)) & (qx < (xj - xi) * (qy - yi) / (yj - yi + 1e-12) + xi)
    inside = cross.sum(1) % 2 == 1
    return np.where(inside, -dist, dist)


def frame_on(obj, x, z, side_dir=(0, -1, 0)):
    """Raycast desde delante sobre obj; devuelve (punto, matriz 3x3 con z=normal, y≈arriba)."""
    bpy.context.view_layer.update()
    mw = obj.matrix_world; inv = mw.inverted()
    o = inv @ Vector((x, -3.0, z)); d = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    hit, loc, nor, _ = obj.ray_cast(o, d)
    assert hit, ("raycast falló", x, z)
    p = mw @ loc
    n = (mw.to_3x3().inverted().transposed() @ nor).normalized()
    up = Vector((0, 0, 1)); y = (up - n * n.dot(up)).normalized(); xx = y.cross(n)
    return p, Matrix((xx, y, n)).transposed()


def place(o, p, R, out, depth, parent):
    o.matrix_world = Matrix.Translation(p + R.col[2] * (out - depth)) @ R.to_4x4()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()


def build():
    remove_prefix("Raccoon_")
    coll = collection("Raccoon")
    M = dict(fur=material("Raccoon_Fur", COL["fur"]), cream=material("Raccoon_Cream", COL["cream"]),
             slate=material("Raccoon_Slate", COL["slate"]), ink=material("Raccoon_Ink", COL["ink"], 0.35))
    neck = Vector(P["neck"])

    # Cabeza: bola con el hocico en colina desplazado hacia delante, remallada y suavizada
    bm = bmesh.new()
    ellipsoid(bm, P["head_r"], Vector(P["head_c"]) - neck, 160, 120)
    zn, zt = P["muz_z"], P["muz_top"]
    for v in bm.verts:                            # mejillas más anchas (gaussiana en altura)
        z = v.co.z + neck.z
        v.co.x *= 1 + P["cheek_w"] * math.exp(-((z - P["cheek_z"]) / P["cheek_sigma"]) ** 2)
    for v in bm.verts:
        if v.co.y >= 0:
            continue
        z = v.co.z + neck.z
        if z >= zn:
            t = min((z - zn) / (zt - zn), 1.0)
            a = (1 - t) ** 1.4
            w = P["muz_w_nose"] + (P["muz_w_top"] - P["muz_w_nose"]) * t
        else:
            t = (zn - z) / P["muz_drop"]
            a = 1 - smoothstep(0, 1, t)
            w = P["muz_w_nose"] * (1 + 0.3 * min(t, 1))
        u = abs(v.co.x) / w
        b = (1 - u * u) ** 2 if u < 1 else 0.0
        disp = P["muz_h"] * a * b * smoothstep(0, 0.15, -v.co.y)
        v.co.y -= disp
        v.co.z += P["muz_lift"] * (disp / P["muz_h"]) ** 2     # la punta del hocico se va hacia arriba
    head = new_obj("Raccoon_Head", bm, coll, M["fur"], neck)
    r = head.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = P["voxel"]
    s = head.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.8; s.iterations = 20
    bake_modifiers(head)

    # Ojos (sin pupila) y párpados pesados
    for side, sx in (("L", 1), ("R", -1)):
        p, R = frame_on(head, sx * P["eye_x"], P["eye_z"])
        er, ery, ed = P["eye_r"], P["eye_ry"], P["eye_d"]
        bm = bmesh.new(); ellipsoid(bm, (er, ery, ed), seg=48, rings=32)
        eye = new_obj(f"Raccoon_Eye_{side}", bm, coll, M["cream"])
        place(eye, p, R, P["eye_out"], ed, head)

        k = P["lid_scale"]; t = math.radians(P["lid_tilt"])
        bm = bmesh.new(); ellipsoid(bm, (er * k, ery * k, ed * 1.12), seg=96, rings=72)
        nrm = Vector((sx * math.sin(t), math.cos(t), 0))
        # Borde inferior plano: los vértices bajo el plano se proyectan sobre él (sin cortar ni rellenar)
        co = Vector((0, P["lid_cut"] * ery, 0))
        for v in bm.verts:
            d = (v.co - co).dot(nrm)
            if d < 0:
                v.co -= nrm * d
        lid = new_obj(f"Raccoon_Lid_{side}", bm, coll, M["fur"])
        place(lid, p, R, P["eye_out"], ed, head)

    # Nariz: botón ovalado plano; la parte de arriba es más recta y más saliente que la de abajo,
    # y el botón mira ligeramente hacia arriba
    tip = min((v.co for v in head.data.vertices if abs(v.co.x) < 0.01), key=lambda c: c.y)
    p, R = frame_on(head, 0.0, tip.z + head.location.z)   # botón en la punta más adelantada
    R = R @ Matrix.Rotation(math.radians(-P["nose_up"]), 3, 'X')
    bm = bmesh.new(); ellipsoid(bm, P["nose_r"], seg=48, rings=32)
    for v in bm.verts:
        if v.co.y > 0:
            v.co.y *= 0.75
        elif v.co.z > 0:
            v.co.z *= 1 - (1 - P["nose_low"]) * (-v.co.y / P["nose_r"][1])
    nose = new_obj("Raccoon_Nose", bm, coll, M["ink"])
    place(nose, p, R, P["nose_out"], P["nose_r"][2], head)

    # Orejas: triángulo redondeado con grosor, base enterrada en la cabeza; concavidad pizarra
    # de la punta a la base con un borde (padding) alrededor. Local: x ancho, z alto, -y = frente.
    outline = rounded_triangle(P["ear_w"], P["ear_h"], -P["ear_bury"], P["ear_round"])
    T = P["ear_t"]
    for side, sx in (("L", 1), ("R", -1)):
        bm = bmesh.new()
        vs = [bm.verts.new((x, -T / 2, z)) for x, z in outline]
        f = bm.faces.new(vs)
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, vec=(0, T, 0), verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bx, by, bz = P["ear_base"]
        ear = new_obj(f"Raccoon_Ear_{side}", bm, coll, M["fur"], (sx * bx, by, bz))
        ear.data.materials.append(M["slate"])
        ear.data.materials.append(M["cream"])
        r = ear.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = 0.0025
        sm = ear.modifiers.new("Smooth", 'SMOOTH'); sm.factor = 0.8; sm.iterations = 40
        bake_modifiers(ear)
        me = ear.data
        d = polygon_sdf(outline, [(v.co.x, v.co.z) for v in me.vertices])
        pad = P["ear_pad"]
        # Concavidad suave, como media palta sin semilla
        import numpy as np
        front = np.array([v.co.y < -T * 0.25 for v in me.vertices])
        disp = np.array([P["ear_cup"] * smoothstep(0, P["ear_bowl"], -(dv + pad)) for dv in d]) * front
        ev = np.array([(e.vertices[0], e.vertices[1]) for e in me.edges])
        deg = np.bincount(ev.ravel(), minlength=len(disp)).astype(float)
        for _ in range(60):                       # suaviza el campo de hundimiento (sin pliegues)
            acc = np.zeros_like(disp)
            np.add.at(acc, ev[:, 0], disp[ev[:, 1]]); np.add.at(acc, ev[:, 1], disp[ev[:, 0]])
            disp = np.where(front, 0.5 * disp + 0.5 * acc / np.maximum(deg, 1), 0.0)
        for v, dz in zip(me.vertices, disp):
            v.co.y += float(dz)
        me.update()
        dc = polygon_sdf(outline, [(pl.center.x, pl.center.z) for pl in me.polygons])
        for pl, dv in zip(me.polygons, dc):
            if pl.normal.y < -0.2 and dv < -pad * 0.75:
                pl.material_index = 1                 # interior pizarra
            elif pl.normal.y < 0.35 and dv > -pad * 0.75 and pl.center.z > P["ear_rim_from"]:
                pl.material_index = 2                 # borde claro (como un mapache real)
            else:
                pl.material_index = 0
        # Curva sutil hacia delante, creciente hacia la punta
        for v in me.vertices:
            t = max(v.co.z, 0.0) / P["ear_h"]
            v.co.y -= P["ear_bend"] * t * t
        me.update()
        ear.rotation_euler = (math.radians(-P["ear_back"]), math.radians(sx * P["ear_tilt"]), math.radians(sx * P["ear_yaw"]))
        ear.parent = head; ear.matrix_parent_inverse = head.matrix_world.inverted()

    bpy.context.view_layer.update()
    return head


build()
