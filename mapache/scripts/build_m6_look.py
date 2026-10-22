# M6 — material de vinilo mate, luz tipo Higgsfield, fondo transparente y suelo que recoge la sombra.
# Se ejecuta después de M1–M5. Uso en Blender:
#   exec(open(bpy.path.abspath("//scripts/build_m6_look.py"), encoding="utf-8").read()); build_m6()
#   test_render(r"...\png", yaw=25)   # render de prueba compuesto sobre #6E7F95
import bpy, math, os
import numpy as np
from mathutils import Vector, Matrix

SCRIPTS = bpy.path.abspath("//scripts")

LOOK = dict(
    # vinilo mate: rugosidad, brillo especular bajo y subsurface leve
    vinyl=dict(rough=0.55, spec=0.35, sss=0.08, sss_scale=0.03),
    ink=dict(rough=0.32, spec=0.5, coat=0.25),          # nariz: satinada
    ear_band=dict(d=0.0015, ny=0.08, z=0.005),          # anchos de la transición de color de la oreja
    # luces de área: (nombre, posición, energía W, tamaño m, color)
    lights=[
        ("Key",   (-2.6, -3.4, 4.2), 520.0, 3.0, (1.0, 0.98, 0.95)),
        ("Fill",  (3.4, -3.0, 2.2),   200.0, 4.0, (0.95, 0.97, 1.0)),
        ("Top",   (0.0, -0.4, 5.5),   160.0, 3.0, (1.0, 1.0, 1.0)),
        ("Rim_L", (-2.8, 2.8, 3.2),   260.0, 1.6, (0.85, 0.92, 1.0)),
        ("Rim_R", (2.8, 2.6, 3.0),    230.0, 1.6, (0.85, 0.92, 1.0)),
    ],
    target=(0.0, 0.0, 1.1),
    render=dict(samples=256, exposure=-0.15, res=(1200, 1600)),
    bg="#6E7F95",
    slate="#444A5F",                                   # interior de la oreja en render (antes #5D6F87)
)


def _hexlin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def _bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def _vinyl(bsdf, rough=None):
    v = LOOK["vinyl"]
    bsdf.inputs['Roughness'].default_value = v["rough"] if rough is None else rough
    bsdf.inputs['Specular IOR Level'].default_value = v["spec"]
    bsdf.inputs['Subsurface Weight'].default_value = v["sss"]
    bsdf.inputs['Subsurface Scale'].default_value = v["sss_scale"]
    bsdf.subsurface_method = 'RANDOM_WALK'


def materials():
    for name in ("Raccoon_Fur", "Raccoon_Cream", "Raccoon_Slate", "Raccoon_Tail"):
        _vinyl(_bsdf(bpy.data.materials[name]))
    sl = _bsdf(bpy.data.materials["Raccoon_Slate"])
    sl.inputs['Base Color'].default_value = _hexlin(LOOK["slate"]) + (1.0,)
    bpy.data.materials["Raccoon_Slate"].diffuse_color = _hexlin(LOOK["slate"]) + (1.0,)
    ink = _bsdf(bpy.data.materials["Raccoon_Ink"]); k = LOOK["ink"]
    ink.inputs['Roughness'].default_value = k["rough"]
    ink.inputs['Specular IOR Level'].default_value = k["spec"]
    ink.inputs['Coat Weight'].default_value = k["coat"]


def _ear_helpers():
    """Trae P, rounded_triangle y polygon_sdf de M1 sin ejecutar su build()."""
    src = open(os.path.join(SCRIPTS, "build_m1_head.py"), encoding="utf-8").read()
    src = src.rsplit("\nbuild()", 1)[0]
    g = {"__name__": "m1_helpers"}
    exec(src, g)
    return g


def ear_material():
    """Borde de color limpio en la oreja: campos continuos por vértice + umbral en el material (no por caras)."""
    g = _ear_helpers(); P = g["P"]
    outline = g["rounded_triangle"](P["ear_w"], P["ear_h"], -P["ear_bury"], P["ear_round"])
    thr = -P["ear_pad"] * 0.75
    m = ear_shader(P, thr)
    for side in ("L", "R"):
        ear = bpy.data.objects[f"Raccoon_Ear_{side}"]; me = ear.data
        d = g["polygon_sdf"](outline, [(v.co.x, v.co.z) for v in me.vertices])
        for name, vals in (("ear_d", d), ("ear_ny", [v.normal.y for v in me.vertices]),
                           ("ear_z", [v.co.z for v in me.vertices])):
            a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'POINT')
            a.data.foreach_set("value", np.asarray(vals, dtype=np.float32))
        me.materials.clear(); me.materials.append(m)
        for pl in me.polygons:
            pl.material_index = 0
        me.update()
    return m


def ear_shader(P, thr):
    m = bpy.data.materials.get("Raccoon_Ear") or bpy.data.materials.new("Raccoon_Ear")
    m.use_nodes = True; nt = m.node_tree; N, L = nt.nodes, nt.links
    N.clear()
    out = N.new('ShaderNodeOutputMaterial'); bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(bsdf.outputs[0], out.inputs[0]); _vinyl(bsdf)
    b = LOOK["ear_band"]

    def attr(name):
        n = N.new('ShaderNodeAttribute'); n.attribute_name = name; return n.outputs['Fac']

    def step(x, a, w, rising):
        n = N.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'; n.clamp = True
        L.new(x, n.inputs['Value'])
        n.inputs['From Min'].default_value = a - w; n.inputs['From Max'].default_value = a + w
        n.inputs['To Min'].default_value = 0.0 if rising else 1.0; n.inputs['To Max'].default_value = 1.0 if rising else 0.0
        return n.outputs['Result']

    def mul(a, c):
        n = N.new('ShaderNodeMath'); n.operation = 'MULTIPLY'; L.new(a, n.inputs[0]); L.new(c, n.inputs[1]); return n.outputs[0]

    d, ny, z = attr("ear_d"), attr("ear_ny"), attr("ear_z")
    slate = mul(step(d, thr, b["d"], False), step(ny, -0.2, b["ny"], False))
    rim = mul(mul(step(d, thr, b["d"], True), step(ny, 0.35, b["ny"], False)), step(z, P["ear_rim_from"], b["z"], True))
    col = lambda name: tuple(_bsdf(bpy.data.materials[name]).inputs['Base Color'].default_value)
    fur = tuple(bpy.data.materials["Raccoon_Fur"].get("rc_base", col("Raccoon_Fur")))
    m1 = N.new('ShaderNodeMix'); m1.data_type = 'RGBA'
    m1.inputs['A'].default_value = fur; m1.inputs['B'].default_value = col("Raccoon_Cream"); L.new(rim, m1.inputs['Factor'])
    m2 = N.new('ShaderNodeMix'); m2.data_type = 'RGBA'
    L.new(m1.outputs['Result'], m2.inputs['A']); m2.inputs['B'].default_value = col("Raccoon_Slate")
    L.new(slate, m2.inputs['Factor']); L.new(m2.outputs['Result'], bsdf.inputs['Base Color'])
    m.diffuse_color = col("Raccoon_Slate")
    return m


def lights():
    coll = _coll("Lights"); tgt = Vector(LOOK["target"])
    for name in [o.name for o in coll.objects if o.name.startswith("Preview_")]:
        bpy.data.objects.remove(bpy.data.objects[name])
    for name, loc, energy, size, color in LOOK["lights"]:
        name = "Light_" + name
        L = bpy.data.objects.get(name)
        if not L:
            L = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA')); coll.objects.link(L)
        L.data.shape = 'DISK'; L.data.energy = energy; L.data.size = size; L.data.color = color
        L.location = loc
        L.data.use_shadow = not name.startswith("Light_Rim")   # los contraluces no manchan el suelo
        L.rotation_euler = (tgt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


def floor():
    f = bpy.data.objects.get("Shadow_Catcher")
    if not f:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
        f = bpy.context.active_object; f.name = "Shadow_Catcher"
        for c in f.users_collection:
            c.objects.unlink(f)
        _coll("Lights").objects.link(f)
    f.is_shadow_catcher = True
    return f


def camera(yaw=25.0, dist=6.0, lens=70.0, height=1.05):
    cam = bpy.data.objects.get("Cam_Main")
    if not cam:
        cam = bpy.data.objects.new("Cam_Main", bpy.data.cameras.new("Cam_Main")); _coll("Cameras").objects.link(cam)
    cam.data.type = 'PERSP'; cam.data.lens = lens
    r = math.radians(yaw); tgt = Vector((0, 0, height))
    cam.location = tgt + Vector((math.sin(r) * dist, -math.cos(r) * dist, 0.35))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_settings():
    sc = bpy.context.scene; R = LOOK["render"]
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        sc.cycles.device = 'GPU'
    except Exception:
        sc.cycles.device = 'CPU'
    sc.cycles.samples = R["samples"]; sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'None'
    sc.view_settings.exposure = R["exposure"]
    sc.render.resolution_x, sc.render.resolution_y = R["res"]; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = _hexlin(LOOK["bg"]) + (1.0,); bg.inputs['Strength'].default_value = 0.15


def build_m6():
    materials(); ear_material(); lights(); floor(); camera(); render_settings()
    bpy.context.view_layer.update()


def test_render(out_png, yaw=25.0, **cam_kw):
    """Render RGBA (transparente) + vista compuesta sobre el fondo de presentación (<nombre>-bg.png)."""
    sc = bpy.context.scene; camera(yaw=yaw, **cam_kw)
    sc.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(out_png); im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4); bpy.data.images.remove(im)
    bg = np.array([int(LOOK["bg"][i:i + 2], 16) / 255 for i in (1, 3, 5)], dtype=np.float32)
    rgb = a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:])
    lum = (a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[a[..., 3] > 0.99]
    out = bpy.data.images.new("_bg", w, h, alpha=False); out.colorspace_settings.name = 'Non-Color'
    out.pixels.foreach_set(np.dstack([rgb, np.ones((h, w, 1), np.float32)]).ravel())
    p2 = out_png[:-4] + "-bg.png"; out.filepath_raw = p2; out.file_format = 'PNG'; out.save()
    bpy.data.images.remove(out)
    return dict(png=out_png, bg=p2, lum_p50=float(np.percentile(lum, 50)), lum_p99=float(np.percentile(lum, 99)))


def test_strip(out_png, yaws=(0, 35, 90, 180), pct=50):
    """Plató giratorio: cámara y luces giran juntas alrededor de Z (misma luz en todas las vistas). Tira sobre el fondo."""
    sc = bpy.context.scene; old_pct = sc.render.resolution_percentage; sc.render.resolution_percentage = pct
    lights_ = [o for o in bpy.data.collections["Lights"].objects if o.type == 'LIGHT']
    rest = {o.name: o.matrix_world.copy() for o in lights_}
    tiles, tmp = [], out_png[:-4] + "_tmp.png"
    try:
        for y in yaws:
            R = Matrix.Rotation(math.radians(y), 4, 'Z')
            for o in lights_:
                o.matrix_world = R @ rest[o.name]
            bpy.context.view_layer.update()
            r = test_render(tmp, yaw=y)
            im = bpy.data.images.load(r["bg"]); im.colorspace_settings.name = 'Non-Color'
            w, h = im.size; tiles.append(np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4))
            bpy.data.images.remove(im)
    finally:
        for o in lights_:
            o.matrix_world = rest[o.name]
        sc.render.resolution_percentage = old_pct
        for p in (tmp, tmp[:-4] + "-bg.png"):
            if os.path.exists(p):
                os.remove(p)
    arr = np.concatenate(tiles, axis=1)
    out = bpy.data.images.new("_strip", arr.shape[1], arr.shape[0]); out.colorspace_settings.name = 'Non-Color'
    out.pixels.foreach_set(arr.ravel()); out.filepath_raw = out_png; out.file_format = 'PNG'; out.save()
    bpy.data.images.remove(out)
    return out_png
