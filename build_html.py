"""Gera index.html a partir de slides-data.json."""
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
slides = json.loads((BASE / "slides-data.json").read_text(encoding="utf-8"))

# Correções de links não capturados no parser
MANUAL_LINKS = {
    (1, "Começar"): 2,
    (1, "Freeform 3"): 2,
    (11, "18 ou mais"): 16,
    (12, "Voltar ao início"): 1,
    (13, "Voltar ao início"): 1,
    (14, "Voltar ao início"): 1,
}

BUTTON_IMG = "assets/image3.png"
NARRATIVE_BG = "assets/image3.png"  # layered decorative panels


def is_background(el, slide):
    if el.get("image") and el["pos"].get("width", 0) >= 99:
        return True
    if el.get("name") == "Freeform 2" and el.get("image"):
        return True
    return False


def is_button_bg(el):
    if el.get("image") != BUTTON_IMG:
        return False
    w = el["pos"].get("width", 0)
    h = el["pos"].get("height", 0)
    return 8 <= w <= 48 and 4 <= h <= 22


def is_narrative_panel(el):
    name = el.get("name", "")
    if name.startswith("TextBox") and el.get("text") and len(el["text"]) > 40:
        return True
    if el.get("image") == BUTTON_IMG and not is_button_bg(el):
        return True
    return False


def is_button(el, slide_id):
    text = (el.get("text") or "").strip()
    if get_link(el, slide_id):
        return True
    if text in ("Começar", "Voltar ao início", "continuar"):
        return True
    return False


def get_link(el, slide_id):
    text = (el.get("text") or "").strip()
    key = (slide_id, text) if text else (slide_id, el.get("name", ""))
    if key in MANUAL_LINKS:
        return MANUAL_LINKS[key]
    link = el.get("link")
    if link and link.get("type") == "slide":
        return link["slide"]
    if text == "Voltar ao início":
        return 1
    if text == "Começar":
        return 2
    if text == "continuar" and slide_id == 16:
        return 13
    if text == "18 ou mais" and slide_id == 11:
        return 16
    return None


def format_label(label: str) -> str:
    """Formata rótulos longos para exibição em botões."""
    label = label.replace('"', "&quot;")
    replacements = {
        "Usar passagem secretaBônus de furtividade: +1": (
            "Usar passagem secreta<span class='btn-sub'>Bônus de furtividade: +1</span>"
        ),
        "Provocar um curto circuito no candelabro": (
            "Provocar curto-circuito<span class='btn-sub'>no candelabro</span>"
        ),
        "Entrar pela Porta Principal": "Entrar pela<br>Porta Principal",
        "Entrar pela uma janela": "Entrar por<br>uma janela",
        "Ir para o confronto": "Ir para o<br>confronto",
        "Voltar ao início": "Voltar ao<br>início",
        "menor que 11": "Menor que 11",
        "menor que 12": "Menor que 12",
        "menor que 15": "Menor que 15",
        "menos que 10": "Menos que 10",
        "Entrar na porta à direita.": "Entrar na porta<br>à direita",
    }
    return replacements.get(label, label)


def slide_needs_dice(slide_data):
    text = (slide_data.get("narrative") or {}).get("text", "")
    return "D20" in text.upper() or "role um" in text.lower()


D20_HTML = """  <div class="d20-zone" aria-live="polite">
    <button type="button" class="d20-btn" aria-label="Rolar D20">
      <div class="d20-die">
        <svg class="d20-shape" viewBox="0 0 100 100" aria-hidden="true">
          <polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="currentColor"/>
          <polygon points="50,4 93,27 50,50 7,27" fill="rgba(0,0,0,.18)"/>
          <polygon points="50,50 93,27 93,73 50,96" fill="rgba(255,255,255,.08)"/>
        </svg>
        <span class="d20-num">?</span>
      </div>
    </button>
    <span class="d20-tag">D20</span>
    <span class="d20-result"></span>
  </div>"""


def button_zone(btn, slide_id):
    if slide_id == 1:
        return "center"
    return "footer"


def build_slide_html(slide):
    sid = slide["id"]
    layers = []
    narrative = None
    buttons = []
    overlays = []

    bg_img = None
    for el in slide["elements"]:
        if is_background(el, slide):
            bg_img = el["image"]
            break

    for el in slide["elements"]:
        if is_background(el, slide):
            continue

        text = (el.get("text") or "").strip()
        pos = el.get("pos") or {}
        link = get_link(el, sid)

        if is_button(el, sid):
            label = text
            if not label:
                continue
            buttons.append({"el": el, "label": label, "link": link, "pos": pos})
            continue

        if is_narrative_panel(el) and text:
            narrative = {"text": text, "pos": pos, "font": el.get("font", {})}
            continue

        if el.get("image") and el["image"] != BUTTON_IMG:
            overlays.append(el)

    # pair button backgrounds with text buttons
    btn_bgs = [
        el
        for el in slide["elements"]
        if is_button_bg(el) and not (el.get("text") or "").strip()
    ]
    paired = []
    used_bg = set()
    for btn in buttons:
        if not btn["label"]:
            continue
        best = None
        best_dist = 999
        for i, bg in enumerate(btn_bgs):
            if i in used_bg:
                continue
            bp = bg["pos"]
            tp = btn["pos"]
            dist = abs(bp.get("left", 0) - tp.get("left", 0)) + abs(bp.get("top", 0) - tp.get("top", 0))
            if dist < best_dist:
                best_dist = dist
                best = i
        style_pos = btn["pos"]
        if best is not None and best_dist < 15:
            used_bg.add(best)
            style_pos = btn_bgs[best]["pos"]
        paired.append({**btn, "pos": style_pos})

    if not paired:
        # buttons only as text with nearby bg
        for el in slide["elements"]:
            link = get_link(el, sid)
            text = (el.get("text") or "").strip()
            if link and text:
                pos = el["pos"]
                for bg in btn_bgs:
                    bp = bg["pos"]
                    if abs(bp.get("left", 0) - pos.get("left", 0)) < 20 and abs(bp.get("top", 0) - pos.get("top", 0)) < 8:
                        pos = bp
                        break
                paired.append({"label": text, "link": link, "pos": pos, "font": el.get("font", {})})

    audio = slide.get("audio") or []
    audio_src = audio[0] if audio else None

    grouped = {"footer": [], "middle": [], "center": []}
    for btn in sorted(paired, key=lambda b: (b["pos"].get("top", 0), b["pos"].get("left", 0))):
        if not btn.get("link"):
            continue
        zone = button_zone(btn, sid)
        grouped[zone].append(btn)

    return {
        "id": sid,
        "bg": bg_img,
        "audio": audio_src,
        "narrative": narrative,
        "buttons": paired,
        "button_groups": grouped,
        "overlays": overlays,
        "needs_dice": bool(narrative and slide_needs_dice({"narrative": narrative})),
    }


processed = [build_slide_html(s) for s in slides]

css = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Source+Sans+3:wght@400;600;700&display=swap');

:root {
  --slide-ratio: 16 / 9;
  --btn-font: 'Source Sans 3', 'Segoe UI', sans-serif;
  --title-font: 'Cinzel', Georgia, serif;
  --text-shadow: 0 2px 8px rgba(0,0,0,.85);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #0a0a0a;
  font-family: var(--btn-font);
  color: #f2e8d8;
}

#app {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

#stage-wrap {
  position: relative;
  width: min(100vw - 24px, calc((100vh - 80px) * 16 / 9));
  aspect-ratio: 16 / 9;
  max-height: calc(100vh - 80px);
}

#stage {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 2px solid #3a2a1a;
  box-shadow: 0 0 60px rgba(120, 20, 20, .35), inset 0 0 80px rgba(0,0,0,.4);
  background: #111;
  container-type: size;
}

.slide {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
  transition: opacity .45s ease;
}

.slide.active {
  opacity: 1;
  pointer-events: auto;
}

.slide-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.slide-overlay {
  position: absolute;
  object-fit: contain;
  pointer-events: none;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,.6));
}

.narrative {
  position: absolute;
  padding: 1.2% 1.4%;
  max-width: 32%;
  font-size: clamp(11px, 1.35vw, 22px);
  line-height: 1.35;
  color: #111;
  font-weight: 600;
  text-shadow: none;
  background: url('assets/image3.png') center/100% 100% no-repeat;
  z-index: 5;
}

.narrative::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(245, 235, 210, .78);
  z-index: -1;
  border-radius: 2px;
}

.action-btn {
  position: relative;
  z-index: 10;
  border: none;
  cursor: pointer;
  color: #14100a;
  font-family: var(--btn-font);
  font-weight: 700;
  font-size: clamp(11px, 1.05cqw, 15px);
  line-height: 1.25;
  text-align: center;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.55em 1em;
  min-height: 2.8em;
  background:
    linear-gradient(180deg, rgba(255,255,255,.92) 0%, rgba(232,220,198,.95) 100%) padding-box,
    url('assets/image3.png') center/100% 100% no-repeat border-box;
  border: 2px solid #0d0d0d;
  box-shadow:
    0 3px 0 #0d0d0d,
    0 6px 16px rgba(0,0,0,.45),
    inset 0 1px 0 rgba(255,255,255,.65);
  transition: transform .15s ease, filter .15s ease, box-shadow .15s ease;
  text-shadow: 0 1px 0 rgba(255,255,255,.35);
  letter-spacing: .02em;
  word-break: break-word;
  hyphens: auto;
}

.action-btn .btn-sub {
  display: block;
  font-size: .78em;
  font-weight: 600;
  margin-top: .15em;
  opacity: .85;
}

.action-btn:hover {
  transform: translateY(-2px);
  filter: brightness(1.05);
  box-shadow:
    0 5px 0 #0d0d0d,
    0 10px 22px rgba(0,0,0,.5),
    inset 0 1px 0 rgba(255,255,255,.7);
}

.action-btn:active {
  transform: translateY(1px);
  box-shadow:
    0 1px 0 #0d0d0d,
    0 3px 8px rgba(0,0,0,.4),
    inset 0 1px 0 rgba(255,255,255,.5);
}

.actions-footer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 12;
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: center;
  gap: clamp(8px, 1.2cqw, 14px);
  padding: clamp(10px, 1.8cqw, 18px) clamp(12px, 2cqw, 24px) clamp(12px, 2cqw, 20px);
  background:
    linear-gradient(to top, rgba(0,0,0,.88) 0%, rgba(0,0,0,.55) 55%, transparent 100%);
  container-type: inline-size;
}

.actions-footer .action-btn {
  flex: 1 1 calc(50% - 8px);
  max-width: calc(50% - 4px);
  min-width: min(42%, 160px);
}

.actions-footer.count-1 .action-btn {
  flex: 0 1 min(52%, 320px);
  max-width: min(52%, 320px);
}

.actions-footer.count-3 .action-btn {
  flex: 1 1 calc(33.33% - 8px);
  max-width: calc(33.33% - 4px);
  min-width: min(30%, 120px);
  font-size: clamp(10px, .95cqw, 13px);
}

.actions-center {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.actions-center .action-btn {
  pointer-events: auto;
  flex: 0 1 min(38%, 340px);
  min-height: 3.4em;
  font-size: clamp(14px, 1.5cqw, 22px);
  padding: 0.7em 1.4em;
}

.actions-middle {
  position: absolute;
  left: 0;
  right: 0;
  z-index: 12;
  display: flex;
  justify-content: flex-start;
  padding: 0 clamp(8px, 1.5cqw, 20px);
  container-type: inline-size;
}

.actions-middle .action-btn {
  flex: 0 1 min(36%, 280px);
  font-size: clamp(10px, 1cqw, 14px);
}

.d20-zone {
  position: absolute;
  top: clamp(8px, 2.5cqh, 24px);
  right: clamp(8px, 2cqw, 20px);
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  pointer-events: auto;
}

.d20-btn {
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  perspective: 500px;
  -webkit-tap-highlight-color: transparent;
}

.d20-die {
  position: relative;
  width: clamp(52px, 7.5cqw, 80px);
  height: clamp(52px, 7.5cqw, 80px);
  color: #8f1d1d;
  filter: drop-shadow(0 6px 14px rgba(0,0,0,.65));
  transition: transform .2s ease;
}

.d20-shape {
  width: 100%;
  height: 100%;
  display: block;
}

.d20-num {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--title-font);
  font-weight: 700;
  font-size: clamp(18px, 2.8cqw, 30px);
  color: #f4e4bc;
  text-shadow: 0 2px 4px rgba(0,0,0,.9), 0 0 12px rgba(180,40,40,.5);
  letter-spacing: -.02em;
}

.d20-btn:hover .d20-die {
  transform: scale(1.06);
}

.d20-btn:active .d20-die {
  transform: scale(.96);
}

.d20-die.rolling {
  animation: d20-tumble 0.85s cubic-bezier(.2,.8,.2,1);
}

@keyframes d20-tumble {
  0%   { transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg) scale(1); }
  25%  { transform: rotateX(180deg) rotateY(90deg) rotateZ(45deg) scale(1.08); }
  50%  { transform: rotateX(360deg) rotateY(270deg) rotateZ(90deg) scale(1.12); }
  75%  { transform: rotateX(540deg) rotateY(450deg) rotateZ(135deg) scale(1.05); }
  100% { transform: rotateX(720deg) rotateY(630deg) rotateZ(180deg) scale(1); }
}

.d20-tag {
  font-family: var(--title-font);
  font-size: clamp(9px, 1cqw, 12px);
  letter-spacing: .2em;
  color: #c9a86a;
  text-shadow: 0 1px 6px rgba(0,0,0,.9);
}

.d20-result {
  font-size: clamp(10px, 1.1cqw, 14px);
  font-weight: 700;
  color: #f0e0c0;
  background: rgba(0,0,0,.72);
  border: 1px solid #6b4a2a;
  padding: 3px 8px;
  border-radius: 3px;
  opacity: 0;
  transform: translateY(-4px);
  transition: opacity .3s ease, transform .3s ease;
  white-space: nowrap;
  text-shadow: 0 1px 4px rgba(0,0,0,.8);
}

.d20-result.show {
  opacity: 1;
  transform: translateY(0);
}

#controls {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: linear-gradient(transparent, rgba(0,0,0,.92));
  z-index: 100;
}

#controls button, #controls label {
  background: rgba(40, 28, 18, .9);
  border: 1px solid #6b4a2a;
  color: #e8d5b5;
  padding: 8px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-family: var(--btn-font);
  font-size: 13px;
}

#controls button:hover { background: rgba(80, 50, 28, .95); }

#start-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.88);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 200;
  text-align: center;
  padding: 24px;
}

#start-overlay h1 {
  font-family: var(--title-font);
  font-size: clamp(1.4rem, 4vw, 2.6rem);
  margin-bottom: 12px;
  color: #c9a86a;
  letter-spacing: .12em;
}

#start-overlay p {
  max-width: 480px;
  color: #b8a890;
  margin-bottom: 24px;
  line-height: 1.5;
}

#start-overlay button {
  font-family: var(--title-font);
  font-size: 1.1rem;
  padding: 14px 36px;
  background: linear-gradient(180deg, #5c3d22, #2a1a0e);
  border: 2px solid #8b6914;
  color: #f0e0c0;
  cursor: pointer;
  letter-spacing: .15em;
}

#start-overlay button:hover {
  filter: brightness(1.15);
}

@media (max-width: 640px) {
  .narrative {
    max-width: 42%;
    font-size: clamp(9px, 2.8vw, 14px);
  }
  .actions-footer .action-btn {
    flex: 1 1 100%;
    max-width: 100%;
    min-width: 0;
    font-size: clamp(11px, 3.2vw, 14px);
  }
  .actions-footer.count-3 .action-btn {
    flex: 1 1 calc(50% - 6px);
    max-width: calc(50% - 3px);
  }
  .actions-footer.count-3 .action-btn:last-child {
    flex: 1 1 100%;
    max-width: 100%;
  }
  .d20-zone {
    top: 6px;
    right: 6px;
  }
  .d20-die {
    width: clamp(44px, 12vw, 64px);
    height: clamp(44px, 12vw, 64px);
  }
}
"""

def render_buttons(group, css_class, top_hint=None):
    if not group:
        return []
    count_class = f" count-{len(group)}"
    lines = [f'  <div class="{css_class}{count_class}"{top_hint or ""}>']
    for btn in group:
        label = format_label(btn["label"])
        lines.append(
            f'    <button class="action-btn" type="button" data-goto="{btn["link"]}" '
            f'title="{btn["label"].replace(chr(34), "&quot;")}">{label}</button>'
        )
    lines.append("  </div>")
    return lines


slides_html = []
for s in processed:
    parts = [f'<section class="slide" id="slide-{s["id"]}" data-slide="{s["id"]}" data-audio="{s["audio"] or ""}">']
    if s["bg"]:
        parts.append(f'  <img class="slide-bg" src="{s["bg"]}" alt="" draggable="false">')
    for ov in s["overlays"]:
        p = ov["pos"]
        parts.append(
            f'  <img class="slide-overlay" src="{ov["image"]}" alt="" draggable="false" '
            f'style="left:{p.get("left",0)}%;top:{p.get("top",0)}%;width:{p.get("width",10)}%;height:{p.get("height",10)}%">'
        )
    if s["narrative"]:
        n = s["narrative"]
        p = n["pos"]
        parts.append(
            f'  <div class="narrative" style="left:{p.get("left",0)}%;top:{p.get("top",0)}%;'
            f'width:{p.get("width",30)}%;min-height:{p.get("height",10)}%">{n["text"]}</div>'
        )

    if s.get("needs_dice"):
        parts.append(D20_HTML)

    groups = s.get("button_groups", {"footer": s["buttons"], "middle": [], "center": []})
    parts.extend(render_buttons(groups.get("center", []), "actions-center"))
    if groups.get("middle"):
        avg_top = sum(b["pos"].get("top", 55) for b in groups["middle"]) / len(groups["middle"])
        parts.extend(render_buttons(groups["middle"], "actions-middle", f' style="top:{avg_top:.1f}%"'))
    parts.extend(render_buttons(groups.get("footer", []), "actions-footer"))

    parts.append("</section>")
    slides_html.append("\n".join(parts))

js_data = json.dumps([{"id": s["id"], "audio": s["audio"]} for s in processed], ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Ordem Paranormal — Livro Jogo v4</title>
  <style>{css}</style>
</head>
<body>
  <div id="start-overlay">
    <h1>ORDEM PARANORMAL</h1>
    <p>Livro-jogo interativo — Sanatório Alvorada. Clique nas ações conforme suas rolagens de D20 e siga a história.</p>
    <button type="button" id="btn-enter">Entrar na missão</button>
  </div>

  <div id="app">
    <div id="stage-wrap">
      <div id="stage">
{chr(10).join(slides_html)}
      </div>
    </div>
  </div>

  <div id="controls">
    <button type="button" id="btn-mute" aria-pressed="false">🔊 Música</button>
    <button type="button" id="btn-fullscreen">Tela cheia</button>
  </div>

  <audio id="bgm" loop preload="auto"></audio>

  <script>
    const SLIDES = {js_data};
    let current = 1;
    let started = false;
    let muted = false;

    const bgm = document.getElementById('bgm');

    function showSlide(id) {{
      current = id;
      document.querySelectorAll('.slide').forEach(el => {{
        el.classList.toggle('active', Number(el.dataset.slide) === id);
      }});

      const slide = SLIDES.find(s => s.id === id);
      if (slide && slide.audio && !muted) {{
        if (bgm.getAttribute('src') !== slide.audio) {{
          bgm.src = slide.audio;
          bgm.currentTime = 0;
        }}
        bgm.play().catch(() => {{}});
      }}

      const diceZone = document.querySelector(`#slide-${{id}} .d20-zone`);
      if (diceZone) {{
        const num = diceZone.querySelector('.d20-num');
        const result = diceZone.querySelector('.d20-result');
        const die = diceZone.querySelector('.d20-die');
        if (num) num.textContent = '?';
        if (result) {{
          result.textContent = '';
          result.classList.remove('show');
        }}
        if (die) die.classList.remove('rolling');
      }}
    }}

    function rollD20(btn) {{
      if (btn.disabled) return;
      const zone = btn.closest('.d20-zone');
      const die = btn.querySelector('.d20-die');
      const numEl = btn.querySelector('.d20-num');
      const resultEl = zone.querySelector('.d20-result');
      if (!die || !numEl) return;

      btn.disabled = true;
      die.classList.add('rolling');

      let tick = 0;
      const ticks = 20;
      const tickMs = 45;

      const interval = setInterval(() => {{
        numEl.textContent = String(Math.floor(Math.random() * 20) + 1);
        tick += 1;
        if (tick >= ticks) {{
          clearInterval(interval);
          const final = Math.floor(Math.random() * 20) + 1;
          numEl.textContent = String(final);
          die.classList.remove('rolling');
          resultEl.textContent = 'Rolou: ' + final;
          resultEl.classList.add('show');
          btn.disabled = false;
        }}
      }}, tickMs);
    }}

    function goTo(id) {{
      if (id >= 1 && id <= 16) showSlide(id);
    }}

    document.getElementById('stage').addEventListener('click', e => {{
      const d20 = e.target.closest('.d20-btn');
      if (d20) {{
        e.preventDefault();
        e.stopPropagation();
        rollD20(d20);
        return;
      }}
      const btn = e.target.closest('[data-goto]');
      if (btn) {{
        e.preventDefault();
        goTo(Number(btn.dataset.goto));
      }}
    }});

    document.getElementById('btn-enter').addEventListener('click', () => {{
      started = true;
      document.getElementById('start-overlay').style.display = 'none';
      showSlide(1);
      if (!muted) bgm.play().catch(() => {{}});
    }});

    document.getElementById('btn-mute').addEventListener('click', () => {{
      muted = !muted;
      const b = document.getElementById('btn-mute');
      b.textContent = muted ? '🔇 Música' : '🔊 Música';
      b.setAttribute('aria-pressed', String(muted));
      if (muted) bgm.pause();
      else if (started) bgm.play().catch(() => {{}});
    }});

    document.getElementById('btn-fullscreen').addEventListener('click', () => {{
      const el = document.documentElement;
      if (!document.fullscreenElement) el.requestFullscreen?.();
      else document.exitFullscreen?.();
    }});

    document.addEventListener('keydown', e => {{
      if (e.key === 'f' || e.key === 'F') document.getElementById('btn-fullscreen').click();
    }});
  </script>
</body>
</html>
"""

(BASE / "index.html").write_text(html, encoding="utf-8")
print("index.html gerado com", len(processed), "slides")
