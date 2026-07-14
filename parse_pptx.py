import xml.etree.ElementTree as ET
import json
import re
import shutil
from pathlib import Path

BASE = Path(__file__).parent
EXTRACTED = BASE / "pptx_extracted" / "ppt"
OUT = BASE / "assets"
OUT.mkdir(exist_ok=True)

SW, SH = 18288000, 10287000
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def emu_pct(x, y, w, h):
    return {
        "left": round(x / SW * 100, 3),
        "top": round(y / SH * 100, 3),
        "width": round(w / SW * 100, 3),
        "height": round(h / SH * 100, 3),
    }


def load_rels(path: Path):
    rels = {}
    rel_path = path.parent / "_rels" / f"{path.name}.rels"
    if not rel_path.exists():
        return rels
    for rel in ET.parse(rel_path).getroot():
        rels[rel.attrib["Id"]] = rel.attrib["Target"]
    return rels


def copy_media(target: str):
    if not target:
        return None
    src = (EXTRACTED / target.replace("../", "")).resolve()
    if not src.exists():
        src = (EXTRACTED / "slides" / target).resolve()
    if not src.exists():
        return target
    dest = OUT / src.name
    if not dest.exists():
        shutil.copy2(src, dest)
    return f"assets/{src.name}"


def slide_id_from_target(target: str):
    m = re.search(r"slide(\d+)\.xml", target or "")
    return int(m.group(1)) if m else None


def get_xfrm(node):
    xfrm = node.find(".//a:xfrm", NS)
    if xfrm is None:
        return {}
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return {}
    try:
        return emu_pct(int(off.attrib["x"]), int(off.attrib["y"]), int(ext.attrib["cx"]), int(ext.attrib["cy"]))
    except KeyError:
        return {}


def get_text(node):
    parts = []
    for t in node.findall(".//a:t", NS):
        if t.text:
            parts.append(t.text)
    return "".join(parts).strip()


def get_font(node):
    rpr = node.find(".//a:rPr", NS)
    if rpr is None:
        return {}
    font = {"size": int(rpr.attrib.get("sz", 1800)) / 100}
    if rpr.attrib.get("b") == "1":
        font["bold"] = True
    if rpr.attrib.get("i") == "1":
        font["italic"] = True
    latin = rpr.find("a:latin", NS)
    if latin is not None:
        font["family"] = latin.attrib.get("typeface", "")
    fill = rpr.find("a:solidFill/a:srgbClr", NS)
    if fill is not None:
        font["color"] = "#" + fill.attrib["val"]
    scheme = rpr.find("a:solidFill/a:schemeClr", NS)
    if scheme is not None:
        font["color"] = "white" if scheme.attrib.get("val") == "bg1" else scheme.attrib.get("val")
    return font


def get_link(node, rels):
    hlink = node.find(".//a:hlinkClick", NS)
    if hlink is None:
        return None
    rid = hlink.attrib.get(RID)
    if not rid or rid not in rels:
        return None
    target = rels[rid]
    sid = slide_id_from_target(target)
    if sid:
        return {"type": "slide", "slide": sid}
    return {"type": "external", "target": target}


def get_image(node, rels):
    blip = node.find(".//a:blip", NS)
    if blip is None:
        return None
    rid = blip.attrib.get(RID.replace("id", "embed"))
    # embed attribute uses full namespace
    for key, val in blip.attrib.items():
        if key.endswith("embed"):
            rid = val
            break
    if rid and rid in rels:
        return copy_media(rels[rid])
    return None


def parse_bg(root):
    bg_el = root.find(".//p:bg", NS)
    if bg_el is None:
        return None
    solid = bg_el.find(".//a:srgbClr", NS)
    if solid is not None:
        return {"type": "color", "value": "#" + solid.attrib.get("val", "000000")}
    blip = bg_el.find(".//a:blip", NS)
    if blip is not None:
        return {"type": "image", "value": None}
    return None


def parse_slide(slide_path: Path):
    root = ET.parse(slide_path).getroot()
    rels = load_rels(slide_path)
    slide_num = int(re.search(r"slide(\d+)", slide_path.name).group(1))

    audio = []
    for rel_id, target in rels.items():
        if target.endswith(".mp3"):
            audio.append(copy_media(target))

    elements = []
    for node in root.findall(".//p:sp", NS):
        nv = node.find("p:nvSpPr/p:cNvPr", NS)
        name = nv.attrib.get("name", "") if nv is not None else ""
        text = get_text(node)
        img = get_image(node, rels)
        pos = get_xfrm(node)
        link = get_link(node, rels)
        font = get_font(node) if text else {}
        if text or img or link:
            elements.append(
                {
                    "name": name,
                    "text": text,
                    "pos": pos,
                    "font": font,
                    "link": link,
                    "image": img,
                    "kind": "shape",
                }
            )

    for node in root.findall(".//p:pic", NS):
        nv = node.find("p:nvPicPr/p:cNvPr", NS)
        name = nv.attrib.get("name", "") if nv is not None else ""
        img = get_image(node, rels)
        pos = get_xfrm(node)
        link = get_link(node, rels)
        if img or link:
            elements.append(
                {
                    "name": name,
                    "text": "",
                    "pos": pos,
                    "font": {},
                    "link": link,
                    "image": img,
                    "kind": "picture",
                }
            )

    return {
        "id": slide_num,
        "bg": parse_bg(root),
        "audio": audio,
        "elements": elements,
    }


slides = []
for i in range(1, 17):
    p = EXTRACTED / "slides" / f"slide{i}.xml"
    if p.exists():
        slides.append(parse_slide(p))

(BASE / "slides-data.json").write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Parsed {len(slides)} slides, assets in {OUT}")
