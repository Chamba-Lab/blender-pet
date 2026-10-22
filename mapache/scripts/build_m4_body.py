# M4 — Cuerpo: torso en forma de pera, piernas, pies con dedos (una sola pieza) y brazos con manos
# de 3 dedos, fundidos en vivo con el cuerpo (Geometry Nodes + Remesh + Smooth), como el conejo.
# Además, la "V" crema del pecho. Referencia: highsfield1.
#   exec(open(bpy.path.abspath("//scripts/build_m4_body.py"), encoding="utf-8").read())
import bpy, bmesh, math
from mathutils import Vector, Matrix

B = dict(
    # torso: anillos (z, rx, ry, desplazamiento y del centro; -y = hacia delante, barriga)
    torso=[(0.25, 0.19, 0.16, -0.01), (0.30, 0.27, 0.23, -0.035), (0.39, 0.32, 0.30, -0.06),
           (0.50, 0.335, 0.32, -0.075), (0.65, 0.31, 0.295, -0.07), (0.80, 0.27, 0.245, -0.08),
           (0.92, 0.20, 0.195, -0.11), (1.04, 0.15, 0.15, -0.135)],
    torso_p=2.2,                                  # superelipse de la sección
    leg=dict(x=0.165, z0=0.07, z1=0.36, r=0.125, r_ankle=0.10),
    foot=dict(c=(0.172, -0.10, 0.075), r=(0.125, 0.15, 0.085), p=2.6,    # pie liso tipo zapato; sin talón (solo hacia delante)
              toes=(), toe_r=0.0, toe_y=0.0, toe_z=0.0,
              sole=0.012),                       # planta plana a esta altura
    # brazo: curva (Bézier) que nace dentro del torso; radio grueso arriba que se estrecha a la muñeca
    arm=dict(shoulder=(0.21, -0.07, 0.80), ctrl=(0.19, -0.045, -0.12), wrist=(0.22, -0.035, -0.32),
             radii=(0.10, 0.108, 0.10, 0.088), dir=(0.3, -0.05, -1.0),
             palm=(0.098, 0.082, 0.095), fingers=3, finger_len=0.012, finger_r=0.034, finger_curl=0.15, finger_gap=1.85,
             finger_in=0.12),                    # patita: dedos insinuados que se curvan hacia la pierna
    chest_v=[(-0.12, 0.905), (-0.06, 0.885), (0.0, 0.915), (0.06, 0.885), (0.12, 0.905),
             (0.05, 0.825), (0.0, 0.775), (-0.05, 0.825)],
    chest_thick=0.012,
    voxel=0.007, smooth=25,
    # postura encorvada: la cabeza (y todo lo que cuelga de ella) avanza, baja y se inclina hacia delante
    posture=dict(head_loc=(0.0, -0.115, 0.925), head_tilt=10.0),
    # colores en vivo (atributos 'belly' y 'paw' que mezcla el material Raccoon_Fur)
    belly=dict(cz=0.50, ax=0.21, az=0.24, col="#424660"),
    paw=dict(col="#171925", reach=0.06),
)


def _mat(name):
    return bpy.data.materials[name]


def _ellipsoid(bm, c, r, seg=32, rings=20):
    g = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in g['verts']:
        v.co = Vector((c[0] + v.co.x * r[0], c[1] + v.co.y * r[1], c[2] + v.co.z * r[2]))


def _superellipsoid(bm, c, r, p, seg=48, rings=32):
    """Bloque redondeado (|x|^p + |y|^p + |z|^p = 1): zapato liso."""
    g = bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in g['verts']:
        q = v.co.normalized()
        k = (abs(q.x) ** p + abs(q.y) ** p + abs(q.z) ** p) ** (-1 / p)
        v.co = Vector((c[0] + q.x * k * r[0], c[1] + q.y * k * r[1], c[2] + q.z * k * r[2]))


def _capsule(bm, a, b, ra, rb, seg=24):
    """Tubo redondeado de a a b (radios ra -> rb) hecho con esferas encadenadas (se funde al remallar)."""
    a, b = Vector(a), Vector(b)
    n = max(2, int((b - a).length / (min(ra, rb) * 0.2)))
    for i in range(n + 1):
        t = i / n
        r = ra + (rb - ra) * t
        _ellipsoid(bm, a.lerp(b, t), (r, r, r), seg, 14)


def _interp_rings(rings, per=6):
    """Catmull-Rom entre los aros de control: sección suave, sin bandas."""
    out = []
    P = [rings[0]] + list(rings) + [rings[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(per):
            t = k / per
            out.append(tuple(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t * t
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t ** 3) for c in range(4)))
    out.append(rings[-1])
    return out


def _torso(bm):
    rings = _interp_rings(B["torso"]); p = B["torso_p"]; N = 64
    vrings = []
    for z, rx, ry, cy in rings:
        ring = []
        for k in range(N):
            a = 2 * math.pi * k / N
            c, s = math.cos(a), math.sin(a)
            x = rx * math.copysign(abs(c) ** (2 / p), c); y = ry * math.copysign(abs(s) ** (2 / p), s)
            ring.append(bm.verts.new((x, y + cy, z)))
        vrings.append(ring)
    for r0, r1 in zip(vrings[:-1], vrings[1:]):
        for k in range(N):
            bm.faces.new((r0[k], r0[(k + 1) % N], r1[(k + 1) % N], r1[k]))
    for ring, z in ((vrings[0], rings[0][0] - 0.06), (vrings[-1], rings[-1][0] + 0.05)):
        cv = bm.verts.new((0, sum(v.co.y for v in ring) / N, z))
        for k in range(N):
            f = bm.faces.new((ring[k], ring[(k + 1) % N], cv))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def _arm_mesh(side):
    A = B["arm"]; sx = 1 if side == "L" else -1
    bm = bmesh.new()
    hand = bm.verts.layers.float.new("hand")       # 0 = brazo, 1 = mano (guante oscuro)
    p0 = Vector((0, 0, 0)); p1 = Vector((A["ctrl"][0] * sx, A["ctrl"][1], A["ctrl"][2]))
    p2 = Vector((A["wrist"][0] * sx, A["wrist"][1], A["wrist"][2]))
    rr = A["radii"]; n = 40
    for i in range(n + 1):
        t = i / n
        c = p0 * (1 - t) ** 2 + p1 * 2 * t * (1 - t) + p2 * t * t
        k = t * (len(rr) - 1); j = min(int(k), len(rr) - 2); f = k - j
        r = rr[j] * (1 - f) + rr[j + 1] * f
        nv = len(bm.verts)
        _ellipsoid(bm, c, (r, r, r), 24, 14)
        bm.verts.ensure_lookup_table()
        for v in bm.verts[nv:]:
            u = min(max((t - 0.55) / 0.45, 0.0), 1.0)
            v[hand] = u * u * (3 - 2 * u)               # el guante se funde a lo largo del antebrazo
    end = p2
    d = (p2 - p1).normalized()
    # mano: palma + 3 dedos cortos que bajan y se curvan un poco hacia delante
    pc = end + d * A["palm"][2] * 0.6
    g = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1.0)
    zz = d; xx = Vector((1, 0, 0)) * sx; xx = (xx - zz * xx.dot(zz)).normalized(); yy = zz.cross(xx)
    for v in g['verts']:      # palma: delgada hacia el cuerpo (x), ancha de delante a atrás (y)
        v.co = pc + xx * v.co.x * A["palm"][1] + yy * v.co.y * A["palm"][0] + zz * v.co.z * A["palm"][2]
    side_v = Vector((1, 0, 0)) * sx
    for i in range(A["fingers"]):
        off = (i - (A["fingers"] - 1) / 2) * A["finger_r"] * A["finger_gap"]
        base = pc + d * A["palm"][2] * 0.62 + Vector((0, off, 0)) - side_v * 0.008
        tipdir = (d + Vector((0, -A["finger_curl"], 0)) - side_v * A["finger_in"]).normalized()
        _capsule(bm, base, base + tipdir * A["finger_len"], A["finger_r"], A["finger_r"] * 0.85)
    for v in bm.verts:                              # palma y dedos -> guante completo
        if (v.co - pc).length < max(A["palm"]) * 1.6:
            v[hand] = 1.0
    return bm


def _fuse_group():
    ng = bpy.data.node_groups.get("Raccoon_FuseArms")
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("Raccoon_FuseArms", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new('NodeGroupInput'); go = ng.nodes.new('NodeGroupOutput')
    join = ng.nodes.new('GeometryNodeJoinGeometry')
    ng.links.new(gi.outputs[0], join.inputs[0])
    for i, side in enumerate(("L", "R")):
        oi = ng.nodes.new('GeometryNodeObjectInfo')
        oi.transform_space = 'RELATIVE'
        oi.inputs['Object'].default_value = bpy.data.objects[f"Raccoon_Arm_{side}"]
        ng.links.new(oi.outputs['Geometry'], join.inputs[0])
    ng.links.new(join.outputs[0], go.inputs[0])
    return ng


def _chest_v(body, coll):
    """'V' crema proyectada desde delante sobre el cuerpo ya fundido."""
    old = bpy.data.objects.get("Raccoon_ChestV")
    if old:
        bpy.data.objects.remove(old)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    # rejilla densa dentro del polígono -> proyectada -> relieve fino
    poly = B["chest_v"]
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    def inside(x, z):
        c = False
        for (x1, z1), (x2, z2) in zip(poly, poly[1:] + poly[:1]):
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1 + 1e-12) + x1:
                c = not c
        return c
    step = 0.004
    bm = bmesh.new(); grid = {}
    nx = int((max(xs) - min(xs)) / step) + 2; nz = int((max(zs) - min(zs)) / step) + 2
    inv = body.matrix_world.inverted()
    for i in range(nx):
        for j in range(nz):
            x = min(xs) + i * step; z = min(zs) + j * step
            hit, loc, nor, _ = ev.ray_cast(inv @ Vector((x, -3, z)), (inv.to_3x3() @ Vector((0, 1, 0))).normalized(), depsgraph=dg)
            if hit:
                p = body.matrix_world @ loc
                grid[(i, j)] = bm.verts.new((x, p.y - B["chest_thick"], z))
    for i in range(nx - 1):
        for j in range(nz - 1):
            cx = min(xs) + (i + 0.5) * step; cz = min(zs) + (j + 0.5) * step
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if inside(cx, cz) and all(k in grid for k in q):
                bm.faces.new([grid[k] for k in q])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    me = bpy.data.meshes.new("Raccoon_ChestV"); bm.to_mesh(me); bm.free()
    me.materials.append(_mat("Raccoon_Cream"))
    o = bpy.data.objects.new("Raccoon_ChestV", me); coll.objects.link(o)
    sw = o.modifiers.new("Shrinkwrap", 'SHRINKWRAP'); sw.target = body
    sw.wrap_method = 'NEAREST_SURFACEPOINT'; sw.offset = B["chest_thick"] * 0.5   # sigue la curva del cuerpo
    so = o.modifiers.new("Solidify", 'SOLIDIFY'); so.thickness = B["chest_thick"] + 0.01; so.offset = 0.0
    r = o.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = 0.003
    s = o.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.8; s.iterations = 10
    new = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    o.modifiers.clear(); oldm = o.data; o.data = new; bpy.data.meshes.remove(oldm); new.shade_smooth()
    o.parent = body; o.matrix_parent_inverse = body.matrix_world.inverted()
    return o


def _hexlin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def _color_group():
    """Atributos en vivo sobre el cuerpo fundido: 'belly' (óvalo frontal difuminado) y 'paw' (guantes)."""
    ng = bpy.data.node_groups.get("Raccoon_BodyColor")
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("Raccoon_BodyColor", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    pos = N.new('GeometryNodeInputPosition'); nor = N.new('GeometryNodeInputNormal')
    sp = N.new('ShaderNodeSeparateXYZ'); L.new(pos.outputs[0], sp.inputs[0])
    sn = N.new('ShaderNodeSeparateXYZ'); L.new(nor.outputs[0], sn.inputs[0])

    def math_(op, a, b=None):
        m = N.new('ShaderNodeMath'); m.operation = op
        for k, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[k].default_value = x
            else:
                L.new(x, m.inputs[k])
        return m.outputs[0]

    def maprange(x, a0, a1, b0, b1):
        m = N.new('ShaderNodeMapRange'); m.interpolation_type = 'SMOOTHSTEP'; m.clamp = True
        L.new(x, m.inputs['Value'])
        m.inputs['From Min'].default_value = a0; m.inputs['From Max'].default_value = a1
        m.inputs['To Min'].default_value = b0; m.inputs['To Max'].default_value = b1
        return m.outputs['Result']

    be = B["belly"]
    u = math_('ADD', math_('POWER', math_('DIVIDE', sp.outputs['X'], be["ax"]), 2.0),
              math_('POWER', math_('DIVIDE', math_('SUBTRACT', sp.outputs['Z'], be["cz"]), be["az"]), 2.0))
    belly = math_('MULTIPLY', maprange(u, 0.55, 1.0, 1.0, 0.0), maprange(sn.outputs['Y'], -0.05, -0.45, 0.0, 1.0))
    st1 = N.new('GeometryNodeStoreNamedAttribute'); st1.data_type = 'FLOAT'; st1.domain = 'POINT'
    st1.inputs['Name'].default_value = "belly"
    L.new(gi.outputs[0], st1.inputs['Geometry']); L.new(belly, st1.inputs['Value'])
    # guantes: el atributo 'hand' de los brazos, tomado del punto más cercano
    join = N.new('GeometryNodeJoinGeometry')
    for side in ("R", "L"):
        oi = N.new('GeometryNodeObjectInfo'); oi.transform_space = 'RELATIVE'
        oi.inputs['Object'].default_value = bpy.data.objects[f"Raccoon_Arm_{side}"]
        L.new(oi.outputs['Geometry'], join.inputs[0])
    near = N.new('GeometryNodeSampleNearest'); L.new(join.outputs[0], near.inputs['Geometry'])
    L.new(pos.outputs[0], near.inputs['Sample Position'])
    na = N.new('GeometryNodeInputNamedAttribute'); na.data_type = 'FLOAT'; na.inputs['Name'].default_value = "hand"
    si = N.new('GeometryNodeSampleIndex'); si.data_type = 'FLOAT'; si.domain = 'POINT'
    L.new(join.outputs[0], si.inputs['Geometry']); L.new(na.outputs['Attribute'], si.inputs['Value'])
    L.new(near.outputs['Index'], si.inputs['Index'])
    prox = N.new('GeometryNodeProximity'); L.new(join.outputs[0], prox.inputs[0])
    L.new(pos.outputs[0], prox.inputs['Sample Position'])
    paw = math_('MULTIPLY', si.outputs[0], maprange(prox.outputs['Distance'], 0.0, B["paw"]["reach"], 1.0, 0.0))
    st2 = N.new('GeometryNodeStoreNamedAttribute'); st2.data_type = 'FLOAT'; st2.domain = 'POINT'
    st2.inputs['Name'].default_value = "paw"
    blur = N.new('GeometryNodeBlurAttribute'); blur.data_type = 'FLOAT'   # sin granulado en la transición
    blur.inputs['Iterations'].default_value = 12; L.new(paw, blur.inputs['Value'])
    L.new(st1.outputs['Geometry'], st2.inputs['Geometry']); L.new(blur.outputs['Value'], st2.inputs['Value'])
    L.new(st2.outputs['Geometry'], go.inputs[0])
    return ng


def _fur_material():
    """Raccoon_Fur: color base + vientre más claro + guantes oscuros (atributos; valen 0 en las demás piezas)."""
    m = bpy.data.materials["Raccoon_Fur"]; nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for n in [n for n in nt.nodes if n.name.startswith("RC_")]:
        nt.nodes.remove(n)
    if "rc_base" not in m:
        m["rc_base"] = list(bsdf.inputs['Base Color'].default_value)
    base = tuple(m["rc_base"])
    a1 = nt.nodes.new('ShaderNodeAttribute'); a1.name = "RC_belly"; a1.attribute_name = "belly"
    a2 = nt.nodes.new('ShaderNodeAttribute'); a2.name = "RC_paw"; a2.attribute_name = "paw"
    m1 = nt.nodes.new('ShaderNodeMix'); m1.name = "RC_mix1"; m1.data_type = 'RGBA'
    m1.inputs['A'].default_value = base; m1.inputs['B'].default_value = _hexlin(B["belly"]["col"])
    nt.links.new(a1.outputs['Fac'], m1.inputs['Factor'])
    m2 = nt.nodes.new('ShaderNodeMix'); m2.name = "RC_mix2"; m2.data_type = 'RGBA'
    nt.links.new(m1.outputs['Result'], m2.inputs['A']); m2.inputs['B'].default_value = _hexlin(B["paw"]["col"])
    nt.links.new(a2.outputs['Fac'], m2.inputs['Factor'])
    nt.links.new(m2.outputs['Result'], bsdf.inputs['Base Color'])


def _posture():
    head = bpy.data.objects.get("Raccoon_Head")
    if not head:
        return
    po = B["posture"]
    head.location = po["head_loc"]
    head.rotation_euler = (math.radians(po["head_tilt"]), 0, 0)


def build_body():
    for n in ("Raccoon_Body", "Raccoon_Arm_L", "Raccoon_Arm_R", "Raccoon_ChestV"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o)
    coll = bpy.data.collections["Raccoon"]
    fur = _mat("Raccoon_Fur")
    # brazos (objetos para posar; origen en el hombro)
    for side, sx in (("L", 1), ("R", -1)):
        me = bpy.data.meshes.new(f"Raccoon_Arm_{side}"); bm = _arm_mesh(side); bm.to_mesh(me); bm.free()
        me.materials.append(fur)
        a = bpy.data.objects.new(f"Raccoon_Arm_{side}", me); coll.objects.link(a)
        sh = B["arm"]["shoulder"]
        a.location = (sh[0] * sx, sh[1], sh[2])
        a.hide_render = True; a.display_type = 'WIRE'
    # cuerpo: torso + piernas + pies (origen entre los pies, en el suelo)
    bm = bmesh.new()
    _torso(bm)
    L, Fo = B["leg"], B["foot"]
    for sx in (1, -1):
        _capsule(bm, (sx * L["x"] * 0.92, -0.03, L["z1"]), (sx * L["x"], -0.02, L["z0"]), L["r"], L["r_ankle"])  # muslo ancho -> tobillo
        c = Fo["c"]
        _superellipsoid(bm, (sx * c[0], c[1], c[2]), Fo["r"], Fo["p"])
        for dx, dy in Fo["toes"]:
            _ellipsoid(bm, (sx * c[0] + dx, Fo["toe_y"] + dy, Fo["toe_z"]), (Fo["toe_r"],) * 3, 20, 12)
    for v in bm.verts:                            # planta plana
        if v.co.z < Fo["sole"]:
            v.co.z = Fo["sole"]
    me = bpy.data.meshes.new("Raccoon_Body"); bm.to_mesh(me); bm.free()
    me.materials.append(fur)
    body = bpy.data.objects.new("Raccoon_Body", me); coll.objects.link(body)
    gn = body.modifiers.new("FuseArms", 'NODES'); gn.node_group = _fuse_group()
    r = body.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = B["voxel"]
    s = body.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.8; s.iterations = B["smooth"]
    cg = body.modifiers.new("BodyColor", 'NODES'); cg.node_group = _color_group()
    _fur_material()
    _posture()
    for side in ("L", "R"):
        a = bpy.data.objects[f"Raccoon_Arm_{side}"]
        a.parent = body; a.matrix_parent_inverse = body.matrix_world.inverted()
    bpy.context.view_layer.update()
    for side in ("L", "R"):
        bpy.data.objects[f"Raccoon_Arm_{side}"].hide_set(True)
    _chest_v(body, coll)
    return body


body = build_body()
