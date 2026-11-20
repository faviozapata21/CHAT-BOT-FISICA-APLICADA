import streamlit as st
import streamlit.components.v1 as components
import urllib.parse
import cmath
import math
import time
import re
from collections import defaultdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (FONDO NEGRO PURO, SIN SIDEBAR)
# ==============================================================================
st.set_page_config(
    page_title="Física Aplicada 1 — Asistente IA + CircuitJS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        display: none !important;
    }
    .stApp {
        background-color: #030407 !important;
        color: #f1f5f9 !important;
    }
    .simulator-box {
        border: 1px solid #1e293b;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.85);
        margin-bottom: 14px;
        background: #080c15;
    }
    .status-badge {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 8px 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        color: #38bdf8;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .stChatMessage {
        background-color: #0b0f19 !important;
        border: 1px solid #1e293b !important;
        border-radius: 12px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 2. GENERADOR DE NETLIST PARA CIRCUITJS (FALSTAD)
# ==============================================================================
def generar_netlist_circuitjs(v_rms: float, f: float, comps: list, tipo: str = "serie") -> str:
    f_segura = f if (f and f > 0) else 60.0
    v_pico = round(v_rms * math.sqrt(2), 3)
    y_top, y_bot, step = 144, 272, 96
    lines = ["$ 1 5.0E-6 10.20027730826997 50 5.0 50"]

    if tipo == "mixto_c":
        # Mixto de capacitores: fuente DC a la izquierda, rama central vertical con C1 y C2 en serie,
        # y rama derecha vertical con C3 en paralelo entre los mismos nodos superior e inferior.
        x_src, x_mid, x_right = 144, 288, 384
        y_mid = (y_top + y_bot) // 2
        lines.append(f"v {x_src} {y_bot} {x_src} {y_top} 0 1 {f_segura} {v_pico} 0 0 0.5")
        lines.append(f"w {x_src} {y_top} {x_mid} {y_top} 0")
        lines.append(f"w {x_src} {y_bot} {x_mid} {y_bot} 0")
        c1 = comps[0]["val"] if len(comps) > 0 else 0.0
        c2 = comps[1]["val"] if len(comps) > 1 else 0.0
        c3 = comps[2]["val"] if len(comps) > 2 else 0.0
        if len(comps) >= 2:
            lines.append(f"c {x_mid} {y_top} {x_mid} {y_mid} 0 {c1 * 1e-6} 0")
            lines.append(f"c {x_mid} {y_mid} {x_mid} {y_bot} 0 {c2 * 1e-6} 0")
        elif len(comps) == 1:
            lines.append(f"c {x_mid} {y_top} {x_mid} {y_bot} 0 {c1 * 1e-6} 0")
        lines.append(f"w {x_mid} {y_top} {x_right} {y_top} 0")
        lines.append(f"w {x_mid} {y_bot} {x_right} {y_bot} 0")
        if len(comps) >= 3:
            lines.append(f"c {x_right} {y_top} {x_right} {y_bot} 0 {c3 * 1e-6} 0")
        lines.append(f"g {x_src} {y_bot} {x_src} {y_bot + 32} 0")
    elif tipo in ("serie", "mixto"):
        x_src = 144
        lines.append(f"v {x_src} {y_bot} {x_src} {y_top} 0 1 {f_segura} {v_pico} 0 0 0.5")
        x_curr = x_src
        for c in comps:
            x_next = x_curr + step
            t, val = c["tipo"], c["val"]
            if t == "R":
                lines.append(f"r {x_curr} {y_top} {x_next} {y_top} 0 {val}")
            elif t == "L":
                lines.append(f"l {x_curr} {y_top} {x_next} {y_top} 0 {val} 0")
            elif t == "C":
                lines.append(f"c {x_curr} {y_top} {x_next} {y_top} 0 {val * 1e-6} 0")
            x_curr = x_next
        lines.append(f"w {x_curr} {y_top} {x_curr} {y_bot} 0")
        lines.append(f"w {x_curr} {y_bot} {x_src} {y_bot} 0")
        lines.append(f"g {x_src} {y_bot} {x_src} {y_bot + 32} 0")
    else:
        x_src = 144
        lines.append(f"v {x_src} {y_bot} {x_src} {y_top} 0 1 {f_segura} {v_pico} 0 0 0.5")
        x_end = x_src + max(1, len(comps)) * step
        lines.append(f"w {x_src} {y_top} {x_end} {y_top} 0")
        lines.append(f"w {x_src} {y_bot} {x_end} {y_bot} 0")
        x_branch = x_src + step
        for c in comps:
            t, val = c["tipo"], c["val"]
            if t == "R":
                lines.append(f"r {x_branch} {y_top} {x_branch} {y_bot} 0 {val}")
            elif t == "L":
                lines.append(f"l {x_branch} {y_top} {x_branch} {y_bot} 0 {val} 0")
            elif t == "C":
                lines.append(f"c {x_branch} {y_top} {x_branch} {y_bot} 0 {val * 1e-6} 0")
            x_branch += step
        lines.append(f"g {x_src} {y_bot} {x_src} {y_bot + 32} 0")
    return "\n".join(lines)


def generar_url_circuitjs(v_rms, f, comps, tipo="serie"):
    return (f"https://www.falstad.com/circuit/circuitjs.html?cct="
            f"{urllib.parse.quote(generar_netlist_circuitjs(v_rms, f, comps, tipo))}")


def extraer_netlist_puro(texto: str) -> str:
    """Extrae el netlist puro (XML o texto) eliminando bloques de markdown o texto periférico."""
    t = texto.strip()
    t_clean = re.sub(r'^```[a-zA-Z]*\s*', '', t)
    t_clean = re.sub(r'\s*```$', '', t_clean).strip()
    t_lower = t_clean.lower()
    if "<cir" in t_lower:
        idx_start = t_lower.find("<cir")
        idx_end = t_lower.rfind(">")
        if idx_start != -1 and idx_end != -1 and idx_end > idx_start:
            return t_clean[idx_start:idx_end + 1].strip()
    elif "$" in t_clean:
        idx_doll = t_clean.find("$")
        return t_clean[idx_doll:].strip()
    return t_clean


def actualizar_iframe_circuitjs(tipo_resp: str, prompt_raw: str, net_data: dict = None) -> str:
    """
    Actualiza la URL del iframe de CircuitJS:
    1. Si es netlist XML (<cir...>) o texto clásico, respeta la cadena exacta del netlist
       del usuario, preservando coordenadas, nodos y cables sin sobrescribirlos con plantillas sintéticas.
    2. Mantiene intacta la frecuencia real que traía el circuito original (ej. 40 Hz) sin forzar 60 Hz.
    3. Solo sintetiza un nuevo diagrama cuando la consulta proviene de procesamiento NLP (M3_ca).
    """
    if tipo_resp in ("netlist_xml", "netlist_text"):
        netlist_limpio = extraer_netlist_puro(prompt_raw)
        return f"https://www.falstad.com/circuit/circuitjs.html?cct={urllib.parse.quote(netlist_limpio)}"

    # Si proviene de consulta textual de CA (NLP M3_ca)
    v_rms = st.session_state.get("v_rms", 120.0)
    f = st.session_state.get("f", 60.0)
    comps = st.session_state.get("componentes", [])
    tipo = st.session_state.get("tipo", "serie")
    if net_data:
        v_rms = net_data.get("v_rms", v_rms)
        f = net_data.get("f", f)
        comps = net_data.get("componentes", comps)
        tipo = net_data.get("tipo", tipo)
    return generar_url_circuitjs(v_rms, f, comps, tipo)


# ==============================================================================
# 3. ANÁLISIS TOPOLÓGICO DE GRAFO
# ==============================================================================
def analizar_grafo_circuito(componentes_con_nodos, wires):
    if not componentes_con_nodos:
        return {"tipo": "serie", "es_mixto": False, "max_degree": 0,
                "nodos_derivacion": 0, "grupos_paralelo": [], "mensaje": "Sin componentes."}
    parent = {}

    def find(i):
        if i not in parent:
            parent[i] = i
        if parent[i] != i:
            parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    for p1, p2 in wires:
        union(p1, p2)

    comp_nodes = []
    node_degree = defaultdict(int)
    node_pairs = defaultdict(list)

    for idx, c in enumerate(componentes_con_nodos):
        if "n1" in c and "n2" in c and c["n1"] and c["n2"]:
            na, nb = find(c["n1"]), find(c["n2"])
            pair = tuple(sorted([na, nb]))
            comp_nodes.append((c, na, nb, pair))
            node_degree[na] += 1
            node_degree[nb] += 1
            node_pairs[pair].append(idx)
        else:
            comp_nodes.append((c, None, None, None))

    valid = [cn for cn in comp_nodes if cn[1] is not None]
    if len(valid) < 2:
        return {"tipo": "serie", "es_mixto": False, "max_degree": 2,
                "nodos_derivacion": 0, "grupos_paralelo": [], "mensaje": "Sin coordenadas suficientes."}

    unique_pairs = set(cn[3] for cn in valid if cn[3][0] != cn[3][1])
    max_degree = max(node_degree.values()) if node_degree else 0
    nodos_der = [n for n, d in node_degree.items() if d >= 3]
    grupos_par = [idxs for pair, idxs in node_pairs.items() if len(idxs) > 1 and pair[0] != pair[1]]

    if len(unique_pairs) == 1 and len(valid) >= 2:
        return {"tipo": "paralelo", "es_mixto": False, "max_degree": max_degree,
                "nodos_derivacion": len(nodos_der), "grupos_paralelo": grupos_par,
                "mensaje": "Paralelo puro."}
    elif nodos_der or grupos_par:
        return {"tipo": "mixto", "es_mixto": True, "max_degree": max_degree,
                "nodos_derivacion": len(nodos_der), "grupos_paralelo": grupos_par,
                "mensaje": f"Red mixta: {len(nodos_der)} nodo(s) de derivación."}
    return {"tipo": "serie", "es_mixto": False, "max_degree": max_degree,
            "nodos_derivacion": 0, "grupos_paralelo": [], "mensaje": "Serie consecutiva."}


def calcular_reduccion_mixta(componentes, grupos_paralelo):
    detalles, indices_par, r_par_list = [], set(), []
    for grp in grupos_paralelo:
        res_grp = [componentes[i] for i in grp
                   if componentes[i].get("tipo") == "R" and componentes[i].get("val", 0) > 0]
        if len(res_grp) >= 2:
            inv = sum(1.0 / c["val"] for c in res_grp)
            rp = 1.0 / inv if inv > 0 else 0.0
            nombres = [f"R{i+1} ({componentes[i]['val']:.1f} Ω)"
                       for i in grp if componentes[i].get("tipo") == "R"]
            detalles.append(f"[{' || '.join(nombres)}] = {rp:.2f} Ω")
            r_par_list.append(rp)
            for i in grp:
                if componentes[i].get("tipo") == "R":
                    indices_par.add(i)
    r_serie = sum(componentes[i]["val"] for i, c in enumerate(componentes)
                  if c.get("tipo") == "R" and i not in indices_par and c.get("val", 0) > 0)
    r_ciega = sum(c.get("val", 0) for c in componentes if c.get("tipo") == "R")
    r_mixta = r_serie + sum(r_par_list)
    return {"detalles": detalles, "r_serie_ciega": r_ciega,
            "r_mixta_estimada": r_mixta if detalles else r_ciega,
            "tiene_reduccion": bool(detalles)}


# ==============================================================================
# 4. PARSERS DE NETLIST
# ==============================================================================
def es_netlist_xml(texto):
    t = texto.lower()
    return "<cir" in t or (("<v" in t or "<r" in t) and ("<l" in t or "<c" in t or "<r" in t))


def es_netlist_texto(texto):
    """
    Detecta ÚNICAMENTE netlists reales de CircuitJS en formato texto.

    Antes se consideraba netlist cualquier texto que contuviera "v " o "r "
    y un salto de línea, lo cual capturaba enunciados como:
        "fuerza magnética sobre un conductor:\\nr = 5 cm\\nI = 2 A"
    y terminaba en el error 'Netlist clásico detectado pero sin componentes'.

    Ahora exige líneas de componente válidas (código v/r/l/c/w seguido de
    coordenadas numéricas), con la cabecera '$' opcional.
    """
    lineas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    if not lineas:
        return False

    # Línea de componente CircuitJS: "r 112 96 240 96 0 1000", "w 0 0 10 0 0", ...
    patron_componente = re.compile(
        r'^[vrlcw]\s+[+-]?\d+(?:\.\d+)?\s+[+-]?\d+(?:\.\d+)?(?:\s|$)',
        re.IGNORECASE,
    )
    n_componentes = sum(1 for l in lineas if patron_componente.match(l))

    # Exportaciones típicas: "$ 1 0 ... " seguida de componentes.
    if lineas[0].startswith("$"):
        return n_componentes >= 1

    # Sin cabecera '$', exigir al menos dos líneas de componente para no
    # confundir un enunciado con datos como "r = 5 cm".
    return n_componentes >= 2


def _extraer_coords(attrs):
    def g(pat):
        m = re.search(pat, attrs)
        return round(float(m.group(1))) if m else None
    x1 = g(r'x1\s*=\s*["\']?(-?\d+(?:\.\d+)?)["\']?')
    y1 = g(r'y1\s*=\s*["\']?(-?\d+(?:\.\d+)?)["\']?')
    x2 = g(r'x2\s*=\s*["\']?(-?\d+(?:\.\d+)?)["\']?')
    y2 = g(r'y2\s*=\s*["\']?(-?\d+(?:\.\d+)?)["\']?')
    if all(v is not None for v in [x1, y1, x2, y2]):
        return (x1, y1), (x2, y2)
    return None, None


def parse_circuitjs_xml(texto):
    t = texto.lower()
    f_prev = st.session_state.get("f", 60.0) if hasattr(st, "session_state") and "f" in st.session_state else 60.0
    v_rms, f, comps, elementos_grafo, wires = 120.0, f_prev, [], [], []

    for m in re.finditer(r'<w\b([^>]*)/?>', t):
        n1, n2 = _extraer_coords(m.group(1))
        if n1 and n2:
            wires.append((n1, n2))

    mv = re.search(r'<(?:v|voltage|acsource)\b([^>]*)/?>', t)
    if mv:
        a = mv.group(1)
        mfr = re.search(r'\b(?:frequency|freq|fr|f)\s*=\s*["\']?([0-9]+(?:\.[0-9]+)?)["\']?', a)
        if mfr:
            parsed_f = float(mfr.group(1))
            f = parsed_f if parsed_f > 0 else f_prev
        else:
            f = f_prev
        mvr = re.search(r'(?:vr|vrms)\s*=\s*["\']?([0-9.eE+\-]+)["\']?', a)
        mmx = re.search(r'(?:maxv|vmax|peak)\s*=\s*["\']?([0-9.eE+\-]+)["\']?', a)
        mva = re.search(r'\bv\s*=\s*["\']?([0-9.eE+\-]+)["\']?', a)
        if mvr:
            v_rms = float(mvr.group(1))
        elif mmx:
            v_rms = round(float(mmx.group(1)) / math.sqrt(2), 2)
        elif mva:
            v_rms = float(mva.group(1))
        n1, n2 = _extraer_coords(a)
        if n1:
            elementos_grafo.append({"tipo": "V", "val": v_rms, "n1": n1, "n2": n2})

    for tag, tipo_c in [("r", "R"), ("l", "L"), ("c", "C")]:
        for m in re.finditer(rf'<{tag}\b([^>]*)/?>', t):
            a = m.group(1)
            mv2 = re.search(rf'(?:{tag}|val|value)\s*=\s*["\']?([0-9.eE+\-]+)\s*(µf|uf|µ|u|nf|pf)?["\']?', a)
            if mv2:
                raw = float(mv2.group(1))
                unit = (mv2.group(2) or "").lower()
                if tipo_c == "C":
                    if unit in ["µf", "uf", "µ", "u"]:
                        val = raw
                    elif unit == "nf":
                        val = round(raw * 1e-3, 4)
                    elif unit == "pf":
                        val = round(raw * 1e-6, 4)
                    else:
                        val = round(raw * 1e6, 4) if raw < 0.01 else raw
                else:
                    val = raw
                n1, n2 = _extraer_coords(a)
                comps.append({"tipo": tipo_c, "val": val, "n1": n1, "n2": n2})
                elementos_grafo.append({"tipo": tipo_c, "val": val, "n1": n1, "n2": n2})

    topo = analizar_grafo_circuito(elementos_grafo, wires)
    tipo = topo["tipo"]
    if topo["max_degree"] == 0:
        tipo = ("mixto" if ("mixto" in t or "derivacion" in t)
                else ("paralelo" if "paralelo" in t else "serie"))
        topo["es_mixto"] = (tipo == "mixto")
    red = calcular_reduccion_mixta(elementos_grafo, topo.get("grupos_paralelo", []))
    comps_calc = [{"tipo": c["tipo"], "val": c["val"]} for c in comps]
    return {"v_rms": v_rms, "f": f, "componentes": comps_calc, "tipo": tipo,
            "topologia_info": topo, "reduccion_mixta": red}


def parse_circuitjs_text(texto):
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    f_prev = st.session_state.get("f", 60.0) if hasattr(st, "session_state") and "f" in st.session_state else 60.0
    v_rms, f, comps, elementos_grafo, wires = 120.0, f_prev, [], [], []

    for ln in lineas:
        p = ln.split()
        if not p:
            continue
        cod = p[0]
        if cod == "v":
            try:
                freq = float(p[7]) if len(p) > 7 else 0.0
                v_pk = float(p[8]) if len(p) > 8 else 169.7
                if v_pk > 0:
                    v_rms = round(v_pk / math.sqrt(2), 2)
                f = freq if freq > 0 else f_prev
                if len(p) >= 5:
                    n1 = (int(p[1]), int(p[2]))
                    n2 = (int(p[3]), int(p[4]))
                    elementos_grafo.append({"tipo": "V", "val": v_rms, "n1": n1, "n2": n2})
            except Exception:
                pass
        elif cod == "w" and len(p) >= 5:
            try:
                wires.append(((int(p[1]), int(p[2])), (int(p[3]), int(p[4]))))
            except Exception:
                pass
        elif cod in ("r", "l", "c") and len(p) >= 7:
            try:
                n1 = (int(p[1]), int(p[2]))
                n2 = (int(p[3]), int(p[4]))
                val = float(p[6])
                tipo_c = cod.upper()
                if tipo_c == "C":
                    val = round(val * 1e6, 4)
                comps.append({"tipo": tipo_c, "val": val, "n1": n1, "n2": n2})
                elementos_grafo.append({"tipo": tipo_c, "val": val, "n1": n1, "n2": n2})
            except Exception:
                pass

    if not f or f <= 0:
        f = f_prev
    topo = analizar_grafo_circuito(elementos_grafo, wires)
    red = calcular_reduccion_mixta(elementos_grafo, topo.get("grupos_paralelo", []))
    comps_calc = [{"tipo": c["tipo"], "val": c["val"]} for c in comps]
    return {"v_rms": v_rms, "f": f, "componentes": comps_calc, "tipo": topo["tipo"],
            "topologia_info": topo, "reduccion_mixta": red}


# ==============================================================================
# 5. MOTOR ANALÍTICO RLC
# ==============================================================================
def calcular_circuito_ac(v_rms, f, comps, tipo="serie",
                         reduccion_mixta=None, topologia_info=None):
    f_s = f if (f and f > 0) else 60.0
    omega = 2 * math.pi * f_s
    res_l = [float(c["val"]) for c in comps
             if c.get("tipo") == "R" and c.get("val") and float(c["val"]) > 0]
    ind_l = [float(c["val"]) for c in comps
             if c.get("tipo") == "L" and c.get("val") and float(c["val"]) > 0]
    cap_l = [float(c["val"]) for c in comps
             if c.get("tipo") == "C" and c.get("val") and float(c["val"]) > 0]
    es_mixto = (tipo == "mixto") or (topologia_info and topologia_info.get("es_mixto", False))
    advertencia = None

    def _cap_eq(clist):
        if not clist:
            return 0.0, 0.0
        inv = sum(1.0 / (c * 1e-6) for c in clist if c > 0)
        cf = 1.0 / inv if inv > 0 else 0.0
        return cf, cf * 1e6

    if es_mixto or tipo == "serie":
        if es_mixto and reduccion_mixta and reduccion_mixta.get("tiene_reduccion"):
            r_eq = reduccion_mixta["r_mixta_estimada"]
            ramas = " | ".join(reduccion_mixta["detalles"])
            advertencia = (f"⚠️ **Red Mixta:** Ramas equivalentes: {ramas}. "
                           f"**R_eq = {r_eq:.2f} Ω**")
        elif es_mixto:
            r_eq = sum(res_l) if res_l else 0.0
            advertencia = (f"⚠️ **Red Mixta:** Nodos con derivaciones detectados. "
                           f"R_eq ≈ {r_eq:.2f} Ω (aproximación de serie).")
        else:
            r_eq = sum(res_l) if res_l else 0.0
        l_eq = sum(ind_l) if ind_l else 0.0
        c_eq_f, c_eq_uf = _cap_eq(cap_l)
        x_l = omega * l_eq if l_eq > 0 and omega > 0 else 0.0
        x_c = 1.0 / (omega * c_eq_f) if c_eq_f > 0 and omega > 0 else 0.0
        x_n = x_l - x_c
        z = complex(r_eq, x_n)
        i_f = complex(v_rms, 0) / z if abs(z) > 1e-9 else 0j
    else:  # paralelo
        r_eq = (1.0 / sum(1.0 / r for r in res_l if r > 0)) if res_l else 1e9
        l_eq = (1.0 / sum(1.0 / l for l in ind_l if l > 0)) if ind_l else 0.0
        c_eq_uf = sum(cap_l) if cap_l else 0.0
        c_eq_f = c_eq_uf * 1e-6
        x_l = omega * l_eq if l_eq > 0 and omega > 0 else 0.0
        x_c = 1.0 / (omega * c_eq_f) if c_eq_f > 0 and omega > 0 else 0.0
        x_n = x_l - x_c
        g = 1.0 / r_eq if r_eq > 0 else 0.0
        b_c = omega * c_eq_f if c_eq_f > 0 and omega > 0 else 0.0
        b_l = 1.0 / (omega * l_eq) if l_eq > 0 and omega > 0 else 0.0
        y = complex(g, b_c - b_l)
        z = 1.0 / y if abs(y) > 1e-9 else 0j
        i_f = complex(v_rms, 0) * y

    z_mag = abs(z)
    ang_rad = cmath.phase(z)
    ang_deg = math.degrees(ang_rad)
    i_mag = abs(i_f)
    fp = math.cos(ang_rad)
    s = v_rms * i_mag
    p = s * fp
    q = s * math.sin(ang_rad)
    f0 = (1.0 / (2 * math.pi * math.sqrt(l_eq * c_eq_f))
          if l_eq > 0 and c_eq_f > 0 else 0.0)

    if es_mixto:
        diag, col = "Red Mixta (derivaciones intermedias)", "⚠️"
    elif l_eq == 0 and c_eq_f == 0:
        diag, col = "Puramente Resistivo (θ = 0°)", "🟡"
    elif c_eq_f == 0 and l_eq > 0:
        diag, col = "Inductivo — circuito RL (corriente se atrasa)", "🔵"
    elif l_eq == 0 and c_eq_f > 0:
        diag, col = "Capacitivo — circuito RC (corriente se adelanta)", "🟠"
    elif abs(x_n) < 1e-4:
        diag, col = "Resonancia — fasor en fase pura", "🟢"
    elif x_l > x_c:
        diag, col = "Inductivo — RLC (predomina XL)", "🔵"
    else:
        diag, col = "Capacitivo — RLC (predomina XC)", "🟠"

    return {
        "tipo": tipo, "es_mixto": es_mixto, "advertencia_topologia": advertencia,
        "omega": omega, "r_eq": r_eq, "l_eq": l_eq, "c_eq_uf": c_eq_uf, "c_eq_f": c_eq_f,
        "x_l": x_l, "x_c": x_c, "x_neta": x_n, "z_fasor": z, "z_mag": z_mag,
        "z_ang_deg": ang_deg, "i_mag": i_mag, "fp": fp, "p_activa": p,
        "q_reactiva": q, "s_aparente": s, "f0": f0,
        "comportamiento": diag, "estado_color": col, "v_rms": v_rms, "f": f_s
    }


# ==============================================================================
# 6. CLASIFICADOR DE MÓDULO
# ==============================================================================
MODULOS = {
    "M1": {
        "nombre": "Electrostática",
        "semanas": "1–3",
        "color": "#f59e0b",
        "keywords": [
            "coulomb", "ley de coulomb", "carga", "cargas", "q1", "q2", "q3", "µc", "μc", "uc", "nc", "mc", "pc",
            "campo eléctrico", "campo electrico", "potencial eléctrico",
            "potencial electrico", "energía potencial", "energia potencial",
            "capacitor", "condensador", "capacitores", "condensadores",
            "dieléctrico", "dielectrico", "permitividad", "gauss", "ley de gauss",
            "flujo eléctrico", "flujo electrico", "carga puntual", "cargas puntuales",
            "placas paralelas", "capacitancia", "q=cv", "eps0",
            "constante k", "k=9e9", "energía del capacitor", "fuerza entre cargas",
            "fuerza electrostática", "fuerza electrostatica", "fuerza eléctrica",
            "fuerza electrica", "electrostática", "electrostatica"
        ],
    },
    "M2": {
        "nombre": "Electrodinámica",
        "semanas": "4–7",
        "color": "#22c55e",
        "keywords": [
            "corriente", "amperios", "amperio", "ohm", "ohmios", "ohms", "resistencia", "resistencias",
            "resistividad", "kirchhoff", "mallas", "malla", "nodos", "nodo", "kvl", "kcl", "ddp",
            "fuente", "voltaje", "voltios", "tensión", "tension", "fem", "batería", "bateria", "resistor", "resistores",
            "transitorio", "rc transitorio", "carga rc", "descarga", "tiempo de relajación", "tiempo de relajacion", "tau",
            "constante de tiempo", "potencia eléctrica", "potencia electrica", "ley de ohm",
            "conductividad", "conductancia", "siemens", "energía disipada", "energia disipada",
            "efecto joule", "joule", "watt", "watts", "vatios", "r1", "r2", "r3", "ω", "Ω",
            "kohm", "kω", "kΩ", "electrodinámica", "electrodinamica"
        ],
    },
    "M3": {
        "nombre": "Magnetismo y CA",
        "semanas": "9–13",
        "color": "#38bdf8",
        "keywords": [
            "magnético", "magnetico", "magnetismo", "fuerza magnética", "fuerza magnetica",
            "conductor", "conductores", "alambre", "alambres", "fuerza magnética sobre un conductor",
            "fuerza sobre un conductor", "fuerza en un conductor",
            "lorentz", "biot-savart", "biot savart", "biot", "savart", "ampere", "ley de ampere",
            "bobina", "inductor", "inductores", "inductancia", "faraday", "lenz", "fem inducida",
            "flujo magnético", "flujo magnetico", "inducción", "induccion", "tesla", "weber",
            "henry", "henrios", "fasor", "fasores", "fasorial", "rlc", "impedancia", "reactancia",
            "xl", "xc", "corriente alterna", "frecuencia", "angular", "omega", "desfase",
            "potencia reactiva", "var", "factor de potencia", "resonancia", "circuitjs",
            "netlist", "simulador", "vrms", "irms", "valor eficaz", "valor pico", "serie rlc",
            "paralelo rlc"
        ],
    },
    "M4": {
        "nombre": "Electrónica",
        "semanas": "14–15",
        "color": "#a78bfa",
        "keywords": [
            "semiconductor", "semiconductores", "diodo", "diodos", "curva iv", "curva i-v",
            "rectificador", "rectificadores", "media onda", "onda completa", "puente", "graetz",
            "zener", "regulador", "reguladores", "polarización", "polarizacion", "directa",
            "inversa", "pn", "unión pn", "union pn", "transistor", "silicio", "germanio",
            "tipo n", "tipo p", "portador", "filtro capacitivo", "rizado", "v ripple",
            "umbral", "vth", "vz", "electrónica", "electronica"
        ],
    },
}


def clasificar_modulo(texto: str):
    t = texto.lower()
    if es_netlist_xml(texto) or es_netlist_texto(texto):
        return "M3"

    scores = {k: 0 for k in MODULOS}
    for mid, info in MODULOS.items():
        for kw in info["keywords"]:
            if kw in t:
                scores[mid] += 1

    # Heurísticas de apoyo basadas en patrones característicos
    # M1: Cargas (q, q1, q2, µC, μC, uC, nC) o Capacitores puros (c1, c2, µF sin inductores)
    if re.search(r'\bq\d*\b', t) or re.search(r'\b\d+(?:[.,]\d+)?\s*(?:µc|μc|uc|nc|mc|pc|coulomb)\b', t) or \
       ("carga" in t and any(u in t for u in ["µc", "μc", "uc", "nc", "mc", "c"])):
        scores["M1"] += 4
    if re.search(r'\bc\d*\s*[=:]\s*[\d.]+', t) or re.search(r'\b\d+(?:\.\d+)?\s*(?:µf|uf|nf|pf)\b', t):
        if not any(k in t for k in ["rlc", "inductor", "l=", "l1", "bobina", "hz", "frecuencia"]):
            if any(k in t for k in ["rc", "transitorio", "tau", "r=", "r1", "resistencia"]):
                scores["M2"] += 3
            else:
                scores["M1"] += 3

    # M2: Resistencia con fuente/voltaje (Ley de Ohm) o Resistencias sin inductores/capacitores AC
    if (re.search(r'\b\d+(?:[.,]\d+)?\s*(?:k?ohm|k?ohms|k?ohmios|k?[ωΩ])\b', t) or any(k in t for k in ["resistencia", "resistor", "ohm", "ohmios", "ω", "Ω"])) and \
       (any(k in t for k in ["fuente", "voltaje", "voltios", "tensión", "tension", "fem", "ddp", "batería", "bateria", "ley de ohm"]) or re.search(r'\b\d+(?:[.,]\d+)?\s*v\b', t)):
        if not any(k in t for k in ["rlc", "inductor", "l=", "bobina", "hz"]):
            scores["M2"] += 5
    elif (re.search(r'\br\d*\b', t) or re.search(r'\b\d+(?:[.,]\d+)?\s*(?:k?ohm|k?ohms|k?ohmios|k?[ωΩ])\b', t)) and not any(k in t for k in ["rlc", "inductor", "l=", "l1", "bobina", "hz"]):
        scores["M2"] += 2

    # M4: Diodos y semiconductores
    if any(k in t for k in ["zener", "diodo", "vth", "vz", "rectificador", "onda completa", "media onda", "puente"]):
        scores["M4"] += 4

    # M3: Magnetismo y CA
    if any(k in t for k in ["lorentz", "biot", "savart", "faraday", "lenz", "rlc", "henry", "henrios", "tesla"]):
        scores["M3"] += 4
    # Fuerza magnética sobre conductor/bobina
    if (any(k in t for k in ["fuerza magnética", "fuerza magnetica", "fuerza sobre el conductor", "fuerza sobre un conductor", "fuerza"])
            and any(k in t for k in ["alambre", "conductor", "espira", "bobina", "hilo", "devanado"])):
        scores["M3"] += 6
    if any(k in t for k in ["conductor", "alambre"]) and any(k in t for k in ["tesla", "t", "campo", "b=", "corriente", "a", "ma"]):
        scores["M3"] += 4

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None


# ==============================================================================
# 7. HELPERS PARA PARSEO NUMÉRICO Y UNIDADES
# ==============================================================================
def extraer_capacitancias_texto(texto: str):
    """
    Extrae valores de capacitancia reconociendo 'µ' y 'u' (ej. 10uF, 10µF, 10u, 10µ),
    además de nF, pF y Faradios directos.
    Multiplica por 1e-6 para 'µ' y 'u', evitando números erróneos o colapsos en las unidades.
    Retorna lista de dicts con:
      - 'raw': número base original (ej. 10.0)
      - 'unit': texto de la unidad (ej. 'uf', 'µf')
      - 'faradios': valor real en Faradios (SI), ej. 10 * 1e-6 = 1e-5
      - 'microfaradios': valor normalizado en µF, ej. 10.0
    """
    patron = r'(?:c\d*|capacit(?:or|ancia|ador)?\d*)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?(?:e[-+]?[0-9]+)?)\s*(µf|uf|µ|u|nf|n|pf|p|f|microfaradios?)?\b'
    matches = re.finditer(patron, texto, re.IGNORECASE)
    res = []
    for m in matches:
        num_str = m.group(1)
        unit = (m.group(2) or '').lower()
        if not num_str:
            continue
        val = float(num_str)
        full = m.group(0).lower().strip()
        if not full:
            continue
        # Asegurar que corresponde a un capacitor
        if any(c in full for c in ['c', 'µ', 'u', 'f', 'cap']):
            if unit in ['µf', 'uf', 'µ', 'u', 'microfaradio', 'microfaradios']:
                farads = val * 1e-6
            elif unit in ['nf', 'n']:
                farads = val * 1e-9
            elif unit in ['pf', 'p']:
                farads = val * 1e-12
            elif unit == 'f':
                farads = val
            else:
                farads = val * 1e-6 if val >= 0.01 else val
            res.append({
                'raw': val,
                'unit': unit,
                'faradios': farads,
                'microfaradios': round(farads * 1e6, 6)
            })
    return res


def _num(patron, texto, default=None):
    m = re.search(patron, texto, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return default


def _nums(patron, texto):
    return [float(x) for x in re.findall(patron, texto, re.IGNORECASE)]


def extraer_cargas_texto(texto: str):
    """
    Extrae valores de cargas eléctricas (q) a partir de texto en lenguaje natural o estándar.
    Reconoce unidades: µC, μC, uC, nC, mC, pC y C (Coulombs).
    Asigna signos automáticamente respetando:
    - Signos explícitos (+ o -).
    - Contexto inmediato ('positiva', 'negativa').
    - Calificador global ('dos cargas positivas', 'dos cargas negativas', 'ambas negativas', etc.).
    Retorna lista de diccionarios:
      [{"val": float_en_coulombs, "mag": float_abs, "unit": str, "signo": int (+1 o -1),
        "texto_signo": str, "span": (start, end)}]
    """
    t = texto.lower()
    global_neg = any(p in t for p in ["dos cargas negativas", "ambas negativas", "cargas negativas", "ambas sean negativas", "todas negativas", "dos negativas", "las dos negativas"])
    global_pos = any(p in t for p in ["dos cargas positivas", "ambas positivas", "cargas positivas", "ambas sean positivas", "todas positivas", "dos positivas", "las dos positivas"])

    patron = re.compile(
        r'([+\-]?\s*\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*([µμu]c|microcoulombs?|nc|nanocoulombs?|mc|milicoulombs?|pc|picocoulombs?|coulombs?|c\b(?![a-zA-Z]))',
        re.IGNORECASE
    )

    cargas = []
    for m in patron.finditer(texto):
        num_raw = m.group(1).replace(" ", "").replace(",", ".")
        unit = m.group(2).lower()
        start, end = m.span()
        try:
            val_base = float(num_raw)
        except Exception:
            continue

        if any(u in unit for u in ["µc", "μc", "uc", "microcoulomb"]):
            mult = 1e-6
        elif any(u in unit for u in ["nc", "nanocoulomb"]):
            mult = 1e-9
        elif any(u in unit for u in ["pc", "picocoulomb"]):
            mult = 1e-12
        elif any(u in unit for u in ["mc", "milicoulomb"]):
            mult = 1e-3
        else:
            mult = 1.0

        # Determinación de signo
        if "-" in m.group(1):
            signo = -1
        elif "+" in m.group(1):
            signo = 1
        else:
            ctx_before = t[max(0, start - 30):start]
            ctx_after = t[end:min(len(t), end + 30)]
            ctx = ctx_before + " " + ctx_after
            if "negativ" in ctx and "positiv" not in ctx:
                signo = -1
            elif "positiv" in ctx and "negativ" not in ctx:
                signo = 1
            elif global_neg:
                signo = -1
            elif global_pos:
                signo = 1
            else:
                signo = 1

        val_coulomb = signo * abs(val_base) * mult
        cargas.append({
            "val": val_coulomb,
            "mag": abs(val_coulomb),
            "unit": unit,
            "signo": signo,
            "texto_signo": "positiva" if signo > 0 else "negativa",
            "span": (start, end)
        })
    return cargas


def extraer_distancia_texto(texto: str, exclusion_spans=None):
    """
    Extrae la distancia r en metros a partir de lenguaje natural o fórmulas estándar.
    Reconoce mm, cm y m. Maneja 'separadas 30 cm', 'distancia de 0.3 m', etc.
    """
    exclusion_spans = exclusion_spans or []

    # 1. Patrón con palabras clave de distancia
    patron_kw = re.compile(
        r'(?:r12|r23|r(?![0-9_a-zA-Z])|d|distancia|separaci[oó]n|separad[ao]s?(?:\s+(?:por|a|de))?)\s*(?:de|por|[=:])?\s*([+\-]?\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(mm|cm|m)?\b',
        re.IGNORECASE
    )
    for m in patron_kw.finditer(texto):
        start, end = m.span()
        if any(es <= start and end <= ee for es, ee in exclusion_spans):
            continue
        try:
            num = float(m.group(1).replace(",", "."))
            unit = (m.group(2) or "m").lower()
            if unit == "cm":
                return num * 1e-2
            elif unit == "mm":
                return num * 1e-3
            elif unit == "m":
                return num
            return num
        except Exception:
            continue

    # 2. Patrón de cualquier medida con cm, mm o m que no sea carga
    patron_medida = re.compile(r'\b(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(cm|mm|m)\b', re.IGNORECASE)
    for m in patron_medida.finditer(texto):
        start, end = m.span()
        if any(es <= start and end <= ee for es, ee in exclusion_spans):
            continue
        unit = m.group(2).lower()
        try:
            num = float(m.group(1).replace(",", "."))
            if unit == "cm":
                return num * 1e-2
            elif unit == "mm":
                return num * 1e-3
            elif unit == "m":
                return num
        except Exception:
            continue
    return None


def extraer_resistencias_ohm(texto: str):
    """
    Extrae todas las resistencias en Ohmios (Ω) a partir de prosa o fórmulas.
    Reconoce 10 Ω, 10 ohm, 10 kohm (10000 Ω), 2.2 MΩ, 'resistencia de 10 Ω', etc.
    """
    res = []
    # Patrón con unidad explícita (Ω, ohm, etc.) con posibles prefijos (k, M, m)
    patron_unit = re.compile(
        r'(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(k|m|meg)?\s*(?:[ωΩ]|ohm|ohms|ohmios)\b',
        re.IGNORECASE
    )
    for m in patron_unit.finditer(texto):
        try:
            val = float(m.group(1).replace(",", "."))
            pfx = (m.group(2) or "").lower()
            if pfx == "k":
                val *= 1e3
            elif pfx in ("m", "meg"):
                val *= 1e6
            res.append(val)
        except Exception:
            continue

    # Si no encontró con unidades explícitas, busca 'resistencia de X' o 'R = X'
    if not res:
        patron_kw = re.compile(
            r'(?:resistencia|resistor|r\d*)\s*(?:de|[=:])?\s*(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(k|m|meg)?\b',
            re.IGNORECASE
        )
        for m in patron_kw.finditer(texto):
            try:
                val = float(m.group(1).replace(",", "."))
                pfx = (m.group(2) or "").lower()
                if pfx == "k":
                    val *= 1e3
                elif pfx in ("m", "meg"):
                    val *= 1e6
                res.append(val)
            except Exception:
                continue
    return res


def extraer_voltaje_texto(texto: str):
    """
    Extrae el voltaje V en Voltios a partir de prosa o fórmulas.
    Reconoce 'fuente de 20 V', 'voltaje de 20 V', 'tensión de 20 V', 'batería de 20 V', '20 V', 'V = 20 V', etc.
    """
    # 1. Con palabra clave (fuente, voltaje, etc.)
    patron_kw = re.compile(
        r'(?:fuente|voltaje|tensi[oó]n|ddp|fem|bater[ií]a|vs|v\d*)\s*(?:de|[=:])?\s*(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(k|m)?\s*(?:v|voltios?|volts?)\b',
        re.IGNORECASE
    )
    m = patron_kw.search(texto)
    if m:
        try:
            val = float(m.group(1).replace(",", "."))
            pfx = (m.group(2) or "").lower()
            if pfx == "k":
                val *= 1e3
            elif pfx == "m":
                val *= 1e-3
            return val
        except Exception:
            pass

    # 1b. Con palabra clave sin unidad V explícita (ej. 'fuente de 20', 'voltaje de 20')
    patron_kw_no_unit = re.compile(
        r'(?:fuente|voltaje|tensi[oó]n|ddp|fem|bater[ií]a)\s*(?:de|[=:])?\s*(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\b',
        re.IGNORECASE
    )
    m = patron_kw_no_unit.search(texto)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except Exception:
            pass

    # 2. Número con unidad V (ej. '20 V', '20 voltios', '12V')
    patron_v = re.compile(r'\b(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(k|m)?\s*(?:v|voltios?|volts?)\b', re.IGNORECASE)
    for m in patron_v.finditer(texto):
        try:
            val = float(m.group(1).replace(",", "."))
            pfx = (m.group(2) or "").lower()
            if pfx == "k":
                val *= 1e3
            elif pfx == "m":
                val *= 1e-3
            return val
        except Exception:
            continue
    return None


def extraer_corriente_texto(texto: str):
    """
    Extrae la corriente I en Amperios a partir de prosa o fórmulas.
    Reconoce 'corriente de 2 A', '2 A', '500 mA', 'I = 2 A', etc.
    """
    patron_kw = re.compile(
        r'(?:corriente|intensidad|i\d*)\s*(?:de|[=:])?\s*(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(m|µ|μ|u|k)?\s*(?:a|amperios?|ampere|amps?)\b',
        re.IGNORECASE
    )
    m = patron_kw.search(texto)
    if m:
        try:
            val = float(m.group(1).replace(",", "."))
            pfx = (m.group(2) or "").lower()
            if pfx in ("m",):
                val *= 1e-3
            elif pfx in ("µ", "μ", "u"):
                val *= 1e-6
            elif pfx == "k":
                val *= 1e3
            return val
        except Exception:
            pass

    patron_a = re.compile(r'\b(\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(m|µ|μ|u|k)?\s*(?:a|amperios?|ampere|amps?)\b', re.IGNORECASE)
    for m in patron_a.finditer(texto):
        try:
            val = float(m.group(1).replace(",", "."))
            pfx = (m.group(2) or "").lower()
            if pfx in ("m",):
                val *= 1e-3
            elif pfx in ("µ", "μ", "u"):
                val *= 1e-6
            elif pfx == "k":
                val *= 1e3
            return val
        except Exception:
            continue
    return None


# ==============================================================================
# 8. SOLUCIONADOR MÓDULO 1: ELECTROSTÁTICA
# ==============================================================================
def resolver_modulo1(texto: str) -> str:
    t = texto.lower()
    K = 8.9875e9

    cargas_detectadas = extraer_cargas_texto(texto)

    # Ley de Coulomb (Soporta 2 o 3 cargas, en lenguaje natural o estándar)
    if any(k in t for k in ["coulomb", "fuerza", "q1", "q2", "q3", "r12", "r23", "carga", "cargas"]) or len(cargas_detectadas) >= 2:
        def _parse_carga(nombre, txt):
            try:
                # Patrón flexible para capturar signos y unidades (incluyendo uC, µC, μC, C)
                patron = rf'{nombre}\s*[=:]?\s*([+\-]?\d+(?:\.\d+)?(?:e[+\-]?\d+)?)\s*([µμu]c|nc|mc|pc|c)?\b'
                m = re.search(patron, txt, re.IGNORECASE)
                if not m:
                    return None
                val = float(m.group(1))
                unit = (m.group(2) or "").lower()
                if unit in ("µc", "μc", "uc"):
                    val *= 1e-6
                elif unit == "nc":
                    val *= 1e-9
                elif unit == "mc":
                    val *= 1e-3
                elif unit == "pc":
                    val *= 1e-12
                elif not unit:
                    # Inferencia global si no tiene unidad pegada
                    if any(u in txt for u in ["µc", "μc", "uc"]):
                        val *= 1e-6
                return val
            except Exception:
                return None

        def _parse_dist(patrones_str, txt):
            try:
                patron = rf'(?:{patrones_str})\s*[=:]?\s*([+\-]?\d+(?:\.\d+)?(?:e[+\-]?\d+)?)\s*(mm|cm|m)?\b'
                m = re.search(patron, txt, re.IGNORECASE)
                if not m:
                    return None
                val = float(m.group(1))
                unit = (m.group(2) or "").lower()
                if unit == "cm":
                    val *= 1e-2
                elif unit == "mm":
                    val *= 1e-3
                return val
            except Exception:
                return None

        q1 = _parse_carga("q1", t)
        q2 = _parse_carga("q2", t)
        q3 = _parse_carga("q3", t)

        # Si no se definieron por q1, q2 explícitamente, asignar desde cargas en lenguaje natural
        if q1 is None and len(cargas_detectadas) >= 1:
            q1 = cargas_detectadas[0]["val"]
        if q2 is None and len(cargas_detectadas) >= 2:
            q2 = cargas_detectadas[1]["val"]
        if q3 is None and len(cargas_detectadas) >= 3:
            q3 = cargas_detectadas[2]["val"]
        
        # Búsqueda robusta de r12 y r23 (incluso si están escritas como r_12, r12, etc.)
        r12 = _parse_dist(r"r12|r_12|r_{12}", t)
        r23 = _parse_dist(r"r23|r_23|r_{23}", t)

        # Caso: 3 cargas lineales (q1, q2, q3) con distancias r12 y r23
        if (q1 is not None and q2 is not None and q3 is not None and
                r12 is not None and r23 is not None and r12 > 0 and r23 > 0):
            def _fmt_carga(c):
                return f"{c:.3e}\\;\\text{{C}}"

            # Fuerza que ejerce q1 sobre q2 (F12)
            F12_mag = K * abs(q1 * q2) / (r12 ** 2)
            if q1 * q2 > 0:
                F12_tipo = "repulsiva"
                F12_sign = 1.0
                F12_sentido = "hacia la derecha (+x, alejándose de $q_1$)"
            else:
                F12_tipo = "atractiva"
                F12_sign = -1.0
                F12_sentido = "hacia la izquierda (-x, acercándose a $q_1$)"
            F12_vec = F12_sign * F12_mag

            # Fuerza que ejerce q3 sobre q2 (F23)
            F23_mag = K * abs(q3 * q2) / (r23 ** 2)
            if q3 * q2 > 0:
                F23_tipo = "repulsiva"
                F23_sign = -1.0
                F23_sentido = "hacia la izquierda (-x, alejándose de $q_3$)"
            else:
                F23_tipo = "atractiva"
                F23_sign = 1.0
                F23_sentido = "hacia la derecha (+x, acercándose a $q_3$)"
            F23_vec = F23_sign * F23_mag

            # Superposición lineal: fuerza neta sobre q2
            F_neta = F12_vec + F23_vec
            if abs(F_neta) < 1e-12:
                dir_neta = "nula (las fuerzas se equilibran)"
                sentido_neta = "sin dirección definida"
            elif F_neta > 0:
                dir_neta = "hacia la derecha (+x)"
                sentido_neta = "hacia $q_3$"
            else:
                dir_neta = "hacia la izquierda (-x)"
                sentido_neta = "hacia $q_1$"

            return f"""
### 🟡 [M1 — Electrostática] Ley de Coulomb — Superposición (3 cargas lineales)

**Configuración asumida (lineal):** $q_1 \\;\\xrightarrow{{r_{{12}}}}\\; q_2 \\;\\xrightarrow{{r_{{23}}}}\\; q_3$  
*(Eje $x$ positivo hacia la derecha: $q_1$ a la izquierda, $q_2$ en el centro, $q_3$ a la derecha.)*

**Constante:** $k = 8.9875 \\times 10^9\\;\\text{{N·m²/C²}}$

**Datos:**
- $q_1 = {_fmt_carga(q1)}$
- $q_2 = {_fmt_carga(q2)}$
- $q_3 = {_fmt_carga(q3)}$
- $r_{{12}} = {r12}\\;\\text{{m}}$ (distancia entre $q_1$ y $q_2$)
- $r_{{23}} = {r23}\\;\\text{{m}}$ (distancia entre $q_2$ y $q_3$)

---

#### 1) Fuerza que ejerce $q_1$ sobre $q_2$ ($\\vec F_{{12}}$)
**Fórmula (magnitud):**
$$F_{{12}} = k\\,\\frac{{|q_1\\,q_2|}}{{r_{{12}}^2}}$$

**Sustitución:**
$$F_{{12}} = (8.9875\\times10^9)\\cdot\\frac{{\\left|({q1:.3e})\\cdot({q2:.3e})\\right|}}{{({r12})^2}}$$

**Resultado parcial:**
$$F_{{12}} = {F12_mag:.4e}\\;\\text{{N}}\\quad\\text{{({F12_tipo})}}$$

**Dirección sobre $q_2$:** {F12_sentido}  
$$\\vec F_{{12}} = {F12_vec:+.4e}\\;\\text{{N}}\\;\\hat{{\\imath}}$$

---

#### 2) Fuerza que ejerce $q_3$ sobre $q_2$ ($\\vec F_{{23}}$)
**Fórmula (magnitud):**
$$F_{{23}} = k\\,\\frac{{|q_3\\,q_2|}}{{r_{{23}}^2}}$$

**Sustitución:**
$$F_{{23}} = (8.9875\\times10^9)\\cdot\\frac{{\\left|({q3:.3e})\\cdot({q2:.3e})\\right|}}{{({r23})^2}}$$

**Resultado parcial:**
$$F_{{23}} = {F23_mag:.4e}\\;\\text{{N}}\\quad\\text{{({F23_tipo})}}$$

**Dirección sobre $q_2$:** {F23_sentido}  
$$\\vec F_{{23}} = {F23_vec:+.4e}\\;\\text{{N}}\\;\\hat{{\\imath}}$$

---

#### 3) Superposición lineal — Fuerza neta sobre $q_2$
**Fórmula:**
$$\\vec F_{{neta,2}} = \\vec F_{{12}} + \\vec F_{{23}}$$

**Sustitución:**
$$\\vec F_{{neta,2}} = ({F12_vec:+.4e}) + ({F23_vec:+.4e})\\;\\text{{N}}\\;\\hat{{\\imath}}$$

$$\\boxed{{\\vec F_{{neta,2}} = {F_neta:+.4e}\\;\\text{{N}}\\;\\hat{{\\imath}}\\quad\\left(|\\vec F_{{neta,2}}| = {abs(F_neta):.4e}\\;\\text{{N}},\\; {dir_neta},\\; \\text{{hacia }} q_3\\right)}}$$
"""

        # Caso: 2 cargas (lenguaje natural o estándar)
        if q1 is not None or q2 is not None or len(cargas_detectadas) >= 2:
            if q1 is None:
                q1 = 1.0
            if q2 is None:
                q2 = 1.0

            # Extraer distancia r considerando lenguaje natural (cm, mm, m, 'separadas 30 cm', etc.)
            exclusion_spans = [c["span"] for c in cargas_detectadas]
            r = extraer_distancia_texto(texto, exclusion_spans=exclusion_spans)
            if (r is None or r <= 0) and r12 is not None and r12 > 0:
                r = r12
            if r is None or r <= 0:
                r = _parse_dist(r"r(?![0-9_])|d|distancia|separaci[oó]n", t)
            if r is None or r <= 0:
                r = 1.0

            F = K * abs(q1 * q2) / (r ** 2)
            es_repulsiva = (q1 * q2 > 0)
            signo_texto = "repulsiva (mismo signo)" if es_repulsiva else "atractiva (signos opuestos)"
            
            explicacion_interaccion = (
                f"Dado que ambas cargas tienen el **mismo signo** "
                f"({'ambas positivas' if q1 > 0 else 'ambas negativas'}), la fuerza es **repulsiva** "
                f"(las cargas experimentan repulsión mutua, alejándose entre sí)."
                if es_repulsiva else
                "Dado que las cargas tienen **signos opuestos** "
                "(una positiva y otra negativa), la fuerza es **atractiva** "
                "(las cargas experimentan atracción mutua, acercándose entre sí)."
            )

            return f"""
### 🟡 [M1 — Electrostática] Ley de Coulomb

**Enunciado interpretado:** Fuerza electrostática entre dos cargas puntuales en reposo en el vacío/aire.

**Ley de Coulomb:**
$$F = k\\,\\frac{{|q_1\\,q_2|}}{{r^2}}$$

**Constante electrostática:**
$$k = 8.9875 \\times 10^9\\;\\text{{N·m²/C²}}$$

**Datos extraídos:**
- $q_1 = {q1:.3e}\\;\\text{{C}}$ ({'positiva' if q1 > 0 else 'negativa'})
- $q_2 = {q2:.3e}\\;\\text{{C}}$ ({'positiva' if q2 > 0 else 'negativa'})
- Distancia ($r$): ${r}\\;\\text{{m}}$

---

#### 1) Producto de las magnitudes de las cargas
$$|q_1 \\cdot q_2| = |({q1:.3e}) \\cdot ({q2:.3e})| = {abs(q1 * q2):.4e}\\;\\text{{C}}^2$$

#### 2) Cuadrado de la distancia de separación
$$r^2 = ({r})^2 = {r**2:.4g}\\;\\text{{m}}^2$$

#### 3) Magnitud de la fuerza eléctrica paso a paso
$$F = (8.9875\\times10^9)\\cdot\\frac{{{abs(q1 * q2):.4e}}}{{{r**2:.4g}}}$$

$$\\boxed{{F = {F:.4e}\\;\\text{{N}}\\ —\\ \\text{{Fuerza {signo_texto}}}}}$$

---

#### 4) Naturaleza de la interacción
{explicacion_interaccion}
"""

    # Campo eléctrico puntual
    if any(k in t for k in ["campo eléctrico", "campo electrico", "campo e"]):
        q = _num(r'(?:q|carga)\s*[=:]\s*([\d.eE+\-]+)', t, 1.0)
        r = _num(r'(?:r|d|distancia)\s*[=:]\s*([\d.]+)', t, 1.0)
        fac = 1e-6 if ("µc" in t or "uc" in t) else (1e-9 if "nc" in t else 1.0)
        q *= fac
        E = K * abs(q) / r**2
        return f"""
### 🟡 [M1 — Electrostática] Campo Eléctrico de Carga Puntual
**Fórmula:**
$$E = k\\,\\frac{{|q|}}{{r^2}}$$

**Datos:** $q = {q:.3e}\\;\\text{{C}}$, $r = {r}\\;\\text{{m}}$

$$\\boxed{{E = {E:.4e}\\;\\text{{N/C}} = {E:.4e}\\;\\text{{V/m}}}}$$

*Dirección: radial desde la carga ({("saliente" if q > 0 else "entrante")} para carga {"positiva" if q > 0 else "negativa"}).*
"""

    # Capacitores
    if any(k in t for k in ["capacitor", "condensador", "capacitancia", "capacitores",
                             "condensadores", "farad", "c1", "c2", "c3", "c ="]):
        caps_info = extraer_capacitancias_texto(t)
        vals = [c["faradios"] for c in caps_info] if caps_info else []
        V = _num(r'(?:v|voltaje|tensi[oó]n)\s*[=:]\s*([\d.]+)', t, 0.0)
        es_par = "paralelo" in t
        if not vals:
            return "⚠️ No encontré valores de capacitancia. Ejemplo: `C1=10uF, C2=22µF en paralelo, V=12V`."
        def _fmt_si(val, base_unit, prefixes):
            mag = abs(val)
            for factor, unit in prefixes:
                if mag < factor[1]:
                    num = val / factor[0]
                    s = f"{num:.4g}"
                    if "e" in s or "E" in s:
                        s = f"{num:.4e}".replace("+0", "+").replace("-0", "-")
                    return f"{s}\\;{unit}"
            num = val
            s = f"{num:.4g}"
            if "e" in s or "E" in s:
                s = f"{num:.4e}".replace("+0", "+").replace("-0", "-")
            return f"{s}\\;\\text{{{base_unit}}}"

        def formatear_capacitancia(val_faradios):
            val = abs(val_faradios)
            if val < 1e-9:
                num, unit = val_faradios * 1e12, r"\text{pF}"
            elif val < 1e-6:
                num, unit = val_faradios * 1e9, r"\text{nF}"
            elif val < 1e-3:
                num, unit = val_faradios * 1e6, r"\mu\text{F}"
            elif val < 1:
                num, unit = val_faradios * 1e3, r"\text{mF}"
            else:
                num, unit = val_faradios, r"\text{F}"
            s = f"{num:.4g}"
            if "e" in s or "E" in s:
                s = f"{num:.4e}".replace("+0", "+").replace("-0", "-")
            return f"{s}\\;{unit}"

        def formatear_carga(val_coulombs):
            mag = abs(val_coulombs)
            if mag < 1e-9:
                num, unit = val_coulombs * 1e12, r"\text{pC}"
            elif mag < 1e-6:
                num, unit = val_coulombs * 1e9, r"\text{nC}"
            elif mag < 1e-3:
                num, unit = val_coulombs * 1e6, r"\mu\text{C}"
            elif mag < 1:
                num, unit = val_coulombs * 1e3, r"\text{mC}"
            else:
                num, unit = val_coulombs, r"\text{C}"
            s = f"{num:.4g}"
            if "e" in s or "E" in s:
                s = f"{num:.4e}".replace("+0", "+").replace("-0", "-")
            return f"{s}\\;{unit}"

        def formatear_energia(val_joules):
            mag = abs(val_joules)
            if mag < 1e-6:
                num, unit = val_joules * 1e9, r"\text{nJ}"
            elif mag < 1e-3:
                num, unit = val_joules * 1e6, r"\mu\text{J}"
            elif mag < 1:
                num, unit = val_joules * 1e3, r"\text{mJ}"
            else:
                num, unit = val_joules, r"\text{J}"
            s = f"{num:.4g}"
            if "e" in s or "E" in s:
                s = f"{num:.4e}".replace("+0", "+").replace("-0", "-")
            return f"{s}\\;{unit}"

        es_mixto_c = (
            len(vals) >= 3 and (
                "mixto" in t or
                ("en serie" in t and "paralelo con" in t) or
                ("serie" in t and "paralelo con c3" in t) or
                re.search(r"c1\s*y\s*c2\s+en\s+serie.*paralelo\s+con\s*c3", t)
            )
        )
        if es_mixto_c:
            c1, c2, c3 = vals[0], vals[1], vals[2]
            if c1 <= 0 or c2 <= 0 or c3 <= 0:
                return "⚠️ Para un circuito mixto de 3 capacitores, C1, C2 y C3 deben ser mayores que 0."
            C12 = (c1 * c2) / (c1 + c2)
            Ceq = C12 + c3
            if V > 0:
                Q12 = C12 * V
                Q1 = Q12
                Q2 = Q12
                V1 = Q1 / c1
                V2 = Q1 / c2
                Q3 = c3 * V
                Q_total = Ceq * V
                U_total = 0.5 * Ceq * V**2
                if hasattr(st, "session_state"):
                    st.session_state["sim_circuito"] = {
                        "v_rms": V,
                        "f": 0.001,
                        "comps": [{"tipo": "C", "val": c["microfaradios"]} for c in caps_info[:3]],
                        "tipo": "mixto_c",
                    }
                return f"""
### 🟡 [M1 — Electrostática] Capacitores en circuito mixto (C1-C2 en serie, en paralelo con C3)

**Datos:** $C_1 = {formatear_capacitancia(c1)}$, $C_2 = {formatear_capacitancia(c2)}$, $C_3 = {formatear_capacitancia(c3)}$, $V = {V}\\;\\text{{V}}$

**1) Rama serie (C1 y C2):**
$$C_{{12}} = \\frac{{C_1 \\cdot C_2}}{{C_1 + C_2}} = {formatear_capacitancia(C12)}$$

**2) Equivalente total (C12 en paralelo con C3):**
$$C_{{eq}} = C_{{12}} + C_3 = {formatear_capacitancia(Ceq)}$$

**3) Cargas y voltajes:**
- Rama serie: $Q_1 = Q_2 = Q_{{12}} = C_{{12}} \\cdot V = {Q12:.4e}\\;\\text{{C}}$
- Voltajes individuales: $V_1 = \\frac{{Q_1}}{{C_1}} = {V1:.6g}\\;\\text{{V}}$, $V_2 = \\frac{{Q_1}}{{C_2}} = {V2:.6g}\\;\\text{{V}}$
- Rama paralela (C3): $Q_3 = C_3 \\cdot V = {Q3:.4e}\\;\\text{{C}}$

**4) Totales del circuito:**
- Carga total: $Q_{{total}} = C_{{eq}} \\cdot V = {Q_total:.4e}\\;\\text{{C}}$
- Energía total: $U = \\frac{{1}}{{2}} C_{{eq}} V^2 = {U_total:.4e}\\;\\text{{J}}$
"""
            # Sin voltaje explícito: al menos equivalente y pasos básicos
            return f"""
### 🟡 [M1 — Electrostática] Capacitores en circuito mixto (C1-C2 en serie, en paralelo con C3)

**Datos:** $C_1 = {formatear_capacitancia(c1)}$, $C_2 = {formatear_capacitancia(c2)}$, $C_3 = {formatear_capacitancia(c3)}$

**1) Rama serie (C1 y C2):**
$$C_{{12}} = \\frac{{C_1 \\cdot C_2}}{{C_1 + C_2}} = {formatear_capacitancia(C12)}$$

**2) Equivalente total (C12 en paralelo con C3):**
$$C_{{eq}} = C_{{12}} + C_3 = {formatear_capacitancia(Ceq)}$$

*Indica un voltaje $V$ para calcular $Q_1, Q_2, V_1, V_2, Q_3$, carga y energía total.*
"""

        if es_par:
            Ceq = sum(vals)
            modo, formula = "Paralelo", r"C_{eq} = \sum C_i"
        else:
            Ceq = 1.0 / sum(1.0 / c for c in vals if c > 0) if all(v > 0 for v in vals) else 0.0
            modo, formula = "Serie", r"C_{eq} = \left(\sum \frac{1}{C_i}\right)^{-1}"
        lista_str = " + ".join([f"{formatear_capacitancia(c)}" for c in vals])
        extra = ""
        if V > 0:
            E_cap = 0.5 * Ceq * V**2
            Q_cap = Ceq * V
            extra = (f"\n**Con $V = {V}\\;\\text{{V}}$:**\n"
                     f"- Carga: $Q = C_{{eq}}V = {formatear_carga(Q_cap)}$\n"
                     f"- Energía: $U = \\frac{{1}}{{2}}C_{{eq}}V^2 = {formatear_energia(E_cap)}$")
            if hasattr(st, "session_state"):
                st.session_state["sim_circuito"] = {
                    "v_rms": V,
                    "f": 0.001,
                    "comps": [{"tipo": "C", "val": c["microfaradios"]} for c in caps_info],
                    "tipo": "paralelo" if es_par else "serie",
                }
        return f"""
### 🟡 [M1 — Electrostática] Capacitores en {modo}
**Fórmula:** ${formula}$

**Capacitores identificados:** ${lista_str}$

$$\\boxed{{C_{{eq}} = {formatear_capacitancia(Ceq)}}}$$
{extra}
"""

    # Potencial eléctrico
    if any(k in t for k in ["potencial eléctrico", "potencial electrico", "potencial v"]):
        q = _num(r'(?:q|carga)\s*[=:]\s*([\d.eE+\-]+)', t, 1.0)
        r = _num(r'(?:r|distancia)\s*[=:]\s*([\d.]+)', t, 1.0)
        fac = 1e-6 if ("µc" in t or "uc" in t) else (1e-9 if "nc" in t else 1.0)
        q *= fac
        V_pot = K * q / r
        return f"""
### 🟡 [M1 — Electrostática] Potencial Eléctrico
**Fórmula:**
$$V = k\\,\\frac{{q}}{{r}}$$

**Datos:** $q = {q:.3e}\\;\\text{{C}}$, $r = {r}\\;\\text{{m}}$

$$\\boxed{{V = {V_pot:.4e}\\;\\text{{V}}}}$$
"""

    return """
### 🟡 [M1 — Electrostática] Temas Disponibles
Escribe tu ejercicio mencionando los datos. Ejemplos:
- `Fuerza entre q1=5µC y q2=-3µC separadas 0.3 m`
- `Campo eléctrico a 0.5 m de una carga de 2µC`
- `C1=10µF C2=22µF en paralelo, V=12V`
- `Potencial eléctrico a 0.2m de q=4nC`
"""


# ==============================================================================
# 9. SOLUCIONADOR MÓDULO 2: ELECTRODINÁMICA
# ==============================================================================
def resolver_modulo2(texto: str) -> str:
    t = texto.lower()

    # Resistencias y Ley de Ohm
    if any(k in t for k in ["resistencia", "resistor", "r1", "r2", "r3", "equivalente", "ohm", "ohmios", "ohms",
                             "ley de ohm", "fuente", "voltaje", "voltios", "tensión", "tension",
                             "corriente", "amperio", "amperios", "ω", "Ω", "ddp", "fem", "batería", "bateria"]):
        vals_r = extraer_resistencias_ohm(texto)
        V = extraer_voltaje_texto(texto)
        I = extraer_corriente_texto(texto)
        es_par = "paralelo" in t

        # Caso 1: Ley de Ohm directa (Resistencia y Voltaje conocidos -> calcula I paso a paso)
        if V is not None and V > 0 and len(vals_r) == 1 and not es_par and I is None:
            R_val = vals_r[0]
            I_calc = V / R_val if R_val > 0 else 0.0
            P_calc = V * I_calc
            return f"""
### 🟢 [M2 — Electrodinámica] Ley de Ohm

**Enunciado interpretado:** Circuito elemental con resistencia conectada a una fuente de voltaje continuo (DC).

**Ley de Ohm:**
La intensidad de corriente ($I$) que circula por un circuito eléctrico es directamente proporcional al voltaje o diferencia de potencial ($V$) aplicado, e inversamente proporcional a la resistencia ($R$) del conductor:
$$I = \\frac{{V}}{{R}}$$

**Datos extraídos:**
- Voltaje de la fuente ($V$): ${V:.4g}\\;\\text{{V}}$
- Resistencia ($R$): ${R_val:.4g}\\;\\Omega$

---

#### 1) Cálculo de la corriente eléctrica ($I$)
**Fórmula:**
$$I = \\frac{{V}}{{R}}$$

**Sustitución:**
$$I = \\frac{{{V:.4g}\\;\\text{{V}}}}{{{R_val:.4g}\\;\\Omega}}$$

**Resultado:**
$$\\boxed{{I = {I_calc:.4f}\\;\\text{{A}} = {I_calc * 1000:.2f}\\;\\text{{mA}}}}$$

---

#### 2) Potencia eléctrica disipada (Efecto Joule)
**Fórmula:**
$$P = V \\cdot I = \\frac{{V^2}}{{R}} = I^2 \\cdot R$$

**Sustitución:**
$$P = ({V:.4g}\\;\\text{{V}}) \\cdot ({I_calc:.4f}\\;\\text{{A}})$$

$$\\boxed{{P = {P_calc:.4f}\\;\\text{{W}}}}$$
"""

        # Caso 2: Ley de Ohm con V e I conocidos (calcula R paso a paso)
        if V is not None and V > 0 and I is not None and I > 0 and not vals_r:
            R_calc = V / I
            P_calc = V * I
            return f"""
### 🟢 [M2 — Electrodinámica] Ley de Ohm

**Ley de Ohm:**
$$R = \\frac{{V}}{{I}}$$

**Datos extraídos:**
- Voltaje ($V$): ${V:.4g}\\;\\text{{V}}$
- Corriente ($I$): ${I:.4g}\\;\\text{{A}}$

---

#### 1) Cálculo de la resistencia ($R$)
**Fórmula:**
$$R = \\frac{{V}}{{I}}$$

**Sustitución:**
$$R = \\frac{{{V:.4g}\\;\\text{{V}}}}{{{I:.4g}\\;\\text{{A}}}}$$

$$\\boxed{{R = {R_calc:.4f}\\;\\Omega}}$$

---

#### 2) Potencia eléctrica disipada
$$P = V \\cdot I = ({V:.4g}\\;\\text{{V}}) \\cdot ({I:.4g}\\;\\text{{A}})$$
$$\\boxed{{P = {P_calc:.4f}\\;\\text{{W}}}}$$
"""

        # Caso 3: Ley de Ohm con I y R conocidos (calcula V paso a paso)
        if I is not None and I > 0 and len(vals_r) == 1 and (V is None or V == 0):
            R_val = vals_r[0]
            V_calc = I * R_val
            P_calc = V_calc * I
            return f"""
### 🟢 [M2 — Electrodinámica] Ley de Ohm

**Ley de Ohm:**
$$V = I \\cdot R$$

**Datos extraídos:**
- Corriente ($I$): ${I:.4g}\\;\\text{{A}}$
- Resistencia ($R$): ${R_val:.4g}\\;\\Omega$

---

#### 1) Cálculo del voltaje ($V$)
**Fórmula:**
$$V = I \\cdot R$$

**Sustitución:**
$$V = ({I:.4g}\\;\\text{{A}}) \\cdot ({R_val:.4g}\\;\\Omega)$$

$$\\boxed{{V = {V_calc:.4f}\\;\\text{{V}}}}$$

---

#### 2) Potencia eléctrica disipada
$$P = I^2 \\cdot R = ({I:.4g}\\;\\text{{A}})^2 \\cdot ({R_val:.4g}\\;\\Omega)$$
$$\\boxed{{P = {P_calc:.4f}\\;\\text{{W}}}}$$
"""

        # Caso 4: Resistencias equivalentes (Serie o Paralelo)
        if vals_r:
            if es_par:
                Req = 1.0 / sum(1.0 / r for r in vals_r if r > 0) if all(r > 0 for r in vals_r) else 0.0
                modo, formula = "Paralelo", r"R_{eq} = \left(\sum \frac{1}{R_i}\right)^{-1}"
            else:
                Req = sum(vals_r)
                modo, formula = "Serie", r"R_{eq} = \sum R_i"
            lista = ", ".join([f"{r:.4g}\\;\\Omega" for r in vals_r])
            extra = ""
            if V is not None and V > 0 and Req > 0:
                I_tot = V / Req
                P_tot = V * I_tot
                extra = (f"\n\n---\n**Con fuente de $V = {V:.4g}\\;\\text{{V}}$:**\n"
                         f"- Corriente total: $I = V/R_{{eq}} = {V:.4g}/{Req:.2f} = {I_tot:.4f}\\;\\text{{A}}$\n"
                         f"- Potencia total disipada: $P = V \\cdot I = {P_tot:.4f}\\;\\text{{W}}$")
            return f"""
### 🟢 [M2 — Electrodinámica] Resistencias en {modo}
**Fórmula:** ${formula}$

**Resistores:** ${lista}$

$$\\boxed{{R_{{eq}} = {Req:.4f}\\;\\Omega}}$$
{extra}
"""

    # Transitorio RC
    if any(k in t for k in ["transitorio", " rc", "tau", "constante de tiempo",
                              "carga rc", "descarga"]):
        R = _num(r'(?:r|resistencia)\s*[=:]\s*([\d.eE+\-]+)', t, 1e3)
        caps_info = extraer_capacitancias_texto(t)
        if caps_info:
            C = caps_info[0]["faradios"]
        else:
            C = _num(r'(?:c|capacitancia)\s*[=:]\s*([\d.eE+\-]+)', t, 1e-6)
            if any(u in t for u in ["µf", "uf", "µ", "u"]):
                C *= 1e-6
            elif "nf" in t:
                C *= 1e-9
        V0 = _num(r'(?:v0|v_0|v\s*inicial|voltaje\s*inicial)\s*[=:]\s*([\d.]+)', t, 0.0)
        Vf = _num(r'(?:vf|v_f|vs|fuente|voltaje\s*final)\s*[=:]\s*([\d.]+)', t, 12.0)
        t_ev = _num(r'(?<![a-z])t\s*[=:]\s*([\d.]+)', t, None)
        if any(k in t for k in ["kohm", "kω", "kΩ", "k ohm"]):
            R *= 1e3
        tau = R * C
        t5tau = 5 * tau
        V_tau = Vf + (V0 - Vf) * math.exp(-1)
        V_5tau = Vf + (V0 - Vf) * math.exp(-5)
        linea_vt = ""
        if t_ev is not None:
            V_t = Vf + (V0 - Vf) * math.exp(-t_ev / tau)
            linea_vt = f"\n**A $t = {t_ev}\\;\\text{{s}}$:** $v_C = {V_t:.4f}\\;\\text{{V}}$"
        return f"""
### 🟢 [M2 — Electrodinámica] Circuito RC Transitorio
**Ecuación de carga/descarga:**
$$v_C(t) = V_f + (V_0 - V_f)\\,e^{{-t/\\tau}}$$

**Constante de tiempo:**
$$\\tau = R \\cdot C = {R:.2e}\\;\\Omega \\times {C:.2e}\\;\\text{{F}} = {tau:.4e}\\;\\text{{s}}$$

**Parámetros:** $V_0 = {V0}\\;\\text{{V}}$, $V_f = {Vf}\\;\\text{{V}}$
{linea_vt}
- **En $t = \\tau = {tau:.4e}\\;\\text{{s}}$:** $v_C = {V_tau:.4f}\\;\\text{{V}}$ (63.2% de la variación)
- **En $t = 5\\tau = {t5tau:.4e}\\;\\text{{s}}$:** $v_C \\approx {V_5tau:.4f}\\;\\text{{V}}$ (régimen estacionario)
"""

    # Potencia
    if any(k in t for k in ["potencia", "watt", "energía eléctrica", "energía disipada",
                              "energia electrica", "energia disipada"]):
        V = _num(r'(?:v|voltaje)\s*[=:]\s*([\d.]+)', t, None)
        I = _num(r'(?:i|corriente)\s*[=:]\s*([\d.]+)', t, None)
        R = _num(r'(?:r|resistencia)\s*[=:]\s*([\d.]+)', t, None)
        t_s = _num(r'(?<![a-z])t\s*[=:]\s*([\d.]+)', t, None)
        P = None
        if V and I:
            P = V * I
        elif V and R:
            P = V**2 / R
        elif I and R:
            P = I**2 * R
        if P is not None:
            E_j = P * t_s if t_s else None
            extra = (f"\n**Energía en $t={t_s}\\;\\text{{s}}$:** $W = P\\cdot t = {E_j:.4f}\\;\\text{{J}}$"
                     if E_j else "")
            return f"""
### 🟢 [M2 — Electrodinámica] Potencia Eléctrica (Efecto Joule)
**Fórmulas:** $P = V I = V^2/R = I^2 R$

$$\\boxed{{P = {P:.4f}\\;\\text{{W}}}}$$
{extra}
"""

    return """
### 🟢 [M2 — Electrodinámica] Temas Disponibles
Ejemplos:
- `V=12V, R=47 ohm → calcula I` (Ley de Ohm)
- `R1=10, R2=22, R3=47 en paralelo, V=5V` (Resistencias equiv.)
- `RC transitorio: R=1kohm, C=100µF, V0=0, Vf=12V, t=0.05s`
- `Potencia: V=220V, I=2A, t=60s`
"""


# ==============================================================================
# 10. SOLUCIONADOR MÓDULO 3: MAGNETISMO (extras sobre motor RLC)
# ==============================================================================
def _parse_numero_decimal(texto_num: str):
    """Acepta coma o punto decimal: '1,50' -> 1.50, '1.234,56' -> 1234.56."""
    s = str(texto_num).strip()
    if "," in s and "." in s:
        # Convención latina: punto de millar, coma decimal.
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    return float(s)


def _extraer_medida(patron, texto, default=None):
    """Devuelve (valor_float, unidad) capturando coma o punto decimal."""
    m = re.search(patron, texto, re.IGNORECASE)
    if not m:
        return default, None
    try:
        valor = _parse_numero_decimal(m.group(1))
    except Exception:
        return default, None
    unidad = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else None
    return valor, unidad


def _fmt_num(valor: float) -> str:
    """Número limpio, redondeado a 6 cifras significativas (4-6 decimals útiles)."""
    if valor == 0:
        return "0"
    return f"{valor:.6g}"


def _si_longitud(valor, unidad):
    u = (unidad or "").lower()
    if u in ("mm", "milimetro", "milimetros", "milímetro", "milímetros"):
        return valor * 1e-3, "mm"
    if u in ("cm", "centimetro", "centimetros", "centímetro", "centímetros"):
        return valor * 1e-2, "cm"
    return valor, "m"


def _si_corriente(valor, unidad):
    u = (unidad or "").lower()
    if u in ("ma", "miliamperio", "miliamperios", "miliamper", "miliamperes"):
        return valor * 1e-3, "mA"
    return valor, "A"


def _si_campo(valor, unidad):
    u = (unidad or "").lower()
    if u in ("mt", "militesla", "militeslas"):
        return valor * 1e-3, "mT"
    return valor, "T"


def formato_valor_limpio(val: float, unidad: str = "") -> str:
    """
    Formatea un número de forma limpia:
    - Decimal limpio para números en rangos comunes (0.0001 a 99999).
    - Notación matemática LaTeX limpia (a \times 10^{b}) para magnitudes muy pequeñas o grandes.
    """
    if val is None:
        return ""
    if abs(val) < 1e-30:
        return f"0\\;\\text{{{unidad}}}" if unidad else "0"

    signo = "-" if val < 0 else ""
    mag = abs(val)

    if 0.0001 <= mag < 100000:
        if abs(mag - round(mag, 2)) < 1e-5:
            s = f"{signo}{mag:.2f}"
            if s.endswith(".00"):
                s = f"{signo}{int(round(mag))}"
        elif abs(mag - round(mag, 4)) < 1e-5:
            s = f"{signo}{mag:.4f}".rstrip('0').rstrip('.')
        else:
            s = f"{signo}{mag:.4g}"
    else:
        exp = int(math.floor(math.log10(mag)))
        mant = mag / (10.0 ** exp)
        if abs(mant - round(mant, 2)) < 1e-4:
            s_mant = f"{mant:.2f}".rstrip('0').rstrip('.')
        else:
            s_mant = f"{mant:.3g}"
        s = f"{signo}{s_mant} \\times 10^{{{exp}}}"

    if unidad:
        return f"{s}\\;\\text{{{unidad}}}"
    return s


def formato_fuerza_limpia(val: float) -> str:
    """Formatea la fuerza en Newtons con decimal limpio (ej. 0.40 N) o notación clara."""
    mag = abs(val)
    if 0.001 <= mag < 1000:
        if abs(mag - round(mag, 2)) < 1e-4:
            return f"{val:.2f}"
        return f"{val:.4f}".rstrip('0').rstrip('.')
    return formato_valor_limpio(val)


def resolver_fuerza_magnetica_conductor(texto: str):
    """
    M3 — Fuerza magnética sobre un conductor, alambre, espira o bobina.
    Fórmula: F = B * I * L * sin(theta)
    Para 0.5 m, 4 A, 0.2 T y 90° resulta exactamente 0.40 N.
    """
    t = texto.lower()

    # Si se menciona explícitamente carga en movimiento o variación de flujo sin relación con conductor, omitir.
    if any(k in t for k in ["carga en campo", "partícula en campo", "particula en campo"]):
        return None
    if any(k in t for k in ["faraday", "lenz", "fem inducida", "variación de flujo", "variacion de flujo"]):
        return None

    es_conductor = any(k in t for k in [
        "conductor", "alambre", "espira", "bobina", "hilo", "cable",
        "vuelta", "devanado", "solenoide", "fuerza magnética sobre un conductor",
        "fuerza sobre un conductor", "fuerza en un conductor"
    ])

    # Si no tiene palabra clave de conductor, verificar si tiene datos de conductor: L (m/cm/mm) y I (A/mA)
    if not es_conductor:
        tiene_l = bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?)\b', t))
        tiene_i = bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:ma|miliamperios?|a|amperios?)\b', t))
        tiene_b = bool(re.search(r'\b\d+(?:[.,]\d+)?\s*(?:mt|militeslas?|t|teslas?)\b', t))
        if tiene_l and tiene_i and (tiene_b or "fuerza" in t):
            es_conductor = True
        else:
            return None

    # 1. Campo magnético B
    B_raw, B_uni = None, None
    m_b = re.search(r'\b(?:b|campo(?:\s+magn[ée]tico)?)\b(?:\s+(?:de|del|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(mt|militeslas?|t|teslas?)?\b', t)
    if m_b and m_b.group(1):
        B_raw = _parse_numero_decimal(m_b.group(1))
        B_uni = m_b.group(2)
    if B_raw is None:
        m_b2 = re.search(r'\b([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(mt|militeslas?|t|teslas?)\b', t)
        if m_b2:
            B_raw = _parse_numero_decimal(m_b2.group(1))
            B_uni = m_b2.group(2)
    if B_raw is None:
        B_raw, B_uni = 1.0, "T"

    B, B_uni_txt = _si_campo(B_raw, B_uni)

    # 2. Corriente I
    I_raw, I_uni = None, None
    m_i = re.search(r'\b(?:i|corriente|intensidad)\b(?:\s+(?:de|del|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(ma|miliamperios?|miliamper|a|amperios?|ampere|amps?)?\b', t)
    if m_i and m_i.group(1):
        I_raw = _parse_numero_decimal(m_i.group(1))
        I_uni = m_i.group(2)
    if I_raw is None:
        m_i2 = re.search(r'\b([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(ma|miliamperios?|miliamper|a|amperios?|ampere|amps?)\b', t)
        if m_i2:
            I_raw = _parse_numero_decimal(m_i2.group(1))
            I_uni = m_i2.group(2)
    if I_raw is None:
        I_raw, I_uni = 1.0, "A"

    I, I_uni_txt = _si_corriente(I_raw, I_uni)

    # 3. Ángulo theta
    m_th = re.search(r'\b(?:theta|θ|ángulo|angulo|ang)\b(?:\s+(?:de|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:°|grados?)?\b', t)
    if not m_th:
        m_th = re.search(r'\b([0-9]+(?:[.,][0-9]+)?)\s*(?:°|grados)\b', t)
    if m_th:
        theta = _parse_numero_decimal(m_th.group(1))
    elif "perpendicular" in t or "perpendiculares" in t:
        theta = 90.0
    elif "paralelo" in t or "paralela" in t or "paralelos" in t:
        theta = 0.0
    else:
        theta = 90.0

    sin_theta = math.sin(math.radians(theta))
    if abs(sin_theta - round(sin_theta)) < 1e-9:
        sin_theta = float(round(sin_theta))

    # 4. Longitud L o parámetros de espira/bobina
    L_raw, L_uni = None, None
    d_raw, d_uni = None, None
    r_raw, r_uni = None, None
    N_raw = None

    # Caso espira/bobina (diámetro o radio)
    m_d = re.search(r'\b(?:di[áa]metro|diametro)\b(?:\s+(?:de|del|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?)?\b', t)
    if m_d:
        d_raw = _parse_numero_decimal(m_d.group(1))
        d_uni = m_d.group(2)

    m_r = re.search(r'\b(?:radio|r)\b(?:\s+(?:de|del|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?)?\b', t)
    if m_r:
        r_raw = _parse_numero_decimal(m_r.group(1))
        r_uni = m_r.group(2)

    m_n = re.search(r'\b(?:n|vueltas?|espiras?|n[úu]mero\s+de\s+vueltas)\b(?:\s+(?:de|del|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\b', t)
    if m_n:
        N_raw = _parse_numero_decimal(m_n.group(1))

    # Longitud L de conductor
    m_l = re.search(r'\b(?:longitud|l|conductor|alambre|hilo|cable)\b(?:\s+(?:de|del|con|longitud))*?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?)?\b', t)
    if m_l and m_l.group(1):
        L_raw = _parse_numero_decimal(m_l.group(1))
        L_uni = m_l.group(2)

    if L_raw is None and d_raw is None and r_raw is None:
        for m_len in re.finditer(r'\b([0-9]+(?:[.,][0-9]+)?)\s*(mm|mil[ií]metros?|cm|cent[ií]metros?|m|metros?)\b', t):
            u_cand = m_len.group(2).lower()
            if u_cand == "m" and re.search(rf'{m_len.group(1)}\s*mt\b', t):
                continue
            L_raw = _parse_numero_decimal(m_len.group(1))
            L_uni = u_cand
            break

    if L_raw is None and d_raw is None and r_raw is None:
        L_raw, L_uni = 1.0, "m"

    # Resolución Caso 1: Longitud L directa
    if L_raw is not None and (d_raw is None and r_raw is None):
        L, L_uni_txt = _si_longitud(L_raw, L_uni)
        F = B * I * L * sin_theta
        F_txt = formato_fuerza_limpia(F)
        titulo = "Fuerza Magnética sobre un Conductor"

        return f"""
### 🔵 [M3 — Magnetismo] {titulo}

**Fórmula:**
$$F = B \\cdot I \\cdot L \\cdot \\sin\\theta$$

**Datos:**
- Campo magnético ($B$): ${formato_valor_limpio(B, 'T')}$
- Corriente ($I$): ${formato_valor_limpio(I, 'A')}$
- Longitud del conductor ($L$): ${formato_valor_limpio(L, 'm')}$
- Ángulo ($\theta$): ${theta:.4g}^\\circ \\implies \\sin({theta:.4g}^\\circ) = {sin_theta:.4g}$

---

#### Sustitución y cálculo:
$$F = ({formato_valor_limpio(B, 'T')}) \\cdot ({formato_valor_limpio(I, 'A')}) \\cdot ({formato_valor_limpio(L, 'm')}) \\cdot ({sin_theta:.4g})$$

$$\\boxed{{F = {F_txt}\\;\\text{{N}}}}$$
"""

    # Resolución Caso 2: Espira / Bobina con diámetro/radio y vueltas
    es_radio = d_raw is None and r_raw is not None
    diametro_raw = (r_raw * 2.0) if es_radio else d_raw
    uni_usada = r_uni if es_radio else d_uni
    if diametro_raw is None:
        return None

    d, d_uni_txt = _si_longitud(diametro_raw, uni_usada)
    N = N_raw if N_raw is not None else 1.0
    L_total = N * math.pi * d
    F = B * I * L_total * sin_theta
    F_txt = formato_fuerza_limpia(F)

    return f"""
### 🔵 [M3 — Magnetismo] Fuerza Magnética sobre Bobina / Espira

**Fórmulas:**
$$L_{{\\text{{total}}}} = N \\cdot \\pi \\cdot d \\qquad;\\qquad F = B \\cdot I \\cdot L_{{\\text{{total}}}} \\cdot \\sin\\theta$$

**Datos:**
- Campo magnético ($B$): ${formato_valor_limpio(B, 'T')}$
- Corriente ($I$): ${formato_valor_limpio(I, 'A')}$
- Diámetro ($d$): ${formato_valor_limpio(d, 'm')}$
- Número de vueltas ($N$): ${int(N) if N == int(N) else N}$
- Ángulo ($\theta$): ${theta:.4g}^\\circ \\implies \\sin({theta:.4g}^\\circ) = {sin_theta:.4g}$

---

#### Sustitución y cálculo:
$$L_{{\\text{{total}}}} = {N} \\cdot \\pi \\cdot ({formato_valor_limpio(d, 'm')}) = {formato_valor_limpio(L_total, 'm')}$$

$$F = ({formato_valor_limpio(B, 'T')}) \\cdot ({formato_valor_limpio(I, 'A')}) \\cdot ({formato_valor_limpio(L_total, 'm')}) \\cdot ({sin_theta:.4g})$$

$$\\boxed{{F = {F_txt}\\;\\text{{N}}}}$$
"""


def resolver_modulo3_extra(texto: str):
    """Resuelve magnetismo puro (fuerza en conductor, Lorentz, Biot-Savart, Faraday)."""
    t = texto.lower()
    mu0 = 4 * math.pi * 1e-7

    # Prioridad 1: fuerza magnética sobre conductor/alambre/espira/bobina.
    resp_fuerza = resolver_fuerza_magnetica_conductor(texto)
    if resp_fuerza:
        return resp_fuerza

    # Si el enunciado menciona conductor, alambre o bobina, NUNCA debe entrar a Lorentz sobre carga puntual
    es_conductor = any(k in t for k in ["conductor", "alambre", "hilo", "cable", "espira", "bobina"])
    if es_conductor:
        return """
### 🔵 [M3 — Magnetismo] Fuerza Magnética sobre un Conductor
**Fórmula:**
$$F = B \\cdot I \\cdot L \\cdot \\sin\\theta$$

Para resolver este ejercicio se requiere la longitud $L$ del conductor (en m/cm), la corriente $I$ (en A/mA) y el campo magnético $B$ (en T).
*Ejemplo:* `conductor de 0.5 m, 4 A, 0.2 T y 90°` $\\rightarrow F = 0.40\\;\\text{N}$
"""

    # Prioridad 2: Fuerza de Lorentz sobre Carga en Movimiento
    if any(k in t for k in ["lorentz", "qvb", "carga en campo", "partícula en campo", "particula en campo"]) or \
       (any(k in t for k in ["fuerza magnética", "fuerza magnetica"]) and any(k in t for k in ["carga", "electr", "prot", "partícula", "particula", "velocidad", "v="])):
        
        # 1. Carga q
        cargas = extraer_cargas_texto(texto)
        if cargas:
            q = cargas[0]["val"]
            q_str = formato_valor_limpio(q, "C")
        else:
            m_q = re.search(r'\b(?:q|carga)\s*[=:]\s*([+\-]?\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*([µμu]c|nc|mc|pc|c)?\b', t)
            if m_q:
                val = _parse_numero_decimal(m_q.group(1))
                u = (m_q.group(2) or "").lower()
                if any(x in u for x in ["µc", "μc", "uc"]):
                    val *= 1e-6
                elif "nc" in u:
                    val *= 1e-9
                elif "mc" in u:
                    val *= 1e-3
                elif "pc" in u:
                    val *= 1e-12
                q = val
                q_str = formato_valor_limpio(q, "C")
            elif any(p in t for p in ["electrón", "electron"]):
                q = -1.602e-19
                q_str = r"-1.602 \times 10^{-19}\;\text{C}\;(\text{electr\'on})"
            elif any(p in t for p in ["protón", "proton"]):
                q = 1.602e-19
                q_str = r"1.602 \times 10^{-19}\;\text{C}\;(\text{prot\'on})"
            else:
                q = 1.602e-19
                q_str = r"1.602 \times 10^{-19}\;\text{C}\;(\text{carga elemental } e)"

        # 2. Velocidad v
        m_v = re.search(r'\b(?:v|velocidad|rapidez)\s*(?:de|[=:])?\s*([+\-]?\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(km/s|m/s)?\b', t)
        if m_v and m_v.group(1):
            v = _parse_numero_decimal(m_v.group(1))
            if (m_v.group(2) or "").lower() == "km/s":
                v *= 1e3
        else:
            m_v2 = re.search(r'\b([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(km/s|m/s)\b', t)
            if m_v2:
                v = _parse_numero_decimal(m_v2.group(1))
                if (m_v2.group(2) or "").lower() == "km/s":
                    v *= 1e3
            else:
                v = 1e6

        # 3. Campo magnético B
        m_b = re.search(r'\b(?:b|campo(?:\s+magn[ée]tico)?)\s*(?:de|[=:])?\s*([+\-]?\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)\s*(mt|t|teslas?)?\b', t)
        if m_b and m_b.group(1):
            B = _parse_numero_decimal(m_b.group(1))
            if (m_b.group(2) or "").lower() in ("mt", "militesla", "militeslas"):
                B *= 1e-3
        else:
            m_b2 = re.search(r'\b([0-9]+(?:[.,][0-9]+)?(?:e[+\-]?[0-9]+)?)\s*(mt|t|teslas?)\b', t)
            if m_b2:
                B = _parse_numero_decimal(m_b2.group(1))
                if (m_b2.group(2) or "").lower() in ("mt", "militesla", "militeslas"):
                    B *= 1e-3
            else:
                B = 1.0

        # 4. Ángulo theta
        m_th = re.search(r'\b(?:theta|θ|ángulo|angulo|ang)\b(?:\s+(?:de|con))*\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:°|grados?)?\b', t)
        if not m_th:
            m_th = re.search(r'\b([0-9]+(?:[.,][0-9]+)?)\s*(?:°|grados)\b', t)
        if m_th:
            theta = _parse_numero_decimal(m_th.group(1))
        elif "perpendicular" in t or "perpendiculares" in t:
            theta = 90.0
        elif "paralelo" in t or "paralela" in t or "paralelos" in t:
            theta = 0.0
        else:
            theta = 90.0

        sin_theta = math.sin(math.radians(theta))
        if abs(sin_theta - round(sin_theta)) < 1e-9:
            sin_theta = float(round(sin_theta))

        F = abs(q) * v * B * sin_theta
        F_txt = formato_fuerza_limpia(F) if 0.001 <= abs(F) < 1000 else formato_valor_limpio(F, "N")

        return f"""
### 🔵 [M3 — Magnetismo] Fuerza de Lorentz sobre Carga en Movimiento

**Fórmula:**
$$\\vec{{F}} = q\\,(\\vec{{v}} \\times \\vec{{B}}) \\implies F = |q| \\cdot v \\cdot B \\cdot \\sin\\theta$$

**Datos:**
- Carga ($q$): ${q_str}$
- Velocidad ($v$): ${formato_valor_limpio(v, 'm/s')}$
- Campo magnético ($B$): ${formato_valor_limpio(B, 'T')}$
- Ángulo ($\theta$): ${theta:.4g}^\\circ \\implies \\sin({theta:.4g}^\\circ) = {sin_theta:.4g}$

---

#### Sustitución y cálculo:
$$F = |{formato_valor_limpio(q)}| \\cdot ({formato_valor_limpio(v, 'm/s')}) \\cdot ({formato_valor_limpio(B, 'T')}) \\cdot ({sin_theta:.4g})$$

$$\\boxed{{F = {F_txt}\\;\\text{{N}}}}$$
"""

    if any(k in t for k in ["biot", "savart", "hilo largo", "conductor largo",
                              "campo de un hilo"]):
        I = _num(r'(?:i|corriente)\s*[=:]\s*([\d.]+)', t, 1.0)
        r = _num(r'(?:r|distancia|d)\s*[=:]\s*([\d.]+)', t, 0.1)
        B = mu0 * I / (2 * math.pi * r)
        return f"""
### 🔵 [M3 — Magnetismo] Campo Magnético — Hilo Largo (Biot-Savart)
**Fórmula:**
$$B = \\frac{{\\mu_0\\,I}}{{2\\pi\\,r}}$$

**Datos:** $I = {I}\\;\\text{{A}}$, $r = {r}\\;\\text{{m}}$, $\\mu_0 = 4\\pi\\times10^{{-7}}\\;\\text{{T·m/A}}$

$$\\boxed{{B = {formato_valor_limpio(B, 'T')}}}$$
"""

    if any(k in t for k in ["faraday", "lenz", "fem inducida", "variación de flujo",
                              "variacion de flujo", "delta phi", "dphi"]):
        dphi = _num(r'(?:dphi|delta.*phi|delta.*flujo|d.*flujo)\s*[=:]\s*([\d.eE+\-]+)', t, 1e-3)
        dt = _num(r'(?:dt|delta.*t|tiempo)\s*[=:]\s*([\d.]+)', t, 0.01)
        N = _num(r'(?:n|espiras|vueltas|bobina)\s*[=:]\s*([\d.]+)', t, 1.0)
        fem = abs(N * dphi / dt)
        return f"""
### 🔵 [M3 — Magnetismo] Ley de Faraday-Lenz
**Fórmula:**
$$|\\mathcal{{E}}| = N\\,\\left|\\frac{{\\Delta\\Phi_B}}{{\\Delta t}}\\right|$$
*(El signo negativo indica que la FEM se opone al cambio — Ley de Lenz)*

**Datos:** $N = {N}$, $\\Delta\\Phi_B = {formato_valor_limpio(dphi, 'Wb')}$, $\\Delta t = {dt}\\;\\text{{s}}$

$$\\boxed{{\\mathcal{{E}} = {formato_valor_limpio(fem, 'V')}}}$$
"""

    if any(k in t for k in ["biot", "savart", "hilo largo", "conductor largo",
                              "campo de un hilo"]):
        I = _num(r'(?:i|corriente)\s*[=:]\s*([\d.]+)', t, 1.0)
        r = _num(r'(?:r|distancia|d)\s*[=:]\s*([\d.]+)', t, 0.1)
        B = mu0 * I / (2 * math.pi * r)
        return f"""
### 🔵 [M3 — Magnetismo] Campo Magnético — Hilo Largo (Biot-Savart)
**Fórmula:**
$$B = \\frac{{\\mu_0\\,I}}{{2\\pi\\,r}}$$

**Datos:** $I = {I}\\;\\text{{A}}$, $r = {r}\\;\\text{{m}}$, $\\mu_0 = 4\\pi\\times10^{{-7}}\\;\\text{{T·m/A}}$

$$\\boxed{{B = {B:.4e}\\;\\text{{T}}}}$$
"""

    if any(k in t for k in ["faraday", "lenz", "fem inducida", "variación de flujo",
                              "variacion de flujo", "delta phi", "dphi"]):
        dphi = _num(r'(?:dphi|delta.*phi|delta.*flujo|d.*flujo)\s*[=:]\s*([\d.eE+\-]+)', t, 1e-3)
        dt = _num(r'(?:dt|delta.*t|tiempo)\s*[=:]\s*([\d.]+)', t, 0.01)
        N = _num(r'(?:n|espiras|vueltas|bobina)\s*[=:]\s*([\d.]+)', t, 1.0)
        fem = abs(N * dphi / dt)
        return f"""
### 🔵 [M3 — Magnetismo] Ley de Faraday-Lenz
**Fórmula:**
$$|\\mathcal{{E}}| = N\\,\\left|\\frac{{\\Delta\\Phi_B}}{{\\Delta t}}\\right|$$
*(El signo negativo indica que la FEM se opone al cambio — Ley de Lenz)*

**Datos:** $N = {N}$, $\\Delta\\Phi_B = {dphi:.3e}\\;\\text{{Wb}}$, $\\Delta t = {dt}\\;\\text{{s}}$

$$\\boxed{{\\mathcal{{E}} = {fem:.4e}\\;\\text{{V}}}}$$
"""

    return None  # Dejar al motor RLC


def extraer_params_nlp_ca(texto: str):
    t = texto.lower()
    res = {}
    mv = (re.search(r'(?:v(?:olt(?:aje)?)?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*v?\b', t) or
          re.search(r'(\d+(?:\.\d+)?)\s*v(?:olt(?:ios)?)?\b', t))
    if mv:
        res['v_rms'] = float(mv.group(1))
    mf = (re.search(r'(?:f(?:rec(?:uencia)?)?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*hz?\b', t) or
          re.search(r'(\d+(?:\.\d+)?)\s*hz\b', t))
    if mf:
        vf = float(mf.group(1))
        res['f'] = vf if vf > 0 else 60.0
    else:
        res['f'] = 60.0
    mr = re.findall(r'(?:r\d*|resistencia\d*)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:ohm|ω|Ω)?\b', t)
    ml = re.findall(r'(?:l\d*|inductancia\d*|bobina\d*)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:h|henrios)?\b', t)
    caps_info = extraer_capacitancias_texto(t)
    comps = ([{"tipo": "R", "val": float(v)} for v in mr] +
             [{"tipo": "L", "val": float(v)} for v in ml] +
             [{"tipo": "C", "val": float(c["microfaradios"])} for c in caps_info])
    if comps:
        res['componentes'] = comps
    if "mixto" in t or "derivacion" in t:
        res['tipo'] = "mixto"
    elif "paralelo" in t:
        res['tipo'] = "paralelo"
    elif "serie" in t:
        res['tipo'] = "serie"
    return res


# ==============================================================================
# 11. SOLUCIONADOR MÓDULO 4: ELECTRÓNICA
# ==============================================================================
def resolver_modulo4(texto: str) -> str:
    t = texto.lower()

    # Curva I-V diodo
    if any(k in t for k in ["curva iv", "curva i-v", "umbral", "vth",
                              "diodo ideal", "polarización directa", "polarizacion directa"]):
        Vth = _num(r'(?:vth|umbral)\s*[=:]\s*([\d.]+)', t, 0.7)
        V = _num(r'(?:vs|v\s*fuente|voltaje\s*fuente|vs|v)\s*[=:]\s*([\d.]+)', t, 5.0)
        R = _num(r'(?:r|resistencia)\s*[=:]\s*([\d.]+)', t, 1e3)
        Vr = max(0.0, V - Vth)
        I = Vr / R if R > 0 else 0.0
        Pd = Vth * I
        return f"""
### 🟣 [M4 — Electrónica] Diodo en Polarización Directa — Modelo de Umbral
**Modelo simplificado:** umbral $V_{{th}} = {Vth}\\;\\text{{V}}$

**Tensión en resistencia:**
$$V_R = V_s - V_{{th}} = {V} - {Vth} = {Vr:.2f}\\;\\text{{V}}$$

**Corriente:**
$$\\boxed{{I = \\frac{{V_R}}{{R}} = \\frac{{{Vr:.2f}}}{{{R}}} = {I:.4f}\\;\\text{{A}}}}$$

**Potencia disipada en el diodo:** $P_D = V_{{th}} \\cdot I = {Vth}\\cdot{I:.4f} = {Pd:.4f}\\;\\text{{W}}$

*Curva I-V: para $V < {Vth}\\;\\text{{V}}$ el diodo está en corte (I = 0).*
"""

    # Rectificador media onda
    if any(k in t for k in ["media onda", "half wave"]):
        Vp = _num(r'(?:vp|v_?pico|vm)\s*[=:]\s*([\d.]+)', t, 170.0)
        Vth = _num(r'(?:vth|umbral)\s*[=:]\s*([\d.]+)', t, 0.7)
        R = _num(r'(?:r(?:l)?|carga|resistencia)\s*[=:]\s*([\d.]+)', t, 1e3)
        Vpout = max(0.0, Vp - Vth)
        Vdc = Vpout / math.pi
        Vrms_out = Vpout / 2.0
        return f"""
### 🟣 [M4 — Electrónica] Rectificador de Media Onda
**Parámetros:** $V_{{p}} = {Vp}\\;\\text{{V}}$, $V_{{th}} = {Vth}\\;\\text{{V}}$, $R_L = {R}\\;\\Omega$

**Tensión pico de salida:**
$$V_{{p,out}} = V_p - V_{{th}} = {Vp} - {Vth} = {Vpout:.2f}\\;\\text{{V}}$$

**Tensión promedio DC:**
$$\\boxed{{V_{{DC}} = \\frac{{V_{{p,out}}}}{{\\pi}} = {Vdc:.4f}\\;\\text{{V}}}}$$

**Tensión RMS de salida:** $V_{{rms}} = V_{{p,out}}/2 = {Vrms_out:.4f}\\;\\text{{V}}$

**Rizado (ripple):** $f_{{ripple}} = f_{{entrada}}$ (misma frecuencia)
"""

    # Rectificador onda completa / puente
    if any(k in t for k in ["onda completa", "full wave", "puente", "bridge"]):
        Vp = _num(r'(?:vp|v_?pico|vm)\s*[=:]\s*([\d.]+)', t, 170.0)
        Vth = _num(r'(?:vth|umbral)\s*[=:]\s*([\d.]+)', t, 0.7)
        R = _num(r'(?:r(?:l)?|carga)\s*[=:]\s*([\d.]+)', t, 1e3)
        n_diodos = 4 if "puente" in t or "bridge" in t else 2
        Vpout = max(0.0, Vp - n_diodos * Vth)
        Vdc = 2.0 * Vpout / math.pi
        Vrms_out = Vpout / math.sqrt(2)
        return f"""
### 🟣 [M4 — Electrónica] Rectificador de Onda Completa ({'Puente de Graetz (4 diodos)' if n_diodos==4 else 'Tap Central (2 diodos)'})
**Parámetros:** $V_p = {Vp}\\;\\text{{V}}$, $V_{{th}} = {Vth}\\;\\text{{V}}$ × {n_diodos} diodos, $R_L = {R}\\;\\Omega$

**Tensión pico de salida:**
$$V_{{p,out}} = {Vp} - {n_diodos}\\times{Vth} = {Vpout:.2f}\\;\\text{{V}}$$

**Tensión promedio DC:**
$$\\boxed{{V_{{DC}} = \\frac{{2\\,V_{{p,out}}}}{{\\pi}} = {Vdc:.4f}\\;\\text{{V}}}}$$

**Tensión RMS:** $V_{{rms}} \\approx {Vrms_out:.4f}\\;\\text{{V}}$

**Rizado (ripple):** $f_{{ripple}} = 2\\,f_{{entrada}}$ (el doble de la frecuencia de entrada)
"""

    # Zener
    if any(k in t for k in ["zener", "regulador"]):
        Vz = _num(r'(?:vz|v_z)\s*[=:]\s*([\d.]+)', t, 5.1)
        Vs = _num(r'(?:vs|v_?s|fuente|entrada|v)\s*[=:]\s*([\d.]+)', t, 12.0)
        Rs = _num(r'(?:rs|r_s|serie)\s*[=:]\s*([\d.]+)', t, 1e3)
        RL = _num(r'(?:rl|r_l|carga)\s*[=:]\s*([\d.]+)', t, 10e3)
        Is = (Vs - Vz) / Rs if Rs > 0 else 0.0
        IL = Vz / RL if RL > 0 else 0.0
        Iz = Is - IL
        estado = ("✅ Zener en zona de regulación." if Iz > 0
                  else "⚠️ Iz < 0: Zener fuera de regulación — RL muy pequeña o Vs insuficiente.")
        return f"""
### 🟣 [M4 — Electrónica] Regulador con Diodo Zener
**Parámetros:** $V_Z = {Vz}\\;\\text{{V}}$, $V_s = {Vs}\\;\\text{{V}}$, $R_S = {Rs}\\;\\Omega$, $R_L = {RL}\\;\\Omega$

**Corriente total (desde la fuente):**
$$I_S = \\frac{{V_s - V_Z}}{{R_S}} = \\frac{{{Vs} - {Vz}}}{{{Rs}}} = {Is:.4f}\\;\\text{{A}}$$

**Corriente de carga:** $I_L = V_Z / R_L = {Vz}/{RL} = {IL:.4f}\\;\\text{{A}}$

**Corriente por el Zener:**
$$\\boxed{{I_Z = I_S - I_L = {Is:.4f} - {IL:.4f} = {Iz:.4f}\\;\\text{{A}}}}$$

{estado}
"""

    return """
### 🟣 [M4 — Electrónica] Temas Disponibles
Ejemplos:
- `Diodo polarización directa: Vth=0.7V, Vs=5V, R=1kohm`
- `Rectificador media onda: Vp=170V, R=2kohm`
- `Puente rectificador: Vp=170V, Vth=0.7V, R=1kohm`
- `Zener: Vz=5.1V, Vs=12V, Rs=1kohm, RL=10kohm`
"""


# ==============================================================================
# 12. FORMATEADOR DE RESPUESTA RLC (Módulo 3 CA)
# ==============================================================================
def formatear_respuesta_rlc(res, net_data=None, f_nota=""):
    alerta = ""
    if res.get("advertencia_topologia"):
        alerta = f"\n> {res['advertencia_topologia']}\n"
    comp_desc = ""
    if net_data and net_data.get("componentes"):
        counts = {"R": 0, "L": 0, "C": 0}
        parts = []
        for c in net_data["componentes"]:
            counts[c["tipo"]] += 1
            u = "Ω" if c["tipo"] == "R" else ("H" if c["tipo"] == "L" else "µF")
            parts.append(f"**{c['tipo']}{counts[c['tipo']]}**: `{c['val']} {u}`")
        comp_desc = "\n**Componentes detectados:** " + " | ".join(parts) + "\n"

    return f"""
### 🔵 [M3 — Magnetismo/CA] Circuito RLC — Solución Analítica
{alerta}{comp_desc}
**Alimentación:** $V_{{rms}} = {res['v_rms']:.2f}\\;\\text{{V}}$, $f = {res['f']:.2f}\\;\\text{{Hz}}${f_nota}  
$\\implies \\omega = 2\\pi f = {res['omega']:.2f}\\;\\text{{rad/s}}$ &nbsp;|&nbsp; Topología: **{res['tipo'].upper()}**

---
#### Magnitudes Equivalentes:

| Parámetro | Valor |
|-----------|-------|
| $R_{{eq}}$ | `{res['r_eq']:.3f} Ω` |
| $L_{{eq}}$ | `{res['l_eq']:.4f} H` → $X_L = \\omega L = {res['x_l']:.3f}\\;\\Omega$ |
| $C_{{eq}}$ | `{res['c_eq_uf']:.3f} µF` → $X_C = 1/(\\omega C) = {res['x_c']:.3f}\\;\\Omega$ |
| $X_{{neta}}$ | `{res['x_neta']:.3f} Ω` |

#### Impedancia y Corriente:
$$Z = {res['z_fasor'].real:.3f} + ({res['z_fasor'].imag:.3f})j\\;\\Omega \\quad\\implies\\quad |Z| = {res['z_mag']:.3f}\\;\\Omega,\\;\\theta = {res['z_ang_deg']:.2f}°$$

$$I_{{rms}} = \\frac{{V_{{rms}}}}{{|Z|}} = \\frac{{{res['v_rms']:.2f}}}{{{res['z_mag']:.3f}}} = {res['i_mag']:.4f}\\;\\text{{A}}$$

#### Triángulo de Potencias:
$$P = {res['p_activa']:.2f}\\;\\text{{W}},\\quad Q = {res['q_reactiva']:.2f}\\;\\text{{VAR}},\\quad S = {res['s_aparente']:.2f}\\;\\text{{VA}},\\quad \\cos\\theta = {res['fp']:.4f}$$

**Diagnóstico:** {res['estado_color']} {res['comportamiento']}  
{f"**Frecuencia de resonancia:** $f_0 = {res['f0']:.2f}\\;\\text{{Hz}}$" if res['f0'] > 0 else ""}

> 🎯 Simulador CircuitJS actualizado arriba con este circuito.
"""


# ==============================================================================
# 13. OSCILOSCOPIO VIRTUAL DE ONDAS AC (PLOTLY GRAPH OBJECTS)
# ==============================================================================
def crear_osciloscopio_ac(res: dict):
    """
    Genera un osciloscopio virtual interactivo con Plotly para visualizar
    las ondas instantáneas de voltaje v(t) y corriente i(t) en doble eje Y.
    Abarca exactamente 2.5 ciclos completos respetando el ángulo de desfase theta.
    """
    v_rms = float(res.get("v_rms", 120.0))
    i_rms = float(res.get("i_mag", 1.0))
    f = float(res.get("f", 60.0))
    if f <= 0:
        f = 60.0
    z_ang_deg = float(res.get("z_ang_deg", 0.0))
    theta_rad = math.radians(z_ang_deg)

    # Valores pico
    v_pico = v_rms * math.sqrt(2)
    i_pico = i_rms * math.sqrt(2)

    # Vector de tiempo: exactamente 2.5 ciclos completos (en milisegundos)
    t_max = 2.5 / f
    n_puntos = 350
    t_vals = [i * (t_max / (n_puntos - 1)) for i in range(n_puntos)]
    t_ms = [t * 1000.0 for t in t_vals]

    # Ecuaciones instantáneas en el tiempo
    v_vals = [v_pico * math.sin(2 * math.pi * f * t) for t in t_vals]
    i_vals = [i_pico * math.sin(2 * math.pi * f * t - theta_rad) for t in t_vals]

    # Subtítulo explicativo según el desfase (signo de theta)
    if abs(z_ang_deg) < 0.1:
        subtitulo = f"⚡ Tensión y Corriente en Fase (θ = {z_ang_deg:.1f}°) — Comportamiento Resistivo / Resonancia"
    elif z_ang_deg > 0:
        subtitulo = f"🔵 La Corriente ATRASA al Voltaje por θ = {abs(z_ang_deg):.2f}° (Comportamiento Inductivo)"
    else:
        subtitulo = f"🟠 La Corriente ADELANTA al Voltaje por |θ| = {abs(z_ang_deg):.2f}° (Comportamiento Capacitivo)"

    # Creación del gráfico con doble eje Y
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Onda de Voltaje v(t) — Eje Y Izquierdo (Cian brillante)
    fig.add_trace(
        go.Scatter(
            x=t_ms,
            y=v_vals,
            name=f"Voltaje v(t) [Vp = {v_pico:.1f} V]",
            line=dict(color="#38bdf8", width=2.5),
            hovertemplate="<b>Voltaje:</b> %{y:.2f} V<br><b>t:</b> %{x:.2f} ms<extra></extra>"
        ),
        secondary_y=False
    )

    # Onda de Corriente i(t) — Eje Y Derecho (Verde neón brillante)
    fig.add_trace(
        go.Scatter(
            x=t_ms,
            y=i_vals,
            name=f"Corriente i(t) [Ip = {i_pico:.3f} A]",
            line=dict(color="#4ade80", width=2.5),
            hovertemplate="<b>Corriente:</b> %{y:.3f} A<br><b>t:</b> %{x:.2f} ms<extra></extra>"
        ),
        secondary_y=True
    )

    # Línea horizontal punteada en cero (eje central)
    fig.add_hline(y=0, line_dash="dash", line_color="#475569", line_width=1.2)

    # Configuración de diseño profesional Dark-Mode
    fig.update_layout(
        template="plotly_dark",
        title=dict(
            text=f"📟 <b>Osciloscopio Virtual de Ondas AC</b> (2.5 Ciclos @ {f:.1f} Hz)<br><span style='font-size:12px; color:#94a3b8;'>{subtitulo}</span>",
            font=dict(color="#f1f5f9", size=15),
            x=0.02,
            y=0.96
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(11,15,25,0.75)",
        margin=dict(l=55, r=55, t=75, b=45),
        height=380,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(15,23,42,0.85)",
            bordercolor="#1e293b",
            borderwidth=1,
            font=dict(size=11, color="#f1f5f9")
        ),
        hovermode="x unified"
    )

    # Eje X: Tiempo en milisegundos
    fig.update_xaxes(
        title_text="Tiempo t (milisegundos)",
        title_font=dict(size=12, color="#94a3b8"),
        gridcolor="#1e293b",
        zerolinecolor="#334155",
        showgrid=True
    )

    # Eje Y Izquierdo: Voltaje (V)
    fig.update_yaxes(
        title_text="<b>Voltaje v(t) [V]</b>",
        title_font=dict(size=12, color="#38bdf8"),
        tickfont=dict(color="#38bdf8"),
        gridcolor="#1e293b",
        showgrid=True,
        secondary_y=False
    )

    # Eje Y Derecho: Corriente (A)
    fig.update_yaxes(
        title_text="<b>Corriente i(t) [A]</b>",
        title_font=dict(size=12, color="#4ade80"),
        tickfont=dict(color="#4ade80"),
        showgrid=False,
        secondary_y=True
    )

    return fig


# ==============================================================================
# 14. DISPATCHER PRINCIPAL
# ==============================================================================
def procesar_consulta(prompt: str):
    """Detecta módulo y devuelve (tipo_resp, net_data, res_ac, respuesta_md)."""

    # Prioridad 0: fuerza magnética sobre conductor/alambre/espira/bobina.
    # Va ANTES de los parsers de netlist para que un enunciado con datos como
    # "r = 5 cm" o "v = ..." nunca se confunda con un netlist de CircuitJS
    # y se corte con "Netlist clásico detectado pero sin componentes".
    resp_fuerza = resolver_fuerza_magnetica_conductor(prompt)
    if resp_fuerza:
        return "M3", None, None, resp_fuerza

    # Netlists siempre → M3
    if es_netlist_xml(prompt):
        net_data = parse_circuitjs_xml(prompt)
        if net_data["componentes"]:
            res = calcular_circuito_ac(
                net_data["v_rms"], net_data["f"], net_data["componentes"],
                net_data["tipo"], net_data.get("reduccion_mixta"),
                net_data.get("topologia_info"))
            fn = (" *(f ajustada a 60 Hz — fr era 0 en el netlist)*"
                  if ("fr=\"0\"" in prompt.lower() or "fr='0'" in prompt.lower()) else "")
            return "netlist_xml", net_data, res, formatear_respuesta_rlc(res, net_data, fn)
        return "error", None, None, "⚠️ Netlist XML detectado pero sin componentes válidos."

    if es_netlist_texto(prompt):
        net_data = parse_circuitjs_text(prompt)
        if net_data["componentes"]:
            res = calcular_circuito_ac(
                net_data["v_rms"], net_data["f"], net_data["componentes"],
                net_data["tipo"], net_data.get("reduccion_mixta"),
                net_data.get("topologia_info"))
            return "netlist_text", net_data, res, formatear_respuesta_rlc(res, net_data)
        return "error", None, None, "⚠️ Netlist clásico detectado pero sin componentes."

    modulo = clasificar_modulo(prompt)

    if modulo == "M1":
        return "M1", None, None, resolver_modulo1(prompt)

    if modulo == "M2":
        return "M2", None, None, resolver_modulo2(prompt)

    if modulo == "M4":
        return "M4", None, None, resolver_modulo4(prompt)

    if modulo == "M3":
        resp_mag = resolver_modulo3_extra(prompt)
        if resp_mag:
            return "M3", None, None, resp_mag
        # Intentar como CA por NLP
        params = extraer_params_nlp_ca(prompt)
        if len(params) >= 2 or "componentes" in params:
            v = params.get("v_rms", st.session_state.v_rms)
            f = params.get("f", st.session_state.f)
            comps = params.get("componentes", st.session_state.componentes)
            tipo = params.get("tipo", st.session_state.tipo)
            res = calcular_circuito_ac(v, f, comps, tipo)
            return "M3_ca", {"v_rms": v, "f": f, "componentes": comps, "tipo": tipo}, res, \
                   formatear_respuesta_rlc(res)
        return "M3", None, None, _ayuda_m3()

    # Sin módulo claro → menú general
    return "menu", None, None, _menu_general(prompt)


def _ayuda_m3():
    return """
### 🔵 [M3 — Magnetismo y CA] Temas Disponibles
Ejemplos:
- `Fuerza magnética en alambre: B=0,5 T, I=250 mA, L=10 cm`
- `Fuerza en bobina: B=0,4 T, I=1,50 A, d=5 cm, N=100 vueltas`
- `Fuerza de Lorentz: q=1.6e-19C, v=2e6 m/s, B=0.5T`
- `Biot-Savart: hilo largo I=10A a r=0.05m`
- `Faraday-Lenz: N=100 espiras, dPhi=0.002Wb, dt=0.01s`
- `RLC serie: V=120V, f=60Hz, R=50, L=0.2H, C=30uF`
- Pegar **netlist de CircuitJS** directamente
"""


def _menu_general(prompt_txt=""):
    t = prompt_txt.lower()
    if any(k in t for k in ["resonancia", "f0"]):
        return """
### 🎯 Resonancia en Corriente Alterna
Ocurre cuando $X_L = X_C$, es decir $\\omega_0 L = 1/(\\omega_0 C)$:
$$f_0 = \\frac{1}{2\\pi\\sqrt{L\\cdot C}}$$
- **Serie:** Impedancia mínima ($Z = R$), corriente máxima.
- **Paralelo:** Impedancia máxima, corriente de línea mínima.
"""
    if any(k in t for k in ["impedancia", "formula de z", "fórmula de z"]):
        return """
### 📐 Impedancia Fasorial $Z$
- **Serie:** $Z = R + j(X_L - X_C) \\implies |Z| = \\sqrt{R^2 + (X_L-X_C)^2}$
- **Paralelo:** $Y = G + j(B_C - B_L) \\implies Z = 1/Y$
- **Ángulo:** $\\theta = \\arctan\\!\\left(\\frac{X_L - X_C}{R}\\right)$
"""
    return """
### 💡 Física Aplicada 1 — Asistente IA

Cubre el sílabo completo en 4 módulos:

| Módulo | Semanas | Temas clave |
|--------|---------|-------------|
| 🟡 **M1 Electrostática** | 1–3 | Coulomb, Campo E, Potencial, Capacitores |
| 🟢 **M2 Electrodinámica** | 4–7 | Ohm, Kirchhoff, R equiv., RC transitorio, Potencia |
| 🔵 **M3 Magnetismo / CA** | 9–13 | Lorentz, Biot-Savart, Faraday, RLC, CircuitJS |
| 🟣 **M4 Electrónica** | 14–15 | Diodos, Rectificadores, Zener |

**Ejemplos rápidos:**
- `Fuerza entre q1=5µC y q2=3µC a 0.3m` → M1
- `R1=10, R2=22 en paralelo con V=9V` → M2
- `RLC serie V=120V f=60Hz R=50 L=0.2H C=30uF` → M3
- `Puente rectificador Vp=170V R=1kohm` → M4
- Pegar **netlist de CircuitJS** → Simulador + cálculo M3
"""


# ==============================================================================
# 14. INICIALIZACIÓN DE ESTADO
# ==============================================================================
_defaults = {
    "v_rms": 120.0,
    "f": 60.0,
    "tipo": "serie",
    "componentes": [{"tipo": "R", "val": 50.0},
                    {"tipo": "L", "val": 0.200},
                    {"tipo": "C", "val": 30.0}]
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "circuitjs_url" not in st.session_state:
    sim = st.session_state.get("sim_circuito")
    if sim:
        st.session_state.circuitjs_url = generar_url_circuitjs(
            sim["v_rms"], sim["f"], sim["comps"], sim.get("tipo", "serie"))
    else:
        st.session_state.circuitjs_url = generar_url_circuitjs(
            st.session_state.v_rms, st.session_state.f,
            st.session_state.componentes, st.session_state.tipo)


# ==============================================================================
# 15. ENCABEZADO Y SIMULADOR CIRCUITJS
# ==============================================================================
st.markdown(
    '<h1 style="color:#38bdf8;margin:0;padding:0;font-size:1.85rem;">'
    '⚡ Física Aplicada 1 — Asistente IA + SimuladorCircuitJS</h1>',
    unsafe_allow_html=True)
st.markdown(
    '<p style="color:#94a3b8;margin-top:2px;font-size:0.88rem;">'
    'Sílabo completo: '
    '<span style="color:#f59e0b;">M1 Electrostática</span> · '
    '<span style="color:#22c55e;">M2 Electrodinámica</span> · '
    '<span style="color:#38bdf8;">M3 Magnetismo/CA</span> · '
    '<span style="color:#a78bfa;">M4 Electrónica</span> — '
    'con parser de netlists CircuitJS y detección de topología.</p>',
    unsafe_allow_html=True)

comps_str = ", ".join([f"{c['tipo']}={c['val']}" for c in st.session_state.componentes])
st.markdown(f"""
<div class="status-badge">
    <span>🟢 <b>CIRCUITO CA ACTIVO:</b> RLC {st.session_state.tipo.upper()}
    &nbsp;|&nbsp; V = {st.session_state.v_rms}V @ {st.session_state.f}Hz
    &nbsp;|&nbsp; [{comps_str}]</span>
    <span style="color:#22c55e;">CircuitJS Listo</span>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="simulator-box">', unsafe_allow_html=True)
components.iframe(src=st.session_state.circuitjs_url, height=580, scrolling=True)
st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# 16. CHATBOT ASISTENTE
# ==============================================================================
st.markdown(
    '<h3 style="color:#38bdf8;margin-top:12px;">'
    '💬 Asistente de Física Aplicada 1 — Sílabo Completo</h3>',
    unsafe_allow_html=True)
st.caption(
    "🎓 **4 Módulos activos:** Escribe tu ejercicio con los datos numéricos o pega un netlist de CircuitJS. "
    "El asistente detecta automáticamente el módulo y resuelve paso a paso.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{
        "role": "assistant",
        "content": (
            "¡Hola! Soy tu asistente de **Física Aplicada 1**. Cubro el sílabo completo:\n\n"
            "| Módulo | Semanas | Temas |\n|--------|---------|-------|\n"
            "| 🟡 **M1 Electrostática** | 1–3 | Ley de Coulomb · Campo E · Potencial · Capacitores |\n"
            "| 🟢 **M2 Electrodinámica** | 4–7 | Ley de Ohm · Kirchhoff · R equiv. · RC Transitorio · Potencia |\n"
            "| 🔵 **M3 Magnetismo/CA** | 9–13 | Lorentz · Biot-Savart · Faraday-Lenz · RLC · CircuitJS |\n"
            "| 🟣 **M4 Electrónica** | 14–15 | Diodos · Rectificadores · Zener |\n\n"
            "**Escribe tu ejercicio** con los datos (detectaré el módulo automáticamente) "
            "o **pega un netlist de CircuitJS** para leerlo y resolverlo.\n\n"
            "*Ejemplos: `Fuerza Coulomb q1=5µC q2=3µC r=0.3m` · "
            "`R1=10 R2=22 paralelo V=9V` · `RLC serie V=120 f=60 R=50 L=0.2 C=30µF` · "
            "`Puente rectificador Vp=170 R=1kohm`*"
        )
    }]

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("fig") is not None:
            st.plotly_chart(msg["fig"], use_container_width=True)

if prompt := st.chat_input("Escribe tu ejercicio (cualquier módulo) o pega un netlist de CircuitJS..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("🔬 Identificando módulo y resolviendo...", expanded=True) as status_box:
            time.sleep(0.3)
            tipo_resp, net_data, res_ac, respuesta = procesar_consulta(prompt)
            m_id = tipo_resp.split("_")[0].upper()
            info_m = MODULOS.get(m_id)
            label = (f"✅ {info_m['nombre']} (Sem. {info_m['semanas']})"
                     if info_m else "✅ Respuesta lista")
            status_box.update(label=label, state="complete", expanded=False)

        fig_osciloscopio = None
        # Actualizar estado CA si aplica y generar osciloscopio virtual
        if tipo_resp in ("netlist_xml", "netlist_text", "M3_ca") and net_data and res_ac:
            st.session_state.v_rms = net_data.get("v_rms", st.session_state.v_rms)
            st.session_state.f = net_data.get("f", st.session_state.f)
            st.session_state.componentes = net_data.get("componentes",
                                                        st.session_state.componentes)
            st.session_state.tipo = net_data.get("tipo", st.session_state.tipo)
            # Sincronización del simulador respetando el netlist y frecuencia original
            st.session_state.circuitjs_url = actualizar_iframe_circuitjs(
                tipo_resp, prompt, net_data
            )

            fig_osciloscopio = crear_osciloscopio_ac(res_ac)

        st.markdown(respuesta)
        if fig_osciloscopio is not None:
            st.plotly_chart(fig_osciloscopio, use_container_width=True)

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": respuesta,
            "fig": fig_osciloscopio
        })

        if tipo_resp in ("netlist_xml", "netlist_text", "M3_ca") and net_data:
            st.rerun()
        elif tipo_resp == "M1" and "sim_circuito" in st.session_state:
            sim = st.session_state.sim_circuito
            st.session_state.circuitjs_url = generar_url_circuitjs(
                sim["v_rms"], sim["f"], sim["comps"], sim.get("tipo", "serie"))
            st.rerun()
