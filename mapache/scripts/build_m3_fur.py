# M3 — Púas de pelo de la cabeza, como las escamas de una piña (highsfield3).
# - Cara lisa (zona frontal sin púas).
# - Escamas en espiral de Fibonacci (filas alternas, como una piña), en forma de hoja: la base apoyada
#   en la cabeza y la punta levantada. Fluyen desde la frente hacia atrás y hacia abajo.
# - Cerca del contorno de la cara se levantan más (anillo que da la silueta erizada de frente).
# - Copete de púas altas arriba, entre las orejas.
# Ejecutar en Blender después de M1/M2:
#   exec(open(r"C:\APPS\Renders\mapache\scripts\build_m3_fur.py", encoding="utf-8").read())
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

F = dict(
    head_c=(0.0, 0.0, 1.38), head_r=(0.43, 0.37, 0.40),
    rows=dict(step=24.0, density=15.0, use=False),  # (desactivado) filas de piña por toda la cabeza
    # Nuca: 2 filas cortas y planas que caen hacia el cuello (q.z de la fila, cuántas, apertura ± en grados desde atrás)
    nape=dict(rows=((-0.28, 7, 70.0), (-0.56, 8, 80.0)), len=0.15, r=0.09, flat=0.55, tip=0.42, lift=8.0, curl=0.05),
    droop=0.15,                                   # caída por gravedad: fracción del largo que baja la punta
    seed=7,
    face_axis=(0.0, -1.0, -0.15), face_deg=45.0,      # zona lisa mínima; el resto lo marca face_objs
    face_objs=("Raccoon_Brow", "Raccoon_Beard", "Raccoon_Eye_L", "Raccoon_Eye_R", "Raccoon_Lid_L", "Raccoon_Lid_R"),
    face_margin=0.07,
    ring_deg=(98.0, 120.0),                            # transición: escamas más levantadas cerca del anillo
    ring=dict(phis=(202.0, 216.0, 230.0, 310.0, 324.0, 338.0), front=0.0, len=0.15, r=0.09, tip=0.36, back=0.0, down=0.55, flat=1.0),  # mejillas: como el collar, hacia abajo y algo hacia fuera
    neck_z=-0.80,                                     # por debajo (q.z) no hay escamas: cuello
    source=(0.0, 0.9, 0.45),                          # el pelo nace arriba-atrás: en los lados la punta mira hacia delante
    ear_dir=(0.63, 0.0, 0.65), ear_clear=0.16,        # sin escamas sobre la base de las orejas
    crown_clear=0.13,
    scale_len=(0.19, 0.23), scale_r=(0.10, 0.115), scale_flat=0.8, scale_tip=0.42, scale_curl=0.09,
    lift_back=16.0, lift_ring=30.0,                   # grados que la escama se levanta sobre la superficie
    sink=0.45,                                        # fracción del radio hundida en la cabeza
    # copete: (dirección desde el centro, largo, radio, inclinación hacia atrás en grados)
    crown=[((0.0, -0.10, 1.0), 0.14, 0.095, 15.0),
           ((-0.20, -0.02, 0.97), 0.11, 0.085, 22.0), ((0.20, -0.02, 0.97), 0.11, 0.085, 22.0)],
    crown_tip=0.36, crown_flat=1.0,
    voxel=0.0045, smooth=14,
)


def _surface(q):
    c, r = Vector(F["head_c"]), Vector(F["head_r"])
    q = q.normalized()
    k = 1.0 / math.sqrt((q.x / r.x) ** 2 + (q.y / r.y) ** 2 + (q.z / r.z) ** 2)
    p = c + q * k
    n = Vector(((p.x - c.x) / r.x ** 2, (p.y - c.y) / r.y ** 2, (p.z - c.z) / r.z ** 2)).normalized()
    head = bpy.data.objects.get("Raccoon_Head")
    if head:                                      # ajustar a la malla real (mejillas ensanchadas)
        inv = head.matrix_world.inverted()
        o = inv @ (c + q * 2.0); dvec = (inv.to_3x3() @ (-q)).normalized()
        hit, loc, nor, _ = head.ray_cast(o, dvec)
        if hit:
            p = head.matrix_world @ loc
            n = (head.matrix_world.to_3x3().inverted().transposed() @ nor).normalized()
    return p, n


def _spike(bm, p, n, axis, length, radius, flat, tip, sink, curl=0.0, droop=None):
    """Hoja/púa: elipsoide afilado a lo largo de 'axis', aplanado según la normal."""
    z = axis.normalized()
    y = (n - z * n.dot(z)).normalized()           # eje 'grosor' (hacia fuera de la cabeza)
    x = y.cross(z)
    R = Matrix((x, y, z)).transposed()
    origin = p - n * radius * flat * sink
    g = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=14, radius=1.0)
    for v in g['verts']:
        t = (v.co.z + 1) / 2                      # 0 base, 1 punta
        k = tip + (1 - tip) * (1 - t ** 1.6) ** 0.9 if t < 0.92 else 0.0   # cachito: base ancha, punta roma
        k = max(k, 0.0) if t < 1.0 else 0.0
        if t >= 0.92:                                                      # cúpula redonda en la punta
            k = tip * math.sqrt(max(0.0, 1 - ((t - 0.92) / 0.08) ** 2))
        loc = Vector((v.co.x * radius * k, v.co.y * radius * flat * k + curl * t * t, t * length - 0.15 * length))
        v.co = origin + R @ loc + Vector((0, 0, -1)) * (F["droop"] if droop is None else droop) * length * t * t


def _on_face(p, objs):
    """¿El punto cae (con margen) delante de la ceja, la barba, los ojos o los párpados?"""
    m = F["face_margin"]
    for dx, dz in ((0, 0), (m, 0), (-m, 0), (0, m), (0, -m)):
        for o in objs:
            inv = o.matrix_world.inverted()
            hit, *_ = o.ray_cast(inv @ Vector((p.x + dx, -3.0, p.z + dz)), (inv.to_3x3() @ Vector((0, 1, 0))).normalized())
            if hit:
                return True
    return False


def build():
    old = bpy.data.objects.get("Raccoon_HeadFur")
    if old:
        bpy.data.objects.remove(old)
    head = bpy.data.objects["Raccoon_Head"]
    coll = bpy.data.collections["Raccoon"]
    rnd = random.Random(F["seed"])
    fa = Vector(F["face_axis"]).normalized()
    src = Vector(F["source"]).normalized()
    ears = [Vector(F["ear_dir"]).normalized(), Vector((-F["ear_dir"][0],) + tuple(F["ear_dir"][1:])).normalized()]
    crown_dirs = [Vector(c[0]).normalized() for c in F["crown"]]
    bpy.context.view_layer.update()
    face_objs = [bpy.data.objects[n] for n in F["face_objs"] if n in bpy.data.objects]
    bm = bmesh.new()
    n_sc = 0
    # Filas concéntricas alrededor de 'source', alternadas medio paso y simétricas izquierda/derecha
    e1 = Vector((1, 0, 0)); e2 = src.cross(e1).normalized()
    pts = []
    k = 0
    while F["rows"]["use"] and k * F["rows"]["step"] <= 180:
        th = math.radians(k * F["rows"]["step"])
        nk = max(1, round(F["rows"]["density"] * math.sin(th)))
        off = 0.5 if k % 2 else 0.0
        for j in range(nk):
            ph = 2 * math.pi * (j + off) / nk
            pts.append(src * math.cos(th) + (e2 * math.cos(ph) + e1 * math.sin(ph)) * math.sin(th))
        k += 1
    for q in pts:
        ang = math.degrees(q.angle(fa))
        if ang < F["ring_deg"][0] or q.z < F["neck_z"]:
            continue
        if q.y < 0.15 and _on_face(_surface(q)[0], face_objs):
            continue
        if any((q - e).length < F["ear_clear"] for e in ears) or any((q - c).length < F["crown_clear"] for c in crown_dirs):
            continue
        p, n = _surface(q)
        d = (q - src); d = d - n * d.dot(n)
        if d.length < 1e-3:                       # escama central de las filas: sale recta hacia fuera
            d = Vector((0, 0, -1)); d = (d - n * d.dot(n))
        d = d.normalized()                        # flujo: se aleja del centro de las filas
        r0, r1 = F["ring_deg"]
        w = 1 - min(max((ang - r0) / (r1 - r0), 0), 1)       # 1 en el anillo, 0 detrás
        lift = math.radians(F["lift_back"] + (F["lift_ring"] - F["lift_back"]) * w)
        axis = d * math.cos(lift) + n * math.sin(lift)
        L = sum(F["scale_len"]) / 2 * (1 - 0.3 * w)
        rr = sum(F["scale_r"]) / 2
        _spike(bm, p, n, axis, L, rr, F["scale_flat"], F["scale_tip"], F["sink"], F["scale_curl"])
        n_sc += 1
    # Nuca: filas cortas que caen hacia el cuello (alternadas medio paso, simétricas)
    nq = F["nape"]
    for ri, (zq, cnt, spread) in enumerate(nq["rows"]):
        rxy = math.sqrt(1 - zq * zq)
        for j in range(cnt):
            f = (j + (0.5 if ri % 2 else 0.0)) / (cnt - (0 if ri % 2 else 1)) if cnt > 1 else 0.5
            az = math.radians(-spread + 2 * spread * f)
            q = Vector((math.sin(az) * rxy, math.cos(az) * rxy, zq))
            p, n = _surface(q)
            dvec = Vector((0, 0, -1)); dvec = (dvec - n * dvec.dot(n)).normalized()
            lift = math.radians(nq["lift"])
            axis = dvec * math.cos(lift) + n * math.sin(lift)
            _spike(bm, p, n, axis, nq["len"], nq["r"], nq["flat"], nq["tip"], F["sink"], nq["curl"])
            n_sc += 1
    # Anillo regular de púas alrededor de la cara (silueta de frente)
    rg = F["ring"]
    for deg in rg["phis"]:
        ph = math.radians(deg)
        q = Vector((math.cos(ph), rg["front"], math.sin(ph))).normalized()
        if any((q - e).length < F["ear_clear"] for e in ears) or any((q - c).length < F["crown_clear"] for c in crown_dirs):
            continue
        p, n = _surface(q)
        radial = Vector((math.cos(ph), 0, math.sin(ph)))          # hacia fuera en el plano de la vista frontal
        axis = (radial + Vector((0, rg["back"], -rg["down"]))).normalized()
        _spike(bm, p, n, axis, rg["len"], rg["r"], rg["flat"], rg["tip"], 0.6, 0.03)
        n_sc += 1
    for (dq, L, rr, back) in F["crown"]:
        p, n = _surface(Vector(dq))
        bdir = Vector((0, 1, 0)); bdir = (bdir - n * bdir.dot(n)).normalized()
        axis = n * math.cos(math.radians(back)) + bdir * math.sin(math.radians(back))
        _spike(bm, p, n, axis, L, rr, F["crown_flat"], F["crown_tip"], 0.6, 0.03)
    me = bpy.data.meshes.new("Raccoon_HeadFur"); bm.to_mesh(me); bm.free()
    me.materials.append(head.data.materials[0])
    o = bpy.data.objects.new("Raccoon_HeadFur", me); coll.objects.link(o)
    r = o.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = F["voxel"]
    s = o.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.7; s.iterations = F["smooth"]
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); oldm = o.data; o.data = new; bpy.data.meshes.remove(oldm)
    new.shade_smooth()
    o.parent = head; o.matrix_parent_inverse = head.matrix_world.inverted()
    return {"scales": n_sc, "verts": len(new.vertices)}


m3_stats = build()
