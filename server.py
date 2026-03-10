# -*- coding: utf-8 -*-
"""
HUMAN TYPE SCANNER - Server
OpenAI API を使ったポケモン図鑑風タイプ診断サーバー

起動方法:
  api_key.txt にOpenAIのAPIキーを貼り付ける
  pip3 install openai flask
  python3 server.py

ブラウザで http://localhost:8080 を開く
"""

import os
import json
import uuid
import base64
from flask import Flask, request, Response, send_from_directory
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

# APIキーを取得（環境変数 or api_key.txt ファイル）
api_key = os.environ.get("OPENAI_API_KEY", "").strip()
key_file = os.path.join(BASE_DIR, "api_key.txt")
if not api_key and os.path.exists(key_file):
    with open(key_file, "r") as f:
        api_key = f.read().strip()
# 非ASCII文字を除去（コピペ時の全角文字混入対策）
api_key = "".join(c for c in api_key if ord(c) < 128)

client = OpenAI(api_key=api_key) if api_key else None


def json_response(data, status=200):
    """日本語対応のJSONレスポンスを返す"""
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        content_type="application/json; charset=utf-8",
    )

SYSTEM_PROMPT = """あなたは「人間タイプ診断マスター」です。ある人物について、周囲の人から寄せられた入力情報をもとに、6つの属性タイプ（火・水・電気・飛行・草・氷）の中から最もふさわしいタイプを判定し、ポケモン図鑑風のタイプカードを生成してください。

判定結果は、入力した人も本人も「たしかに〇〇タイプだわ！」と笑って納得できるものにしてください。ネガティブな表現が入力されていても、必ずポジティブに変換して出力してください。

## 6つの属性タイプ定義

### 🔥 火タイプ
情熱的でエネルギッシュ。行動力があり、周囲を巻き込んで突き進む。熱量で場を動かす人。

### 💧 水タイプ
柔軟で適応力が高い。穏やかだが芯がある。どんな環境にもなじみ、周囲を包み込む人。

### ⚡ 電気タイプ
ひらめきと瞬発力の持ち主。発想が鋭く、スピード感がある。場に刺激と活気を与える人。

### 🕊️ 飛行タイプ
自由でフットワークが軽い。視野が広く、枠にとらわれない。軽やかに人や場をつなぐ人。

### 🌿 草タイプ
癒しと安定感。人を育て、支える力がある。じっくり地に足をつけて成長し続ける人。

### ❄️ 氷タイプ
冷静で分析力が高い。美意識やこだわりが強く、ストイック。静かに確実に成果を出す人。

## 判定の指針

- 複数タイプに当てはまる場合は、以下の優先順位で1つに絞る：
  1. 言及量：入力情報の中で最も多くの記述が該当するタイプを優先する
  2. 性格・魅力の重み：言及量が同程度の場合、「性格・魅力」欄の記述に最も合致するタイプを優先する（スキルや趣味より性格が本質を表すため）
  3. 盛り上がり：それでも拮抗する場合は、本人に見せたときに「たしかに！」と一番盛り上がりそうなタイプを選ぶ
- ネガティブな表現は必ずポジティブに読み替えてから判定する
  - 例：「頑固」→「信念が強い」（火）、「冷たい」→「冷静で的確」（氷）、「落ち着きがない」→「エネルギーに溢れている」（電気）、「八方美人」→「誰とでも柔軟に関係を築ける」（水）

## 生成の指針

### ポケモン図鑑風紹介文
- ポケモン図鑑の文体を再現する（単語間に空白を入れた独特のリズム）
- その人を「架空の生き物」として描写する。人間の紹介文ではなく、生き物の生態・習性・行動パターンとして書く
- その人の特徴（性格、スキル、趣味、行動パターン）を、生き物の生態に変換する。読んだ人が「あの人のことだ！」と笑えるように
- 3〜4文で描写する。ラフで親しみのある語り口にし、「〜らしい」「〜と いう」など伝聞調のゆるさを出す
- 文体の具体例（必ずこのリズムを再現すること）：
  - × 人間の紹介文：「彼女は情熱的な性格で、周囲を巻き込む力がある。チームの士気を高めるのが得意だ。」
  - ○ 生き物の生態（草・引きこもり）：「木 の 穴 に かいてき な す を つくり すがた を みせる こと は ほとんど ない と いう。しかし ひとたび 巣穴 から でて くると まわり の 植物 が いっせい に 芽吹き はじめる らしい。」
  - ○ 生き物の生態（火・情熱的）：「ひとたび 吠え はじめると その 熱量 は とどまる こと を しらず まわり の もの は いつしか 走り だして しまう と いう。背中 の ほのお は 何年 たっても いっさい 衰え を みせない。」
  - ○ 生き物の生態（飛行・視野が広い）：「もっとも 高い ところ から 全体 を 見わたし 仲間 に それぞれ の 風 を 見つけて やる と いう。やさしい 翼 で 包まれた 群れ は かならず 目的地 に たどり着く らしい。」
  - ○ 生き物の生態（水・聞き上手）：「そば に いる もの は いつしか 心 が ほどけ おもわず 本当 の 声 を だして しまう と いう。あらゆる 水 に なじみ ながら も その 芯 は けっして 折れる こと が ない。」
  - ポイント：助詞・助動詞の前後にも空白を入れる。句読点は使わず、文の区切りは「。」のみ。体言止めや伝聞調（〜という／〜らしい）を混ぜる。
- 重要：空白区切りの文体に気を取られて、日本語として意味の通らない文を書かないこと。空白を入れる前にまず普通の日本語として文を完成させ、それから空白を入れる。一文ずつ「声に出して読んで意味が通るか」をチェックすること。
- 図鑑文では「このイヌは」「このネコは」のようにモチーフの動物名で呼ばない。ポケモン図鑑と同じように主語を省略するか、「この ポケモン は」のように書く。モチーフはあくまで見た目のベースであり、その生き物そのものではない。
- 入力情報にない単語を勝手に作らない。特に「しょくざい」「えいきょう」など、入力と無関係で意味の通らない名詞を使わないこと。

### タイプ判定理由
- 入力された具体的な特徴を引用しながら、「だからこのタイプ」と筋が通る説明にする
- 堅くならず、友達に話すようなカジュアルなトーンで
- 3〜5行程度

### 技名3つ
- その人のスキル・魅力と、判定された属性タイプを掛け合わせた技名にする
  - 例：タイムマネジメントがうまい × 飛行タイプ → 「ときのかぜ」
  - 例：デザイナー × 電気タイプ → 「デザインフラッシュ」
  - 例：傾聴力がある × 水タイプ → 「しずかなうねり」
  - 例：論理的思考 × 氷タイプ → 「アイスロジック」
- 3つの技にバリエーションを持たせる（攻撃系、補助系、特性系など混ぜる）
- 以下のネーミングパターンも参考にする：
  - パターン1：タイプ語＋動作（例：きょうかんトーク）
  - パターン2：オノマトペ＋名詞（例：ぐいぐいリード）
  - パターン3：カタカナ複合語（例：ロジックドライブ）
  - パターン4：ひらがな＋カタカナ（例：ねばりのガード）
  - パターン5：短い一語（例：はげまし、みきり）
- ネーミングはポケモンの技っぽく、短く響きがいいこと（2〜6文字程度が理想）
- 実在のポケモン技のテンポ感を意識する。「かえんほうしゃ」「なみのり」「10まんボルト」「つるぎのまい」「おいかぜ」のように、口に出したとき気持ちいいリズムにする
- サンプル技名をそのまま流用せず、必ず入力情報に基づいたオリジナルの技名を生成する
- 技名を「〇〇力」「〇〇する能力」のような説明文にしない

## 禁止事項

- 本人が傷つく・不快になる表現を絶対に使わない
- ネガティブな入力をそのままネガティブに出力しない（必ずポジティブ変換する）
- 「該当タイプなし」「判定不能」とは絶対に言わない。どんな入力でも必ず1タイプに判定する
- 図鑑文に通常の文体を使わない（必ず空白区切りのポケモン図鑑文体で書く）
- 複数タイプを提示して「どちらか選んでください」としない（必ず1つに絞る）

## 出力形式

必ず以下のJSON形式のみで出力してください。JSON以外のテキストは一切出力しないでください。

```json
{
  "type": "fire または water または electric または flying または grass または ice",
  "zukan": "ポケモン図鑑風の紹介文（空白区切りの文体で）",
  "reason": "タイプ判定理由（カジュアルなトーンで3〜5行）",
  "moves": [
    {"name": "技名1", "description": "一言説明1"},
    {"name": "技名2", "description": "一言説明2"},
    {"name": "技名3", "description": "一言説明3"}
  ],
  "creature_prompt": "このキャラクターの外見的特徴を英語で短く描写（例: has a fluffy tail with ember tips, wears a tiny scarf, has star-shaped markings on its cheeks）"
}
```

### creature_promptについて
- 対象者の性格やスキルから連想される外見的特徴を、英語で1〜2文で記述する
- 判定タイプに関連する装飾的な要素を含める（火タイプなら炎の模様や赤いアクセントなど）
- その人らしさが外見に現れるようにする（例：料理好き→シェフハットを被っている、音楽好き→音符模様がある）
- 具体的なアクセサリーやパーツで個性を出す"""


MOTIF_LABELS = {
    "cat": "ネコ", "dog": "イヌ", "fox": "キツネ", "rabbit": "ウサギ",
    "bear": "クマ", "bird": "トリ", "dragon": "ドラゴン", "wolf": "オオカミ",
    "lizard": "トカゲ", "fish": "サカナ", "butterfly": "チョウ", "snake": "ヘビ",
}


def build_user_message(data):
    """入力データからユーザーメッセージを構築する"""
    parts = [f"## 対象者\n名前：{data['name']}"]

    parts.append(f"\n## 性格・魅力\n{data['personality']}")

    if data.get("soft"):
        parts.append(f"\n## ソフトスキル\n{data['soft']}")
    if data.get("hard"):
        parts.append(f"\n## ハードスキル\n{data['hard']}")
    if data.get("hobby"):
        parts.append(f"\n## 趣味・好きなこと\n{data['hobby']}")
    if data.get("episode"):
        parts.append(f"\n## 印象的なエピソード\n{data['episode']}")

    if data.get("motifs"):
        motif_names = [MOTIF_LABELS.get(m, m) for m in data["motifs"]]
        parts.append(f"\n## キャラクターイメージ（選択されたモチーフ）\n{'・'.join(motif_names)}")

    parts.append("\n上記の情報をもとに、タイプ判定を行い、JSON形式で出力してください。creature_promptには、選択されたモチーフの生き物をベースに、この人の個性が外見に反映されたクリーチャーの特徴を英語で記述してください。")
    return "\n".join(parts)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "type-diagnosis.html")


@app.route("/api/diagnose", methods=["POST"])
def diagnose():
    data = request.get_json()

    if not data or not data.get("name") or not data.get("personality"):
        return json_response({"error": "名前と性格・魅力は必須です"}, 400)

    user_message = build_user_message(data)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        # レスポンステキストからJSONを抽出
        text = response.choices[0].message.content.strip()

        # ```json ... ``` で囲まれている場合に対応
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)

        # バリデーション
        valid_types = ["fire", "water", "electric", "flying", "grass", "ice"]
        if result.get("type") not in valid_types:
            result["type"] = "fire"

        if not result.get("moves") or len(result["moves"]) < 3:
            return json_response({"error": "生成結果が不完全です。もう一度お試しください。"}, 500)

        return json_response(result)

    except json.JSONDecodeError:
        return json_response({"error": "AIの応答を解析できませんでした。もう一度お試しください。"}, 500)
    except Exception as e:
        import traceback
        with open(os.path.join(BASE_DIR, "error.log"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        return json_response({"error": f"エラーが発生しました: {str(e)}"}, 500)


# モチーフの英語→日本語マッピング（プロンプト生成用）
MOTIF_MAP = {
    "cat": "cat",
    "dog": "dog",
    "fox": "fox",
    "rabbit": "rabbit",
    "bear": "bear",
    "bird": "bird",
    "dragon": "dragon",
    "wolf": "wolf",
    "lizard": "lizard",
    "fish": "fish",
    "butterfly": "butterfly",
    "snake": "snake",
}

# タイプごとの色パレットとキーワード
TYPE_VISUAL = {
    "fire": {"colors": "warm red and orange", "element": "fire, flames, ember glow"},
    "water": {"colors": "blue and aqua", "element": "water, bubbles, ocean waves"},
    "electric": {"colors": "yellow and gold", "element": "lightning, electric sparks, thunderbolt"},
    "flying": {"colors": "purple and lavender", "element": "wind, feathers, clouds"},
    "grass": {"colors": "green and leaf-green", "element": "leaves, vines, nature"},
    "ice": {"colors": "cyan and icy blue", "element": "ice crystals, frost, snowflakes"},
}

# バイブ（オノマトペ）→ ビジュアルスタイルへのマッピング
# ゆるかわ系: ふわふわ, にこにこ, ぽかぽか
# 元気キュート系: てきぱき, きらきら, わくわく
# かっこいい系: きりっ, しゅっ, めらめら
VIBE_STYLE = {
    "fuwafuwa": "soft_cute",
    "nikoniko": "soft_cute",
    "pokapoka": "soft_cute",
    "tekipaki": "energetic_cute",
    "kirakira": "energetic_cute",
    "wakuwaku": "energetic_cute",
    "kiri": "cool",
    "shu": "cool",
    "meramera": "cool",
}

# スタイルカテゴリ → DALL-Eプロンプト用のビジュアル指示
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
    """選択されたバイブからビジュアルスタイルを決定する"""
    if not vibes:
        return STYLE_PROMPTS["energetic_cute"]  # デフォルト

    # 各バイブのカテゴリをカウント
    category_counts = {}
    for v in vibes:
        cat = VIBE_STYLE.get(v, "energetic_cute")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 最多カテゴリを採用（同数ならmixed処理）
    sorted_cats = sorted(category_counts.items(), key=lambda x: -x[1])

    if len(sorted_cats) == 1 or sorted_cats[0][1] > sorted_cats[1][1]:
        return STYLE_PROMPTS[sorted_cats[0][0]]

    # 2カテゴリが同数（1つずつ選んだ場合）→ ブレンド
    cat_a, cat_b = sorted_cats[0][0], sorted_cats[1][0]
    a, b = STYLE_PROMPTS[cat_a], STYLE_PROMPTS[cat_b]
    return {
        "tone": f"{a['tone'].rstrip(',')} yet {b['tone'].lower().lstrip('a ')}",
        "design": f"{a['design']}, blended with {b['design']}",
    }


def build_image_prompt(type_key, motifs, vibes=None, creature_prompt=None):
    """モチーフ・バイブ・タイプからDALL-E用の画像生成プロンプトを構築する"""
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


@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    """DALL-Eを使ってポケモン風キャラクター画像を生成する"""
    data = request.get_json()

    if not data or not data.get("type") or not data.get("motifs"):
        return json_response({"error": "タイプとモチーフが必要です"}, 400)

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

        # base64画像をファイルに保存
        image_data = response.data[0].b64_json
        filename = f"creature_{uuid.uuid4().hex[:12]}.png"
        filepath = os.path.join(BASE_DIR, "generated", filename)

        os.makedirs(os.path.join(BASE_DIR, "generated"), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(image_data))

        return json_response({"image_url": f"/generated/{filename}"})

    except Exception as e:
        import traceback
        with open(os.path.join(BASE_DIR, "error.log"), "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        return json_response({"error": f"画像生成エラー: {str(e)}"}, 500)


if __name__ == "__main__":
    if not api_key:
        print("\n⚠️  APIキーが設定されていません。")
        print("以下のいずれかの方法で設定してください：")
        print("  1. api_key.txt ファイルにOpenAIのAPIキーを貼り付ける")
        print("  2. export OPENAI_API_KEY='sk-...'")
        print()
        exit(1)

    print("\n🔥💧⚡🕊️🌿❄️")
    print("HUMAN TYPE SCANNER - Server Started")
    print("http://localhost:8080 をブラウザで開いてください")
    print("終了: Ctrl+C\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
