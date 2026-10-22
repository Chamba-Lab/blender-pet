# modeling_lib.py — piezas, material, luz y cámara para un personaje de vinilo.
# Uso dentro de Blender (MCP execute_blender_code):
#   exec(open(r"<skill>/scripts/modeling_lib.py", encoding="utf-8").read())
#   head = bun_head("Char_Head", w=1.40, h=0.96, d=0.78, loc=(0, 0, 1.52))
#   arm = capsule("Char_Arm_L", r=0.09, length=0.34, loc=(0.30, 0, 0.98))
#   set_origin(arm, (0.30, 0, 1.12))           # origen en el hombro
# Todas las medidas en metros; altura de trabajo recomendada: 2 m sin accesorios.
import bpy, bmesh, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

D = math.radians


# ---------- utilidades ----------
def hex_to_linear(h):
    """'#F4F4F2' -> (r, g, b, 1) en espacio lineal (lo que esperan los nodos)."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)


def _link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def obj_from_bmesh(name, bm, loc=(0, 0, 0), collection=None, smooth=True):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    return _link(ob, collection)


def _sphere(segments=64, rings=32, r=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=r)
    return bm


def set_origin(ob, world_point):
    """Pone el origen en una articulación sin mover la malla (para posar girando el objeto)."""
    bpy.context.view_layer.update()
    p = Vector(world_point)
    local = ob.matrix_world.inverted() @ p
    ob.data.transform(Matrix.Translation(-local))
    ob.matrix_world = Matrix.Translation(p) @ ob.matrix_world.to_3x3().to_4x4()
    bpy.context.view_layer.update()


# ---------- formas ----------
def ellipsoid(name, rx, ry, rz, loc=(0, 0, 0), segments=48, rings=24):
    bm = _sphere(segments, rings)
    bmesh.ops.scale(bm, vec=(rx, ry, rz), verts=bm.verts)
    return obj_from_bmesh(name, bm, loc)


def bun_head(name, w, h, d, p=2.4, base_flare=0.06, base_flat=0.10, loc=(0, 0, 0)):
    """Cabeza tipo "bollo": esfera normalizada a superelipse de exponente p (2 = elipsoide,
    más alto = más cuadrada) con la base algo más ancha y plana. w = ancho (X), h = alto (Z),
    d = fondo (Y). Si sale un pliegue o "cintura", cambiar los parámetros: no parchear."""
    rx, ry, rz = w / 2, d / 2, h / 2
    bm = _sphere(96, 48)
    for v in bm.verts:
        n = v.co.normalized()
        s = (abs(n.x / rx) ** p + abs(n.y / ry) ** p + abs(n.z / rz) ** p) ** (-1 / p)
        c = n * s
        if c.z < 0:                       # mitad inferior: más ancha y más plana
            k = -c.z / rz
            c.x *= 1 + base_flare * k
            c.y *= 1 + base_flare * k
            c.z *= 1 - base_flat * k
        v.co = c
    return obj_from_bmesh(name, bm, loc)


def capsule(name, r, length, loc=(0, 0, 0), flatten=1.0, belly=0.0, taper=0.0,
            segments=48, rings=24):
    """Cápsula a lo largo de Z (largo total = length + 2r). flatten < 1 aplana en Y (orejas);
    belly > 0 la ensancha en el centro; taper > 0 estrecha la punta superior."""
    bm = _sphere(segments, rings, r)
    half = length / 2
    for v in bm.verts:
        z = v.co.z
        v.co.z = z + half if z > 0 else z - half
        t = (v.co.z + half + r) / (length + 2 * r)            # 0 abajo, 1 arriba
        k = (1 + belly * math.sin(math.pi * t)) * (1 - taper * t)
        v.co.x *= k
        v.co.y *= k * flatten
    return obj_from_bmesh(name, bm, loc)


def pill(name, w, h, depth, loc=(0, 0, 0)):
    """Píldora plana (nariz, trazo de un ojo): w a lo largo de X, h en Z, depth en Y."""
    ob = capsule(name, r=h / 2, length=max(w - h, 0.0), loc=loc)
    ob.data.transform(Matrix.Rotation(D(90), 4, 'Y') @ Matrix.Diagonal((1, depth / h, 1, 1)))
    return ob


def plus_sign(name, size, stroke_ratio=0.38, depth=0.02, loc=(0, 0, 0)):
    """Ojo en '+' con puntas redondeadas (dos píldoras unidas). Para el parpadeo usar solo
    la barra horizontal: pill(name, size, size*stroke_ratio, depth)."""
    t = size * stroke_ratio
    a = pill(name, size, t, depth, loc)
    b = pill(name + "_v", size, t, depth, loc)
    b.data.transform(Matrix.Rotation(D(90), 4, 'Y'))
    return join([a, b], name)


def join(objs, name):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


# ---------- rasgos sobre la superficie ----------
def place_on_surface(feature, target, x, z, sink=0.5, from_front=-5.0):
    """Lanza un rayo desde delante (-Y) hacia la cabeza en (x, z) del mundo, coloca el rasgo
    en el impacto y alinea su eje Y local con la normal. sink = fracción del grosor que queda
    hundida dentro (≈0,5: relieve sutil). Devuelve la posición del impacto o None."""
    bpy.context.view_layer.update()
    mw = target.matrix_world
    inv = mw.inverted()
    o = inv @ Vector((x, from_front, z))
    dvec = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    hit, loc, nrm, _ = target.ray_cast(o, dvec)
    if not hit:
        return None
    p = mw @ loc
    n = (mw.to_3x3() @ nrm).normalized()
    depth = feature.dimensions.y
    q = (-n).to_track_quat('Y', 'Z')             # +Y local del rasgo apunta hacia dentro
    feature.matrix_world = Matrix.Translation(p - n * depth * (sink - 0.5)) @ q.to_matrix().to_4x4()
    bpy.context.view_layer.update()
    return tuple(p)


# ---------- uniones ----------
def voxel_union(objs, name, voxel=0.007, smooth=25, factor=0.5):
    """Funde varias piezas en una sola malla (cuerpo de una pieza: torso + cuello + piernas + pies)."""
    ob = join(objs, name)
    rm = ob.modifiers.new("Remesh", 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel
    sm = ob.modifiers.new("Smooth", 'SMOOTH')
    sm.iterations = smooth
    sm.factor = factor
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def live_fusion(body, parts, voxel=0.007, smooth=25):
    """Brazos fundidos en vivo: Geometry Nodes une `parts` (Object Info relativo) al cuerpo y
    después Remesh + Smooth. Las piezas siguen siendo objetos para posar, pero ocultas."""
    ng = bpy.data.node_groups.new(body.name + "_Fusion", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new('NodeGroupInput')
    go = ng.nodes.new('NodeGroupOutput')
    jn = ng.nodes.new('GeometryNodeJoinGeometry')
    ng.links.new(gi.outputs[0], jn.inputs[0])
    for i, part in enumerate(parts):
        oi = ng.nodes.new('GeometryNodeObjectInfo')
        oi.transform_space = 'RELATIVE'
        oi.inputs['Object'].default_value = part
        oi.location = (-300, -150 * (i + 1))
        ng.links.new(oi.outputs['Geometry'], jn.inputs[0])
        part.hide_set(True)
        part.hide_render = True
    ng.links.new(jn.outputs[0], go.inputs[0])
    gn = body.modifiers.new("Fusion", 'NODES')
    gn.node_group = ng
    rm = body.modifiers.new("Remesh", 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel
    sm = body.modifiers.new("Smooth", 'SMOOTH')
    sm.iterations = smooth
    return gn


# ---------- medidas y choques ----------
def bvh(ob, zmax=None):
    """BVH de la malla evaluada en coordenadas del mundo (zmax: ignorar caras por encima)."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    vs = [oe.matrix_world @ v.co for v in me.vertices]
    fs = [tuple(p.vertices) for p in me.polygons
          if zmax is None or sum(vs[i].z for i in p.vertices) / len(p.vertices) < zmax]
    tree = BVHTree.FromPolygons(vs, fs)
    oe.to_mesh_clear()
    return tree, vs


def gap(a, b):
    """Distancia mínima real entre superficies (m). 0 o casi 0 = se tocan. Nunca medir a ojo
    ni desde el eje sin restar el radio."""
    tb, _ = bvh(b)
    _, va = bvh(a)
    ds = (tb.find_nearest(v)[3] for v in va)
    return min((d for d in ds if d is not None), default=None)


def overlaps(a, b, zmax_b=None):
    """Número de pares de caras que se cruzan (objetivo: 0)."""
    return len(bvh(a)[0].overlap(bvh(b, zmax_b)[0]))


# ---------- materiales ----------
def _principled(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')  # nunca por nombre
    return m, bsdf


def vinyl(name, hex_color, roughness=0.5, subsurface=0.05):
    """Vinilo mate con subsurface leve (la luz "entra" en los bordes)."""
    m, b = _principled(name)
    b.inputs['Base Color'].default_value = hex_to_linear(hex_color)
    b.inputs['Roughness'].default_value = roughness
    b.inputs['Subsurface Weight'].default_value = subsurface
    b.inputs['Subsurface Radius'].default_value = (0.1, 0.06, 0.04)
    return m


def gummy(name, hex_color, darken=0.85):
    """Gomita: base algo más oscura + subsurface 0,45 + transmisión 0,35 + coat. Sin volumen
    (oscurece hasta el negro sobre fondo oscuro)."""
    m, b = _principled(name)
    c = hex_to_linear(hex_color)
    b.inputs['Base Color'].default_value = (c[0] * darken, c[1] * darken, c[2] * darken, 1)
    b.inputs['Roughness'].default_value = 0.3
    b.inputs['Subsurface Weight'].default_value = 0.45
    b.inputs['Transmission Weight'].default_value = 0.35
    b.inputs['Coat Weight'].default_value = 0.5
    return m


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


# ---------- render, luz y cámara ----------
def setup_render(res=(1200, 1600), samples=256, exposure=0.35):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = exposure
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    sc.cycles.device = 'GPU'
                    return kind
            except TypeError:
                continue
    except KeyError:
        pass
    sc.cycles.device = 'CPU'
    return 'CPU'


def shadow_floor(size=8):
    old = bpy.data.objects.get("Floor")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    ob = obj_from_bmesh("Floor", bm, smooth=False)
    ob.is_shadow_catcher = True
    return ob


def _area(name, loc, energy, size, color=(1, 1, 1), target=(0, 0, 1.0)):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    li = bpy.data.lights.new(name, 'AREA')
    li.energy, li.size, li.color = energy, size, color
    ob = _link(bpy.data.objects.new(name, li))
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def studio_lights(accent_hex="#329DA8", scale=1.0):
    """Principal arriba-izquierda, relleno derecha, cenital suave (sombra de contacto) y dos
    contraluces del color de acento (separan el personaje de un fondo oscuro)."""
    acc = hex_to_linear(accent_hex)[:3]
    return [
        _area("Light_Key", (-3, -4, 4.5), 900 * scale, 3),
        _area("Light_Fill", (4, -3, 2), 250 * scale, 4),
        _area("Light_Top", (0, 0, 6), 300 * scale, 5, target=(0, 0, 0)),
        _area("Light_Rim_L", (-3, 3.5, 2.5), 500 * scale, 1.5, acc),
        _area("Light_Rim_R", (3, 3.5, 2.5), 500 * scale, 1.5, acc),
    ]


def camera(name, lens=85, ortho_scale=None, yaw=-10, height=1.1, dist=9.0, target_z=1.0):
    """Cámara de la web: casi frontal (yaw ≈ -10°), teleobjetivo y algo baja.
    Con ortho_scale = alto del personaje × 1,16 sale la cámara de la hoja de personaje."""
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cam = bpy.data.cameras.new(name)
    if ortho_scale:
        cam.type = 'ORTHO'
        cam.ortho_scale = ortho_scale
    else:
        cam.lens = lens
    ob = _link(bpy.data.objects.new(name, cam))
    a = D(yaw)
    ob.location = (dist * math.sin(a), -dist * math.cos(a), height)
    ob.rotation_euler = (Vector((0, 0, target_z)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = ob
    return ob


def turntable(angles, render_fn, rig=None):
    """Plató giratorio: gira cámara y luces juntas alrededor de Z (no el personaje) para que
    todas las vistas tengan la misma luz. render_fn(angulo) renderiza; se restaura al final."""
    sc = bpy.context.scene
    rig = rig or [sc.camera] + [o for o in sc.objects if o.type == 'LIGHT']
    bpy.context.view_layer.update()
    saved = {o.name: o.matrix_world.copy() for o in rig}
    try:
        for ang in angles:
            R = Matrix.Rotation(D(ang), 4, 'Z')
            for o in rig:
                o.matrix_world = R @ saved[o.name]
            bpy.context.view_layer.update()
            render_fn(ang)
    finally:
        for o in rig:
            o.matrix_world = saved[o.name]
        bpy.context.view_layer.update()
