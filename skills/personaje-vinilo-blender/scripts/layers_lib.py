# layers_lib.py — poses, capas, fotogramas intermedios, verificación y exportación web.
# Todo lo propio del personaje vive en <carpeta>/rig.json (plantilla en templates/rig.json)
# y las poses en <carpeta>/poses/poses.json. Este archivo no se edita.
#
# Uso dentro de Blender (MCP execute_blender_code), con el .blend del personaje abierto:
#   exec(open(r"<skill>/scripts/layers_lib.py", encoding="utf-8").read())
#   init(r"C:\ruta\mi-personaje")
#   render_shadow(); render_pose("rest"); render_pose("curious-left")
#   render_tween("curious-left", 0.5)                       # reposo -> pose, t = 0,5
#   render_tween("look-up-left", 0.5, to="curious-left")    # transición directa entre poses
#   verify_pose("rest")                                      # capas montadas == render completo
#   export_web(r"C:\ruta\mi-personaje\web")                 # WebP recortados + layers.web.js
# Renderizar en tandas de 6-9 imágenes por llamada (el MCP pasa a segundo plano a los 120 s).
import bpy, math, json, os
import numpy as np
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

D = math.radians
O = bpy.data.objects
C = {}          # rig.json
POSES = {}
REST = {}
STEPS = (0.25, 0.5, 0.75)


def init(char_dir):
    """Carga rig.json y poses.json y guarda el reposo (matrix_basis) de las piezas que se mueven."""
    global C, POSES, REST
    C = json.load(open(os.path.join(char_dir, "rig.json"), encoding="utf-8"))
    C["dir"] = char_dir
    C["out"] = os.path.join(char_dir, "layers")
    POSES = json.load(open(os.path.join(char_dir, "poses", "poses.json"), encoding="utf-8"))["poses"]
    bpy.context.view_layer.update()      # el .blend debe estar guardado en reposo
    movable = [C["head"]] + C.get("ears", []) + list(C.get("arms", {}).values())
    REST = {n: O[n].matrix_basis.copy() for n in movable}
    return {"pieces": all_pieces(), "poses": list(POSES)}


def all_pieces():
    return C["body"] + C["head_parts"] + C.get("ears", []) + C["eyes"] + C.get("blink", [])


def key(*parts):
    return "-".join([C["prefix"], *parts])


def tname(t):
    return f"t{round(t * 100)}"


# ---------- poses ----------
def pose_arm(side, up, fwd):
    """Brazo con el origen en el hombro, colgando en -Z. up = elevación lateral, fwd = hacia delante."""
    n = C["arms"][side]
    s = 1 if side == "L" else -1
    sh = REST[n].translation
    O[n].matrix_basis = Matrix.Translation(sh) @ Matrix.Rotation(D(-s * fwd), 4, 'Z') @ Matrix.Rotation(D(-s * up), 4, 'Y')


def reset():
    for n, m in REST.items():
        O[n].matrix_basis = m.copy()
    bpy.context.view_layer.update()


def apply(p):
    """p = dict de pose (ver templates/poses.json). Siempre parte del reposo."""
    reset()
    if "head" in p:
        yaw, roll, lift = p["head"][:3]
        pitch = p["head"][3] if len(p["head"]) > 3 else 0
        piv = Vector(C["head_pivot"])
        R = Matrix.Rotation(D(yaw), 4, 'Z') @ Matrix.Rotation(D(pitch), 4, 'X') @ Matrix.Rotation(D(roll), 4, 'Y')
        h = C["head"]
        O[h].matrix_basis = Matrix.Translation(piv + Vector((0, 0, lift))) @ R @ Matrix.Translation(-piv) @ REST[h]
    for e, d in p.get("ears", {}).items():
        O[e].matrix_basis = O[e].matrix_basis @ Matrix.Rotation(D(d), 4, 'Y')
    for e, d in p.get("ears_x", {}).items():
        O[e].matrix_basis = O[e].matrix_basis @ Matrix.Rotation(D(d), 4, 'X')
    if "arm" in p:
        pose_arm(*p["arm"])
    for a in p.get("arms", []):
        pose_arm(*a)
    bpy.context.view_layer.update()


def _arm_rest(side):
    return [side, C.get("arm_rest_up", 0), 0]


def lerp_pose(a, b, t):
    """Pose intermedia entre a (t=0) y b (t=1); a = {} es el reposo. Interpolación lineal."""
    q = {}
    ha = (a.get("head", [0, 0, 0]) + [0])[:4]
    hb = (b.get("head", [0, 0, 0]) + [0])[:4]
    if "head" in a or "head" in b:
        q["head"] = [x + (y - x) * t for x, y in zip(ha, hb)]
    for k in ("ears", "ears_x"):
        ea, eb = a.get(k, {}), b.get(k, {})
        if ea or eb:
            q[k] = {e: ea.get(e, 0) + (eb.get(e, 0) - ea.get(e, 0)) * t for e in set(ea) | set(eb)}
    arms_a = {x[0]: x for x in ([a["arm"]] if "arm" in a else []) + a.get("arms", [])}
    arms_b = {x[0]: x for x in ([b["arm"]] if "arm" in b else []) + b.get("arms", [])}
    sides = set(arms_a) | set(arms_b)
    if sides:
        q["arms"] = []
        for s in sorted(sides):
            u, v = arms_a.get(s, _arm_rest(s)), arms_b.get(s, _arm_rest(s))
            q["arms"].append([s, u[1] + (v[1] - u[1]) * t, u[2] + (v[2] - u[2]) * t])
    return q


def clashes():
    """Pares de caras que se cruzan según rig.json → clash_pairs (objetivo: 0)."""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    clip = C.get("clash_clip_z", {})

    def bvh(name):
        oe = O[name].evaluated_get(dg)
        m = oe.to_mesh()
        vs = [oe.matrix_world @ v.co for v in m.vertices]
        zmax = clip.get(name)
        fs = [tuple(pl.vertices) for pl in m.polygons
              if zmax is None or sum(vs[i].z for i in pl.vertices) / len(pl.vertices) < zmax]
        tree = BVHTree.FromPolygons(vs, fs)
        oe.to_mesh_clear()
        return tree
    return sum(len(bvh(a).overlap(bvh(b))) for a, b in C.get("clash_pairs", []))


def min_clear(pose_name, field, lo, hi, step=1.0):
    """Fuerza bruta: primer valor de pose[field...] entre lo y hi sin choques.
    field = ("head", 2) para la elevación de la cabeza, ("arm", 1) para la del brazo."""
    p = json.loads(json.dumps(POSES[pose_name]))
    v = lo
    while v <= hi + 1e-9:
        p[field[0]][field[1]] = v
        apply(p)
        if clashes() == 0:
            reset()
            return v
        v += step
    reset()
    return None


# ---------- visibilidad y render ----------
def set_visibility(camera_set, eyes="open", floor=False, holdout=()):
    """camera_set: piezas que ve la cámara. El resto sigue proyectando sombras (sombras entre
    piezas horneadas). holdout: piezas que la cámara ve como recorte transparente."""
    for n in all_pieces():
        o = O[n]
        o.visible_camera = n in camera_set or n in holdout
        o.is_holdout = n in holdout
        o.hide_render = False
    if C.get("arms_fused", True):
        for n in C.get("arms", {}).values():
            O[n].hide_render = True           # se ven a través del cuerpo (fusión en vivo)
    for n in C["eyes"]:
        O[n].hide_render = eyes != "open"
    for n in C.get("blink", []):
        O[n].hide_render = eyes != "blink"
    O[C["floor"]].visible_camera = floor


def restore_visibility():
    for n in all_pieces():
        O[n].visible_camera = True
        O[n].is_holdout = False
        O[n].hide_render = n in C.get("blink", [])
    if C.get("arms_fused", True):
        for n in C.get("arms", {}).values():
            O[n].hide_render = True
    O[C["floor"]].visible_camera = True


def render_to(name, samples=None):
    sc = bpy.context.scene
    os.makedirs(C["out"], exist_ok=True)
    p = os.path.join(C["out"], name + ".png")
    tmp = os.path.join(C["out"], "_tmp_" + name + ".png")
    old = sc.cycles.samples
    if samples:
        sc.cycles.samples = samples
    try:
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
    finally:
        sc.cycles.samples = old
    os.replace(tmp, p)              # Windows bloquea archivos abiertos en visores
    return p


def _img(path):
    i = bpy.data.images.load(path, check_existing=False)
    i.colorspace_settings.name = 'Non-Color'
    i.alpha_mode = 'STRAIGHT'
    return i


def load_rgba(p):
    """Array (alto, ancho, 4) con la fila 0 arriba, alfa directo."""
    i = _img(p)
    w, h = i.size
    a = np.array(i.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(i)
    return a[::-1].copy()


def save_rgba(a_top_first, p):
    h, w = a_top_first.shape[:2]
    o = bpy.data.images.new("tmp", w, h, alpha=True)
    o.colorspace_settings.name = 'Non-Color'
    o.alpha_mode = 'STRAIGHT'
    o.pixels[:] = a_top_first[::-1].ravel()
    o.filepath_raw = p
    o.file_format = 'PNG'
    o.save()
    bpy.data.images.remove(o)


def clean(p, border=6):
    """Alfa a 0 en un borde de 6 px (restos del denoiser) y RGB a 0 donde alfa < 1/255."""
    a = load_rgba(p)
    a[:border], a[-border:], a[:, :border], a[:, -border:] = 0, 0, 0, 0
    a[a[..., 3] < 1 / 255] = 0
    save_rgba(a, p)


def render_layer(name, camera_set, eyes="open", floor=False):
    set_visibility(camera_set, eyes=eyes, floor=floor)
    p = render_to(name)
    clean(p)
    return p


def render_head(name, eyes="open", ears=True):
    """Cabeza completa (con rasgos y, fuera del reposo, orejas) por estado de ojos. Si el
    cuello/cuerpo queda delante: color del render normal + alfa del render con el cuerpo como
    holdout (alfa = mínimo). Solo con holdout, los reflejos salen negros."""
    cam = set(C["head_parts"]) | set(C["eyes"] if eyes == "open" else C.get("blink", []))
    if ears:
        cam |= set(C.get("ears", []))
    set_visibility(cam, eyes=eyes)
    color = render_to("_c_" + name)
    set_visibility(cam, eyes=eyes, holdout=C["body"])
    mask = render_to("_m_" + name, samples=64)
    c, m = load_rgba(color), load_rgba(mask)
    c[..., 3] = np.minimum(c[..., 3], m[..., 3])
    p = os.path.join(C["out"], name + ".png")
    save_rgba(c, p)
    clean(p)
    os.remove(color)
    os.remove(mask)
    return p


def render_shadow():
    """Solo el suelo (shadow catcher) visible para la cámara: la sombra de todo el personaje en reposo."""
    reset()
    p = render_layer(key("shadow"), set(), floor=True)
    restore_visibility()
    return p


def render_pose(pose_name, blink=True):
    """Un cuerpo por pose (lleva la sombra de su cabeza) + cabeza abierta (+ parpadeo).
    En el reposo, orejas en capas sueltas (para moverlas en CSS) y la imagen fija completa;
    en las demás poses las orejas van dentro de la cabeza."""
    apply(POSES[pose_name])
    assert clashes() == 0, f"{pose_name}: hay choques"
    out = [render_layer(key("body", pose_name), set(C["body"]))]
    sep = pose_name == "rest"          # en reposo las orejas van en capas sueltas (se mueven en CSS)
    out.append(render_head(key("head", pose_name, "open"), ears=not sep))
    if blink and C.get("blink"):
        out.append(render_head(key("head", pose_name, "blink"), eyes="blink", ears=not sep))
    if pose_name == "rest":
        for e, side in zip(C.get("ears", []), ("left", "right")):
            out.append(render_layer(key("ear", side), {e}))
        out.append(render_layer(key("full", "rest"), set(all_pieces()) - set(C.get("blink", [])), floor=True))
    restore_visibility()
    reset()
    return out


def render_tween(pose_name, t, to=None):
    """Fotograma intermedio. Sin `to`: del reposo a pose_name. Con `to`: de pose_name a `to`
    (transición directa entre poses vecinas, se lista en rig.json → transitions)."""
    if to:
        p = lerp_pose(POSES[pose_name], POSES[to], t)
        base = f"{pose_name}--{to}-{tname(t)}"
    else:
        p = lerp_pose({}, POSES[pose_name], t)
        base = f"{pose_name}-{tname(t)}"
    apply(p)
    assert clashes() == 0, f"{base}: hay choques"
    out = [render_layer(key("body", base), set(C["body"])),
           render_head(key("head", base, "open"))]
    restore_visibility()
    reset()
    return out


# ---------- verificación ----------
def stack(pose_name):
    """Orden de dibujo de una pose: sombra → cuerpo → orejas (solo reposo) → cabeza."""
    s = [key("shadow"), key("body", pose_name)]
    if pose_name == "rest":
        s += [key("ear", side) for side, _ in zip(("left", "right"), C.get("ears", []))]
    return s + [key("head", pose_name, "open")]


def compose(keys):
    out = None
    for k in keys:
        a = load_rgba(os.path.join(C["out"], k + ".png"))
        if out is None:
            out = np.zeros_like(a)
        al, ao = a[..., 3:4], out[..., 3:4]
        na = al + ao * (1 - al)
        rgb = (a[..., :3] * al + out[..., :3] * ao * (1 - al)) / np.maximum(na, 1e-6)
        out = np.concatenate([rgb, na], axis=2)
    return out


def verify_pose(pose_name, bg_hex="#0C111C"):
    """Monta la pose desde capas y la compara con su render completo sobre el fondo real.
    Aprobado si media < 0,3/255 y p99,9 ≤ 5/255. Guarda el mapa de diferencias ×8."""
    apply(POSES[pose_name])
    ref = render_layer("_ref_" + pose_name, set(all_pieces()) - set(C.get("blink", [])), floor=True)
    restore_visibility()
    reset()
    bg = np.array([int(bg_hex.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)

    def flat(a):
        return a[..., :3] * a[..., 3:4] + bg * (1 - a[..., 3:4])
    d = np.abs(flat(compose(stack(pose_name))) - flat(load_rgba(ref))) * 255
    diff = np.concatenate([np.clip(d * 8 / 255, 0, 1), np.ones(d.shape[:2] + (1,), np.float32)], axis=2)
    save_rgba(diff, os.path.join(C["out"], "_diff_" + pose_name + ".png"))
    os.remove(ref)
    mean, p999 = float(d.mean()), float(np.percentile(d, 99.9))
    return {"pose": pose_name, "mean": round(mean, 3), "p99.9": round(p999, 2), "ok": mean < 0.3 and p999 <= 5}


# ---------- exportación web ----------
def px(world):
    sc = bpy.context.scene
    v = world_to_camera_view(sc, sc.camera, Vector(world))
    return [round(v.x * sc.render.resolution_x, 1), round((1 - v.y) * sc.render.resolution_y, 1)]


def bbox(a, pad=2):
    m = a[..., 3] > 0.004
    if not m.any():
        return None
    ys, xs = np.where(m)
    h, w = m.shape
    return [max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
            min(int(xs.max()) + 1 + pad, w), min(int(ys.max()) + 1 + pad, h)]


def export_web(web_dir, quality=88):
    """Recorta cada capa a su recuadro (+2 px), la guarda en WebP y escribe layers.web.json y
    layers.web.js (window.CHARACTER = {...}) para que el reproductor funcione con doble clic."""
    sc = bpy.context.scene
    assets = os.path.join(web_dir, "assets")
    os.makedirs(assets, exist_ok=True)
    layers = {}
    for f in sorted(os.listdir(C["out"])):
        if not f.endswith(".png") or f.startswith("_"):
            continue
        k = f[:-4]
        a = load_rgba(os.path.join(C["out"], f))
        bb = bbox(a)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        crop = a[y0:y1, x0:x1]
        h, w = crop.shape[:2]
        img = bpy.data.images.new("webp", w, h, alpha=True)
        img.colorspace_settings.name = 'Non-Color'
        img.alpha_mode = 'STRAIGHT'
        img.pixels[:] = crop[::-1].ravel()
        out = os.path.join(assets, k + ".webp")
        img.filepath_raw = out
        img.file_format = 'WEBP'
        img.save(quality=quality)
        bpy.data.images.remove(img)
        layers[k] = {"file": "assets/" + k + ".webp", "x": x0, "y": y0, "w": w, "h": h,
                     "bytes": os.path.getsize(out)}
    pv = {n: px(p) for n, p in C.get("pivots_world", {}).items()}
    feet = pv.get("feet", [sc.render.resolution_x / 2, sc.render.resolution_y * 0.9])
    data = {
        "prefix": C["prefix"],
        "canvas": [sc.render.resolution_x, sc.render.resolution_y],
        "pivots": pv,
        "halo_css": {"center": feet, "half_width": C.get("halo_half_width_px") or round(sc.render.resolution_x * 0.14),
                     "color": C.get("accent", "#329DA8")},
        "poses": {p: stack(p) for p in POSES if key("body", p) in layers},
        "transitions": C.get("transitions", []),
        "layers": layers,
    }
    js = json.dumps(data, ensure_ascii=False, indent=1)
    open(os.path.join(web_dir, "layers.web.json"), "w", encoding="utf-8").write(js)
    open(os.path.join(web_dir, "layers.web.js"), "w", encoding="utf-8").write("window.CHARACTER = " + js + ";\n")
    total = sum(l["bytes"] for l in layers.values())
    return {"layers": len(layers), "kb": round(total / 1024), "missing_poses": [p for p in POSES if key("body", p) not in layers]}
