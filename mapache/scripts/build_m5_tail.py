# M5 — Cola: bala gruesa con anillos crema en zigzag ondulado (highsfield1) y punta oscura.
# Objeto Raccoon_Tail (origen en la base, hijo del cuerpo). Las rayas son del material (coordenadas del objeto).
#   exec(open(bpy.path.abspath("//scripts/build_m5_tail.py"), encoding="utf-8").read())
import bpy, bmesh, math
from mathutils import Vector

T = dict(
    base=(0.0, 0.10, 0.33),             # bien metida en la espalda baja (sin cuello visible)
    dir=(0.0, 1.0, -0.22),              # hacia atrás y algo hacia abajo
    length=0.42,                        # chibi
    # perfil del radio a lo largo de la cola (t de 0 a 1)
    # cola de mapache: grosor casi uniforme que se afina un poco hacia la punta (una sola curva suave)
    r_base=0.10, r_bulge=0.01, r_taper=0.02,
    dome=(0.82, None),                  # desde aquí, punta redonda en cúpula
    lift=0.05, sag=0.03,               # cae por su peso en el centro y la punta se levanta un poco
    # anillos crema: tramos de t (0 = base); en medio y en la punta, pelo oscuro
    bands=((0.30, 0.47), (0.62, 0.79)),
    zig_n=7, zig_amp=0.035, edge=0.006,
    ring_col="#9C958A",                  # gris beige de los anillos de un mapache real
    voxel=0.004, smooth=10,
)


def _radius(t):
    """Grosor con una sola curva suave (sin escalones) y punta en cúpula que empalma con la misma pendiente."""
    t0 = T["dome"][0]
    def body(x):
        return T["r_base"] + T["r_bulge"] * math.sin(math.pi * x) - T["r_taper"] * x * x
    if t < t0:
        return body(t)
    u = (t - t0) / (1 - t0)
    return body(t) * math.sqrt(max(0.0, 1 - u * u))      # misma pendiente al empalmar: sin línea


def _tail_material():
    m = bpy.data.materials.get("Raccoon_Tail") or bpy.data.materials.new("Raccoon_Tail")
    m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    N.clear()
    out = N.new('ShaderNodeOutputMaterial'); bsdf = N.new('ShaderNodeBsdfPrincipled')
    fur_b = next(n for n in bpy.data.materials["Raccoon_Fur"].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    cre_b = next(n for n in bpy.data.materials["Raccoon_Cream"].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    fur_col = tuple(bpy.data.materials["Raccoon_Fur"].get("rc_base", fur_b.inputs['Base Color'].default_value))
    cre_col = tuple((int(T['ring_col'][i:i + 2], 16) / 255) for i in (1, 3, 5))
    cre_col = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in cre_col) + (1.0,)
    bsdf.inputs['Roughness'].default_value = fur_b.inputs['Roughness'].default_value
    L.new(bsdf.outputs[0], out.inputs[0])
    tc = N.new('ShaderNodeTexCoord'); sx = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sx.inputs[0])

    def math_(op, a, b=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for k, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[k].default_value = x
            else:
                L.new(x, n.inputs[k])
        return n.outputs[0]

    def step(x, a, rising=True):
        n = N.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'; n.clamp = True
        L.new(x, n.inputs['Value'])
        n.inputs['From Min'].default_value = a - T["edge"]; n.inputs['From Max'].default_value = a + T["edge"]
        n.inputs['To Min'].default_value = 0.0 if rising else 1.0; n.inputs['To Max'].default_value = 1.0 if rising else 0.0
        return n.outputs['Result']

    # w = z/L + amp * sin(n * ángulo): posición a lo largo de la cola con el zigzag ondulado
    ang = math_('ARCTAN2', sx.outputs['Y'], sx.outputs['X'])
    w = math_('ADD', math_('DIVIDE', sx.outputs['Z'], T["length"]),
              math_('MULTIPLY', math_('SINE', math_('MULTIPLY', ang, float(T["zig_n"]))), T["zig_amp"]))
    cream = None
    for a, b in T["bands"]:
        band = math_('MULTIPLY', step(w, a, True), step(w, b, False))
        cream = band if cream is None else math_('ADD', cream, band)
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = fur_col; mix.inputs['B'].default_value = cre_col
    L.new(cream, mix.inputs['Factor']); L.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    return m


def build_tail():
    old = bpy.data.objects.get("Raccoon_Tail")
    if old:
        bpy.data.objects.remove(old)
    coll = bpy.data.collections["Raccoon"]
    bm = bmesh.new()
    n_ring, n_seg = 48, 96
    def axis(t):                          # eje curvo en el plano local y-z
        return Vector((0.0, T["lift"] * t ** 3 - T["sag"] * math.sin(math.pi * t), t * T["length"]))
    rings = []
    for i in range(n_seg + 1):
        t = i / n_seg
        r = _radius(t)
        c = axis(t)
        tan = (axis(min(t + 1e-3, 1.0)) - axis(max(t - 1e-3, 0.0))).normalized()
        ex = Vector((1, 0, 0)); ey = tan.cross(ex).normalized() * -1   # marco perpendicular al eje
        if ey.dot(Vector((0, 1, 0))) < 0:
            ey = -ey
        if r < 1e-4:
            rings.append([bm.verts.new(c)])
            continue
        rings.append([bm.verts.new(c + (ex * math.cos(2 * math.pi * k / n_ring) + ey * math.sin(2 * math.pi * k / n_ring)) * r)
                      for k in range(n_ring)])
    for r0, r1 in zip(rings[:-1], rings[1:]):
        if len(r1) == 1:
            for k in range(n_ring):
                bm.faces.new((r0[k], r0[(k + 1) % n_ring], r1[0]))
        else:
            for k in range(n_ring):
                bm.faces.new((r0[k], r0[(k + 1) % n_ring], r1[(k + 1) % n_ring], r1[k]))
    cap = bm.verts.new((0, 0, -0.02))
    for k in range(n_ring):
        bm.faces.new((rings[0][(k + 1) % n_ring], rings[0][k], cap))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("Raccoon_Tail"); bm.to_mesh(me); bm.free()
    me.materials.append(_tail_material())
    o = bpy.data.objects.new("Raccoon_Tail", me); coll.objects.link(o)
    s = o.modifiers.new("Subdiv", 'SUBSURF'); s.levels = 1; s.render_levels = 2
    me.shade_smooth()
    # orientar: eje local z -> dirección de la cola; eje local y (curva de la punta) -> arriba
    d = Vector(T["dir"]).normalized()
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    o.location = T["base"]
    body = bpy.data.objects.get("Raccoon_Body")
    if body:
        bpy.context.view_layer.update()
        o.parent = body; o.matrix_parent_inverse = body.matrix_world.inverted()
    return o


tail = build_tail()
