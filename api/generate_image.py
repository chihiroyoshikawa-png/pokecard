# -*- coding: utf-8 -*-
"""Vercel Serverless Function: DALL-E 画像生成 API"""

from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

MOTIF_MAP = {
    "cat": "cat", "dog": "dog", "fox": "fox", "rabbit": "rabbit",
    "bear": "bear", "bird": "bird", "dragon": "dragon", "wolf": "wolf",
    "lizard": "lizard", "fish": "fish", "butterfly": "butterfly", "snake": "snake",
}

TYPE_VISUAL = {
    "fire": {"colors": "warm red and orange", "element": "fire, flames, ember glow"},
    "water": {"colors": "blue and aqua", "element": "water, bubbles, ocean waves"},
    "electric": {"colors": "yellow and gold", "element": "lightning, electric sparks, thunderbolt"},
    "flying": {"colors": "purple and lavender", "element": "wind, feathers, clouds"},
    "grass": {"colors": "green and leaf-green", "element": "leaves, vines, nature"},
    "ice": {"colors": "cyan and icy blue", "element": "ice crystals, frost, snowflakes"},
}

VIBE_STYLE = {
    "fuwafuwa": "soft_cute", "nikoniko": "soft_cute", "pokapoka": "soft_cute",
    "tekipaki": "energetic_cute", "kirakira": "energetic_cute", "wakuwaku": "energetic_cute",
    "kiri": "cool", "shu": "cool", "meramera": "cool",
}

STYLE_PROMPTS = {
    "soft_cute": {
        "tone": "A soft, round, and gentle",
        "design": "rounded body shape with stubby limbs, simple small dot eyes or half-closed relaxed eyes, "
                  "no eyelashes or sparkle highlights, calm neutral expression, "
                  "one deliberate quirky feature like an oversized tail or asymmetric ear",
    },
    "energetic_cute": {
        "tone": "A lively and energetic",
        "design": "dynamic pose, simple round eyes with small pupils, wide open-mouth grin, "
                  "compact athletic body, no sparkle effects or star highlights in eyes, "
                  "one playful asymmetric feature like a crooked fang or uneven markings",
    },
    "cool": {
        "tone": "A fierce, sleek, and powerful",
        "design": "sharp angular body shape, narrow eyes with simple slit pupils, "
                  "streamlined muscular body, confident stance, "
                  "spiky or flowing natural body features like fins or crests, "
                  "bold contrasting colors with dark accents",
    },
}


def resolve_style(vibes):
    if not vibes:
        return STYLE_PROMPTS["energetic_cute"]

    category_counts = {}
    for v in vibes:
        cat = VIBE_STYLE.get(v, "energetic_cute")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    sorted_cats = sorted(category_counts.items(), key=lambda x: -x[1])

    if len(sorted_cats) == 1 or sorted_cats[0][1] > sorted_cats[1][1]:
        return STYLE_PROMPTS[sorted_cats[0][0]]

    cat_a, cat_b = sorted_cats[0][0], sorted_cats[1][0]
    a, b = STYLE_PROMPTS[cat_a], STYLE_PROMPTS[cat_b]
    return {
        "tone": f"{a['tone'].rstrip(',')} yet {b['tone'].lower().lstrip('a ')}",
        "design": f"{a['design']}, blended with {b['design']}",
    }


def build_image_prompt(type_key, motifs, vibes=None, creature_prompt=None):
    visual = TYPE_VISUAL.get(type_key, TYPE_VISUAL["fire"])
    style = resolve_style(vibes)
    motif_animals = [MOTIF_MAP.get(m, m) for m in motifs]

    if len(motif_animals) == 1:
        creature_desc = f"{motif_animals[0]}"
    else:
        creature_desc = f"fusion of {motif_animals[0]} and {motif_animals[1]}"

    extra = ""
    if creature_prompt:
        extra = f" {creature_prompt}."

    prompt = (
        f"{style['tone']} fictional creature in the style of Ken Sugimori's official Pokemon artwork. "
        f"The creature is a {creature_desc} with {visual['element']} themed natural body features. "
        f"Color palette: {visual['colors']}, flat cel-shaded coloring with only 2-3 main colors. "
        f"Design: {style['design']}. "
        f"IMPORTANT RULES: simple dot eyes or small oval eyes with NO sparkle highlights and NO star reflections. "
        f"NO accessories, NO jewelry, NO necklaces, NO scarves, NO clothing - all features must be biological body parts. "
        f"Moderate detail level - a few strong recognizable features, not overdecorated. "
        f"Must pass the silhouette test - recognizable shape even as a solid black shadow. "
        f"White background, full body, front-facing, clean lineart, official Pokemon game art style.{extra}"
    )
    return prompt


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        if not data or not data.get("type") or not data.get("motifs"):
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "タイプとモチーフが必要です"}, ensure_ascii=False).encode("utf-8"))
            return

        type_key = data["type"]
        motifs = data["motifs"]
        creature_prompt = data.get("creature_prompt")
        vibes = data.get("vibes", [])
        prompt = build_image_prompt(type_key, motifs, vibes, creature_prompt)

        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                response_format="b64_json",
            )

            image_data = response.data[0].b64_json

            # Vercelはファイル保存不可のため、base64データURLとして返す
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "image_url": f"data:image/png;base64,{image_data}"
            }).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"画像生成エラー: {str(e)}"}, ensure_ascii=False).encode("utf-8"))
