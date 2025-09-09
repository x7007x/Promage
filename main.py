import os
import json
import uuid
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, abort
import redis


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

REDIS_URL = "redis://default:axuRTYfEF9YyrxaGFcbFqv5x8GeRujl2@redis-19857.c62.us-east-1-4.ec2.redns.redis-cloud.com:19857"
r = redis.from_url(REDIS_URL, decode_responses=True)

SITE = {
    "name": "Promage",
    "base_url": os.environ.get("BASE_URL", "http://localhost:5000"),
    "default_og_image": "https://files.catbox.moe/lqdkks.jpg",
}
DEFAULT_IMAGES = [
    {
        "id": "future-city",
        "title": "Future City",
        "src": "https://files.catbox.moe/lqdkks.jpg",
        "alt": "Futuristic neon cityscape at dusk with reflective wet streets",
        "prompt": "Cinematic cyberpunk skyline at dusk, neon holograms, volumetric fog, reflective wet streets, dense high-rises, flying cars light trails, ultra-detailed, global illumination, ray-traced reflections, octane render, photorealistic, 8k, high contrast, teal-magenta palette",
        "negative": "low-res, artifacts, oversharpen, banding, blown highlights, deformed geometry, duplicated buildings, text watermark",
    },
    {
        "id": "ethereal-portrait",
        "title": "Ethereal Portrait",
        "src": "https://files.catbox.moe/wfnud7.jpg",
        "alt": "Ethereal portrait with soft lighting and pastel tones",
        "prompt": "Hyperreal portrait, soft diffused key light, pastel holographic makeup, porcelain skin, shallow depth of field, creamy bokeh, rim light, 35mm lens, f/1.8, subtle film grain, serene expression, color grading in airy pastels, studio backdrop",
        "negative": "harsh shadows, plastic skin, oversmoothing, extra fingers, misaligned eyes, jpeg artifacts, watermark",
    },
]


def ensure_session():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]

def image_key(image_id):
    return f"image:{image_id}"

def seed_defaults():
    if r.exists("images:seeded"):
        return

    now = int(time.time())
    pipe = r.pipeline()

    for i, item in enumerate(DEFAULT_IMAGES):
        key = image_key(item["id"])

        if not r.exists(key):
            pipe.hset(
                key,
                mapping={
                    "id": item["id"],
                    "title": item["title"],
                    "src": item["src"],
                    "alt": item["alt"],
                    "prompt": item["prompt"],
                    "negative": item["negative"],
                    "likes": 0,
                    "views": 0,
                    "created_at": now - (len(DEFAULT_IMAGES) - i),
                },
            )

        pipe.zadd("images:trending", {item["id"]: now - (len(DEFAULT_IMAGES) - i)})

    pipe.set("images:seeded", 1)
    pipe.execute()

def get_image(image_id):
    data = r.hgetall(image_key(image_id))

    if not data:
        return None

    data["likes"] = int(data.get("likes", 0))
    data["views"] = int(data.get("views", 0))

    return data

def get_trending(limit=100):
    ids = r.zrevrange("images:trending", 0, limit - 1)
    items = []

    for image_id in ids:
        item = get_image(image_id)
        if item:
            items.append(item)

    return items

def log_activity(kind, detail):
    payload = {
        "ts": int(time.time()),
        "kind": kind,
        "detail": detail,
    }
    r.lpush("activities", json.dumps(payload))
    r.ltrim("activities", 0, 499)

def admin_claimed_sid():
    return r.get("admin:sid")

def is_admin():
    sid = session.get("sid")
    claimed = admin_claimed_sid()
    return sid and claimed and sid == claimed

@app.before_request
def setup():
    ensure_session()
    seed_defaults()

@app.route("/")
def index():
    items = get_trending()

    sid = ensure_session()
    liked_set_key = f"likes:session:{sid}"
    liked_ids = set(r.smembers(liked_set_key))

    meta = {
        "title": f"{SITE['name']}",
        "description": "Browse AI images, reveal the exact prompts behind each piece, and reuse them in your favorite generative tools.",
        "url": f"{SITE['base_url']}/",
        "image": SITE["default_og_image"],
    }

    special_thanks_list = [
        {"name": "Ahmed Negm", "image": "https://a7med.pages.dev/img/ai-2937.png"},
        {"name": "Ahmed Negm", "image": "https://a7med.pages.dev/img/ai-2937.png"},
        {"name": "Ahmed Negm", "image": "https://a7med.pages.dev/img/ai-2937.png"},
        {"name": "Ahmed Negm", "image": "https://a7med.pages.dev/img/ai-2937.png"},
        {"name": "Ahmed Negm", "image": "https://a7med.pages.dev/img/ai-2937.png"},
    ]

    return render_template("index.html", site=SITE, items=items, liked_ids=liked_ids, meta=meta, special_thanks_list=special_thanks_list)

@app.route("/prompt")
def prompt():
    image_id = request.args.get("id")

    if not image_id:
        return redirect(url_for("index"))

    item = get_image(image_id)

    if not item:
        abort(404)

    sid = ensure_session()

    viewed_key = f"views:session:{sid}"
    if r.sadd(viewed_key, image_id) == 1:
        r.hincrby(image_key(image_id), "views", 1)
        r.incr(f"image:{image_id}:views")
        r.zincrby("images:views", 1, image_id)
        log_activity("view", {"image_id": image_id, "sid": sid})

    liked_set_key = f"likes:session:{sid}"
    liked = r.sismember(liked_set_key, image_id)

    item = get_image(image_id)

    meta = {
        "title": f"{item['title']} — Prompt · {SITE['name']}",
        "description": f"View and copy the exact text prompt used to generate {item['title']}.",
        "url": f"{SITE['base_url']}/prompt?id={image_id}",
        "image": item["src"],
    }

    return render_template("prompt.html", site=SITE, item=item, liked=liked, meta=meta)

@app.route("/api/like", methods=["POST"])
def api_like():
    data = request.get_json(silent=True) or {}
    image_id = data.get("id")

    if not image_id or not get_image(image_id):
        return jsonify({"ok": False, "error": "invalid_id"}), 200

    sid = ensure_session()
    liked_set_key = f"likes:session:{sid}"

    if r.sismember(liked_set_key, image_id):
        item = get_image(image_id)
        return jsonify({"ok": False, "error": "already_liked", "likes": item["likes"]}), 200

    r.sadd(liked_set_key, image_id)
    r.hincrby(image_key(image_id), "likes", 1)
    r.incr(f"image:{image_id}:likes")
    r.zincrby("images:likes", 1, image_id)
    log_activity("like", {"image_id": image_id, "sid": sid})

    item = get_image(image_id)
    return jsonify({"ok": True, "liked": True, "likes": item["likes"]}), 200

@app.route("/api/stats/<image_id>")
def api_stats(image_id):
    item = get_image(image_id)

    if not item:
        return jsonify({"ok": False}), 404

    return jsonify({"ok": True, "likes": item["likes"], "views": item["views"]})

@app.route("/admin", methods=["GET"])
def admin():
    sid = ensure_session()
    claimed = admin_claimed_sid()

    state = "unclaimed"
    if claimed:
        if claimed == sid:
            state = "mine"
        else:
            state = "taken"

    items = get_trending()
    activities = [json.loads(x) for x in r.lrange("activities", 0, 49)]

    return render_template("admin.html", site=SITE, state=state, items=items, activities=activities)

@app.route("/admin/claim", methods=["POST"])
def admin_claim():
    sid = ensure_session()
    claimed = admin_claimed_sid()

    if claimed and claimed != sid:
        abort(403)

    r.set("admin:sid", sid)
    log_activity("admin_claim", {"sid": sid})

    return redirect(url_for("admin"))

@app.route("/admin/release", methods=["POST"])
def admin_release():
    if not is_admin():
        abort(403)

    r.delete("admin:sid")
    log_activity("admin_release", {})

    return redirect(url_for("admin"))

@app.route("/admin/add", methods=["POST"])
def admin_add():
    if not is_admin():
        abort(403)

    image_id = request.form.get("id", "").strip()
    title = request.form.get("title", "").strip()
    src = request.form.get("src", "").strip()
    alt = request.form.get("alt", "").strip()
    prompt_text = request.form.get("prompt", "").strip()
    negative = request.form.get("negative", "").strip()

    if not image_id or not title or not src:
        abort(400)

    key = image_key(image_id)
    now = int(time.time())

    r.hset(
        key,
        mapping={
            "id": image_id,
            "title": title,
            "src": src,
            "alt": alt,
            "prompt": prompt_text,
            "negative": negative,
            "likes": 0,
            "views": 0,
            "created_at": now,
        },
    )
    r.zadd("images:trending", {image_id: now})

    log_activity("admin_add", {"id": image_id})

    return redirect(url_for("admin"))

@app.route("/admin/update", methods=["POST"])
def admin_update():
    if not is_admin():
        abort(403)

    image_id = request.form.get("id", "").strip()

    if not image_id or not r.exists(image_key(image_id)):
        abort(400)

    fields = {}

    for f in ["title", "src", "alt", "prompt", "negative"]:
        val = request.form.get(f)
        if val is not None:
            fields[f] = val.strip()

    if fields:
        r.hset(image_key(image_id), mapping=fields)
        log_activity("admin_update", {"id": image_id, "fields": list(fields.keys())})

    return redirect(url_for("admin"))

@app.route("/admin/delete", methods=["POST"])
def admin_delete():
    if not is_admin():
        abort(403)

    image_id = request.form.get("id", "").strip()

    if not image_id:
        abort(400)

    r.delete(image_key(image_id))
    r.zrem("images:trending", image_id)
    r.zrem("images:likes", image_id)
    r.zrem("images:views", image_id)
    r.delete(f"image:{image_id}:likes")
    r.delete(f"image:{image_id}:views")

    log_activity("admin_delete", {"id": image_id})

    return redirect(url_for("admin"))

@app.route("/admin/reorder", methods=["POST"])
def admin_reorder():
    if not is_admin():
        abort(403)

    order_text = request.form.get("order", "")
    order = [x.strip() for x in order_text.split(",") if x.strip()]

    now = int(time.time())
    pipe = r.pipeline()

    for i, image_id in enumerate(order):
        score = now - (len(order) - i)
        pipe.zadd("images:trending", {image_id: score})

    pipe.execute()

    log_activity("admin_reorder", {"count": len(order)})

    return redirect(url_for("admin"))

@app.errorhandler(404)
def page_not_found(e):
    meta = {
        "title": f"404 Not Found - {SITE['name']}",
        "description": "The page you are looking for could not be found.",
        "url": f"{SITE['base_url']}/404",
        "image": SITE["default_og_image"],
    }
    return render_template("404.html", site=SITE, meta=meta), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)