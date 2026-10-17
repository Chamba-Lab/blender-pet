# M2 — Cejas en "M" y barba (sin boca), como relieves crema sobre la cabeza.
# Las siluetas salen de references/highsfield3.png (vista frontal), simetrizadas, y se proyectan desde
# delante sobre Raccoon_Head. Ejecutar dentro de Blender, después de build_m1_head.py:
#   exec(open(r"C:\APPS\Renders\mapache\scripts\build_m2_face.py", encoding="utf-8").read())
import bpy, bmesh, math
import numpy as np
from collections import deque
from mathutils import Vector

REF = r"C:\APPS\Renders\mapache\references\highsfield3.png"
CROP = (120, 280, 740, 900)            # x0, y0, x1, y1 (px, origen arriba-izquierda)
# Anclaje: centros de los ojos en el recorte (204,345)/(410,347) <-> x ±0,205, z 1,345 en el modelo
S = 0.41 / 206.0
CX, CY, Z0 = 307.0, 346.0, 1.345

Q = dict(
    brow=dict(seed=(220, 309), thick=0.016, edge=6, bury=0.02, hang=0.0, max_ny=-0.45),
    beard=dict(seed=(459, 309), fade=None, tip_cut=16, notch_amp=0.35, tip_round=4,
               muzzle_only=True, muzzle_bottom=548, muzzle_top=396, muzzle_half=80, muzzle_narrow=0.5, muzzle_side=(62, 128, 72), muzzle_round=7, muzzle_thick=0.014, notch_win=18, notch_from=470, thick=0.022, edge=7, bury=0.02, hang=0.10, max_ny=1.0, back_edge=30, smooth=30),
    beard_mass=dict(c=(0.0, -0.02, 1.20), r=(0.30, 0.33, 0.40)),   # soporte para la parte que cuelga
    voxel=0.003,
)


def _load_ref():
    im = bpy.data.images.load(REF); im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(im)
    x0, y0, x1, y1 = CROP
    return a[y0:y1, x0:x1].mean(2) > 0.55


def _component(mask, seed):
    H, W = mask.shape
    if not mask[seed]:                        # semilla en un hueco: tomar el píxel de la máscara más cercano
        ys, xs = np.nonzero(mask)
        k = np.argmin((ys - seed[0]) ** 2 + (xs - seed[1]) ** 2); seed = (int(ys[k]), int(xs[k]))
    out = np.zeros_like(mask); q = deque([seed]); out[seed] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not out[ny, nx]:
                out[ny, nx] = True; q.append((ny, nx))
    return out


def _fill_holes(m):
    H, W = m.shape
    bg = np.zeros_like(m); q = deque()
    for y in range(H):
        for x in (0, W - 1):
            if not m[y, x]: bg[y, x] = True; q.append((y, x))
    for x in range(W):
        for y in (0, H - 1):
            if not m[y, x] and not bg[y, x]: bg[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and not m[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True; q.append((ny, nx))
    return ~bg


def _symmetric(m):
    """Unión con su espejo respecto al eje x = CX."""
    H, W = m.shape
    out = m.copy()
    xs = np.arange(W); mx = np.round(2 * CX - xs).astype(int)
    ok = (mx >= 0) & (mx < W)
    out[:, xs[ok]] |= m[:, mx[ok]]
    return out


def _edge_distance(m, n):
    d = np.zeros(m.shape, np.float32); cur = m.copy()
    for _ in range(n):
        d += cur
        e = cur.copy()
        e[1:, :] &= cur[:-1, :]; e[:-1, :] &= cur[1:, :]; e[:, 1:] &= cur[:, :-1]; e[:, :-1] &= cur[:, 1:]
        cur = e
    return d  # 1 en el borde ... n en el interior


def _beard_tips(m, cfg):
    """Acorta las puntas de la barba (tip_cut px) y hace más profundos los huecos entre mechones:
    la distancia de cada columna a la línea de las puntas se multiplica por (1 + notch_amp)."""
    H, W = m.shape
    cols = np.where(m.any(0))[0]
    yb = np.full(W, -1)
    for x in cols:
        yb[x] = np.nonzero(m[:, x])[0].max()
    k = cfg["notch_win"]
    env = np.array([yb[max(0, x - k):x + k + 1].max() if yb[x] >= 0 else -1 for x in range(W)])
    out = m.copy()
    for x in cols:
        if yb[x] < cfg["notch_from"]:
            continue
        new = env[x] - cfg["tip_cut"] - (env[x] - yb[x]) * (1 + cfg["notch_amp"])
        out[int(np.ceil(new)) + 1:, x] = False
    return out


def _round_tips(m, r, from_row):
    """Apertura morfológica (disco de radio r) solo en la zona que cuelga: redondea las puntas
    convexas sin cambiar los huecos."""
    offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dy * dy + dx * dx <= r * r]
    def shift(a, dy, dx):
        out = np.zeros_like(a)
        H, W = a.shape
        out[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] = a[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
        return out
    er = np.ones_like(m)
    for dy, dx in offs:
        er &= shift(m, dy, dx)
    op = np.zeros_like(m)
    for dy, dx in offs:
        op |= shift(er, dy, dx)
    out = m.copy()
    out[from_row:] = op[from_row:]
    return out


def _px_to_xz(px, py):
    return (px - CX) * S, Z0 - (py - CY) * S


def _ray_front(objs, x, z):
    best = None
    for o in objs:
        inv = o.matrix_world.inverted()
        hit, loc, nor, _ = o.ray_cast(inv @ Vector((x, -3.0, z)), (inv.to_3x3() @ Vector((0, 1, 0))).normalized())
        if hit:
            p = o.matrix_world @ loc
            n = (o.matrix_world.to_3x3().inverted().transposed() @ nor).normalized()
            if best is None or p.y < best[0].y:
                best = (p, o, n)
    return best


def relief(name, m, cfg, head, support, mat, coll):
    """Malla cerrada tipo 'campo de alturas' sobre la cabeza; luego remallado + suavizado."""
    H, W = m.shape
    dist = _edge_distance(m, max(cfg["edge"], cfg.get("back_edge", 0)))
    nodes = {}
    def node_y(i, j):
        x, z = _px_to_xz(j, i)
        if support:                               # barba: la envolvente más adelantada de cabeza y soporte
            hb = _ray_front([head, support], x, z)
            return (hb[0].y, hb[1] is support) if hb else (None, None)
        hh = _ray_front([head], x, z)
        if hh:
            if hh[2].y > cfg["max_ny"]:           # solo la parte que mira al frente (no se estira por los lados)
                return None, None
            return hh[0].y, False
        hs = _ray_front([support], x, z) if support else None
        return (hs[0].y, True) if hs else (None, None)
    bm = bmesh.new()
    cells = np.argwhere(m)
    # alturas por nodo: media de la distancia al borde de las celdas vecinas
    def nd(i, j):
        acc = [dist[a, b] for a, b in ((i - 1, j - 1), (i - 1, j), (i, j - 1), (i, j)) if 0 <= a < H and 0 <= b < W and m[a, b]]
        return min(acc) if acc else 0
    keep = np.zeros_like(m)
    for i, j in cells:
        ok = True
        for a, b in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)):
            if (a, b) not in nodes:
                y, hung = node_y(a, b)
                if y is None:
                    nodes[(a, b)] = None
                else:
                    x, z = _px_to_xz(b, a)
                    t = cfg["thick"] * math.sin(min(nd(a, b) / cfg["edge"], 1.0) * math.pi / 2)
                    if cfg.get("fade"):               # hacia abajo el relieve se pega a la cara (sin "labio")
                        f0, f1, mn = cfg["fade"]
                        u = min(max((a - f0) / (f1 - f0), 0.0), 1.0); u = u * u * (3 - 2 * u)
                        t *= 1 - (1 - mn) * u
                    if hung:   # la parte que cuelga se adelgaza hacia el borde (sin cortes rectos)
                        back = cfg["hang"] * math.sin(min(nd(a, b) / cfg["back_edge"], 1.0) * math.pi / 2)
                    else:
                        back = cfg["bury"]
                    nodes[(a, b)] = (bm.verts.new((x, y - t, z)), bm.verts.new((x, y + back, z)))
            ok &= nodes[(a, b)] is not None
        keep[i, j] = ok
    for i, j in np.argwhere(keep):
        q = [nodes[(i, j)], nodes[(i, j + 1)], nodes[(i + 1, j + 1)], nodes[(i + 1, j)]]
        bm.faces.new([v[0] for v in q])
        bm.faces.new([v[1] for v in reversed(q)])
        for (a, b), (c, d), (di, dj) in (((i, j), (i, j + 1), (-1, 0)),
                                         ((i, j + 1), (i + 1, j + 1), (0, 1)),
                                         ((i + 1, j + 1), (i + 1, j), (1, 0)),
                                         ((i + 1, j), (i, j), (0, -1))):
            ni, nj = i + di, j + dj
            if not (0 <= ni < H and 0 <= nj < W and keep[ni, nj]):
                p0, p1 = nodes[(a, b)], nodes[(c, d)]
                bm.faces.new((p0[0], p0[1], p1[1], p1[0]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    r = o.modifiers.new("Remesh", 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = Q["voxel"]
    s = o.modifiers.new("Smooth", 'SMOOTH'); s.factor = 0.8; s.iterations = cfg.get("smooth", 12)
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); old = o.data; o.data = new; bpy.data.meshes.remove(old)
    new.shade_smooth()
    o.parent = head; o.matrix_parent_inverse = head.matrix_world.inverted()
    return o


def build():
    for n in ("Raccoon_Brow", "Raccoon_Beard", "Raccoon_BeardTop", "Raccoon_Cheek"):
        o = bpy.data.objects.get(n)
        if o: bpy.data.objects.remove(o)
    head = bpy.data.objects["Raccoon_Head"]
    coll = bpy.data.collections["Raccoon"]
    cream = bpy.data.materials["Raccoon_Cream"]
    bpy.context.view_layer.update()

    mask = _load_ref()
    masks = {k: _symmetric(_fill_holes(_component(mask, Q[k]["seed"]))) for k in ("brow", "beard")}
    bq = Q["beard"]
    if bq.get("muzzle_only"):
        # Solo el hocico crema (sin mechones colgantes): bajo la nariz se estrecha en forma de gota
        # hasta la barbilla, sin esquinas a los lados (para que no se lea como una boca)
        H, W = masks["beard"].shape
        rows = np.arange(H)[:, None]; cols = np.arange(W)[None, :]
        # Hocico blanco completo (como un mapache real): bajo los ojos se ensancha hacia los costados
        # del morro y las mejillas bajas, y baja redondeado por la barbilla.
        h0, hmax, hchin = bq["muzzle_side"]
        u = np.clip((rows - bq["muzzle_top"]) / (bq["muzzle_bottom"] - bq["muzzle_top"]), 0, 1)
        grow = h0 + (hmax - h0) * np.sin(np.pi / 2 * np.clip(u / 0.35, 0, 1))
        shrink = hmax + (hchin - hmax) * np.clip((u - 0.35) / 0.65, 0, 1) ** 1.5
        half = np.where(u < 0.35, grow, shrink) * np.sqrt(np.clip(1 - u ** 8, 0, 1))
        below = (rows >= bq["muzzle_top"]) & (rows <= bq["muzzle_bottom"]) & (np.abs(cols - CX) <= half)
        masks["beard"] = (masks["beard"] & (rows < bq["muzzle_top"])) | below
        masks["beard"] = _round_tips(masks["beard"], bq["muzzle_round"], 0)
    else:
        masks["beard"] = _beard_tips(masks["beard"], bq)
        masks["beard"] = _round_tips(masks["beard"], bq["tip_round"], bq["notch_from"])

    # soporte temporal para la barba que cuelga bajo la barbilla
    sbm = bmesh.new()
    g = bmesh.ops.create_uvsphere(sbm, u_segments=64, v_segments=40, radius=1.0)
    c, r = Q["beard_mass"]["c"], Q["beard_mass"]["r"]
    for v in g['verts']:
        v.co = Vector((v.co.x * r[0] + c[0], v.co.y * r[1] + c[1], v.co.z * r[2] + c[2]))
    sme = bpy.data.meshes.new("_beard_support"); sbm.to_mesh(sme); sbm.free()
    sup = bpy.data.objects.new("_beard_support", sme); coll.objects.link(sup)
    bpy.context.view_layer.update()

    out = {}
    out["brow"] = relief("Raccoon_Brow", masks["brow"], Q["brow"], head, None, cream, coll)
    if bq.get("muzzle_only"):                 # pegado a la cara, relieve fino y uniforme como la ceja
        mcfg = dict(bq, thick=bq["muzzle_thick"], edge=6, smooth=12)
        out["beard"] = relief("Raccoon_Beard", masks["beard"], mcfg, head, None, cream, coll)
    else:
        out["beard"] = relief("Raccoon_Beard", masks["beard"], bq, head, sup, cream, coll)
    bpy.data.objects.remove(sup); bpy.data.meshes.remove(sme)

    # La nariz se apoya sobre la barba (no queda enterrada)
    bpy.context.view_layer.update()
    nose = bpy.data.objects["Raccoon_Nose"]
    p = nose.matrix_world.translation
    hb = _ray_front([out["beard"]], p.x, p.z); hh = _ray_front([head], p.x, p.z)
    if hb and hh:
        if "y0" not in nose:
            nose["y0"] = p.y                      # posición sobre la cabeza (M1), para no acumular
        nose.matrix_world.translation = Vector((p.x, nose["y0"] + hb[0].y - hh[0].y, p.z))
    return {k: len(o.data.vertices) for k, o in out.items()}


m2_stats = build()
