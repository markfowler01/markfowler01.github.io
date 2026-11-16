"""Build the WA DOR quarterly tax training video (1920x1080 MP4 + SRT captions).

Needs: ffmpeg, Pillow, piper-tts (`pip install piper-tts`) and a Piper voice model.
Usage:  python3 build_video.py --voice /path/to/en-us-lessac-medium.onnx
"""
import argparse, os, subprocess, sys, tempfile, wave
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from script import SLIDES  # noqa: E402

W, H = 1920, 1080
BLACK, ORANGE, WHITE, GRAY = (10, 10, 10), (205, 68, 25), (255, 255, 255), (170, 170, 170)
FONT = os.path.join(ROOT, "garage-tv", "fonts", "Montserrat.ttf")
LOGO = os.path.join(ROOT, "logo.png")
PAD_START, PAD_END, GAP = 0.6, 1.0, 0.35  # seconds


def font(size, weight=400):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def render_slide(i, s, path):
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)
    # left accent bar + progress
    d.rectangle([0, 0, 18, H], fill=ORANGE)
    n = len(SLIDES)
    d.rectangle([0, H - 10, W, H], fill=(40, 40, 40))
    d.rectangle([0, H - 10, int(W * (i + 1) / n), H], fill=ORANGE)
    # logo
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((150, 150))
    im.paste(logo, (W - 150 - 70, 60), logo)
    x = 130
    d.text((x, 110), s["kicker"], font=font(34, 700), fill=ORANGE)
    y = 165
    for line in s["title"].split("\n"):
        for wl in wrap(d, line, font(78, 800), W - x - 300):
            d.text((x, y), wl, font=font(78, 800), fill=WHITE)
            y += 96
    y += 40
    bf = font(44, 500)
    for b in s["bullets"]:
        lines = wrap(d, b, bf, W - x - 200)
        d.rectangle([x, y + 22, x + 14, y + 36], fill=ORANGE)
        for ln in lines:
            d.text((x + 44, y), ln, font=bf, fill=WHITE)
            y += 60
        y += 22
    d.text((x, H - 70), "Absolute ADAS  ·  Internal training  ·  Not tax advice — confirm with the owner/CPA",
           font=font(24, 400), fill=GRAY)
    d.text((W - 200, H - 70), f"{i + 1} / {n}", font=font(24, 600), fill=GRAY)
    im.save(path)


def tts(text, voice, out):
    subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", out, "--length-scale", "1.05"],
                   input=text.encode(), check=True, capture_output=True)
    with wave.open(out) as w:
        return w.getnframes() / w.getframerate(), w.getframerate()


# Narration is written the way the voice should say it; captions show the normal spelling.
CAPTION_FIXES = [
    ("secure dot D O R dot W A dot gov", "secure.dor.wa.gov"),
    ("W A D O R", "WA DOR"), ("D O R", "DOR"), ("B and O", "B&O"), ("E S D", "ESD"), ("I R S", "IRS"),
    ("eleven fifty-nine p m", "11:59 p.m."), ("two point nine six percent", "2.96%"),
    ("point four seven one percent", "0.471%"), ("point five percent", "0.5%"),
    ("three six zero, seven zero five, six seven zero five", "360-705-6705"),
]


def caption(text):
    for a, b in CAPTION_FIXES:
        text = text.replace(a, b)
    return text


def ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "wa-dor-quarterly-taxes-training.mp4"))
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    segs, srt, clock, k = [], [], 0.0, 1
    for i, s in enumerate(SLIDES):
        png = os.path.join(tmp, f"s{i:02}.png")
        render_slide(i, s, png)
        if i == 0:
            import shutil; shutil.copy(png, os.path.join(HERE, "thumbnail.png"))
        # narration: one wav per sentence, joined with silence
        parts, t = [], PAD_START
        for j, sent in enumerate(s["narration"]):
            wav = os.path.join(tmp, f"s{i:02}_{j:02}.wav")
            dur, sr = tts(sent, a.voice, wav)
            parts.append(wav)
            srt.append(f"{k}\n{ts(clock + t)} --> {ts(clock + t + dur)}\n{caption(sent)}\n")
            k += 1
            t += dur + GAP
        total = t - GAP + PAD_END
        lst = os.path.join(tmp, f"s{i:02}.txt")
        with open(lst, "w") as f:
            f.write("\n".join(f"file '{p}'" for p in parts))
        # concat sentences with gaps via adelay-free approach: apad each then concat filter
        inputs, filt = [], []
        for j, p in enumerate(parts):
            inputs += ["-i", p]
            filt.append(f"[{j}:a]apad=pad_dur={GAP}[a{j}]")
        cat = "".join(f"[a{j}]" for j in range(len(parts)))
        filt.append(f"{cat}concat=n={len(parts)}:v=0:a=1,adelay={int(PAD_START*1000)}:all=1,apad=whole_dur={total}[out]")
        audio = os.path.join(tmp, f"s{i:02}.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                        "-map", "[out]", "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "128k", audio], check=True)
        seg = os.path.join(tmp, f"s{i:02}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", png, "-i", audio,
                        "-t", f"{total:.3f}", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-shortest", seg], check=True)
        segs.append(seg)
        clock += total
        print(f"slide {i + 1}/{len(SLIDES)}  {total:5.1f}s")
    srt_path = os.path.join(HERE, "wa-dor-quarterly-taxes-training.srt")
    with open(srt_path, "w") as f:
        f.write("\n".join(srt))
    lst = os.path.join(tmp, "all.txt")
    with open(lst, "w") as f:
        f.write("\n".join(f"file '{p}'" for p in segs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", srt_path,
                    "-map", "0", "-map", "1", "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
                    "-movflags", "+faststart", a.out], check=True)
    print(f"done: {a.out}  ({clock / 60:.1f} min)")


if __name__ == "__main__":
    main()
