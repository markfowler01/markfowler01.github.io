"""Build the GM steering column inspection training video (1920x1080 MP4 + SRT captions).

Needs: ffmpeg, Pillow, piper-tts (`pip install piper-tts`) and a Piper voice model.
Usage:  python3 build_video.py --voice /path/to/en-us-lessac-medium.onnx
"""
import argparse, os, subprocess, sys, tempfile, wave
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from script import SLIDES, FOOTER, CAPTION_FIXES  # noqa: E402

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


def render_slide(i, s, path, shown=None):
    """shown = how many bullets (or 1 = the image) are visible; None = everything."""
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
    tsz = 60 if s.get("image") else 78
    for line in s["title"].split("\n"):
        for wl in wrap(d, line, font(tsz, 800), W - x - 300):
            d.text((x, y), wl, font=font(tsz, 800), fill=WHITE)
            y += int(tsz * 1.23)
    if s.get("image") and shown == 0:
        s = dict(s, bullets=[])
    elif s.get("image"):
        shot = Image.open(os.path.join(HERE, "screens", s["image"])).convert("RGB")
        box_w, box_h = W - x - 90, H - y - 10 - 110
        shot.thumbnail((box_w, box_h), Image.LANCZOS)
        if shot.width < box_w and shot.height < box_h:  # upscale small shots to fill
            r = min(box_w / shot.width, box_h / shot.height)
            shot = shot.resize((int(shot.width * r), int(shot.height * r)), Image.LANCZOS)
        sx, sy = x + (box_w - shot.width) // 2, y + 10
        d.rectangle([sx - 6, sy - 6, sx + shot.width + 5, sy + shot.height + 5], fill=ORANGE)
        im.paste(shot, (sx, sy))
        s = dict(s, bullets=[])
    y += 40
    bf = font(44, 500)
    for b in (s["bullets"] if shown is None else s["bullets"][:shown]):
        lines = wrap(d, b, bf, W - x - 200)
        d.rectangle([x, y + 22, x + 14, y + 36], fill=ORANGE)
        for ln in lines:
            d.text((x + 44, y), ln, font=bf, fill=WHITE)
            y += 60
        y += 22
    d.text((x, H - 70), FOOTER,
           font=font(24, 400), fill=GRAY)
    d.text((W - 200, H - 70), f"{i + 1} / {n}", font=font(24, 600), fill=GRAY)
    im.save(path)


def tts(text, voice, out):
    subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", out, "--length-scale", "1.05"],
                   input=text.encode(), check=True, capture_output=True)
    with wave.open(out) as w:
        return w.getnframes() / w.getframerate(), w.getframerate()


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
    ap.add_argument("--out", default=os.path.join(HERE, "gm-steering-column-inspection-training.mp4"))
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    segs, srt, clock, k = [], [], 0.0, 1
    for i, s in enumerate(SLIDES):
        png = os.path.join(tmp, f"s{i:02}.png")
        render_slide(i, s, png)
        if i == 0:
            import shutil; shutil.copy(png, os.path.join(HERE, "thumbnail.png"))
        # narration: one wav per sentence, joined with silence
        pad0 = 2.2 if i == 0 else PAD_START  # let the music open the video
        parts, t, starts = [], pad0, []
        for j, sent in enumerate(s["narration"]):
            wav = os.path.join(tmp, f"s{i:02}_{j:02}.wav")
            dur, sr = tts(sent, a.voice, wav)
            parts.append(wav)
            starts.append(t)
            srt.append(f"{k}\n{ts(clock + t)} --> {ts(clock + t + dur)}\n{caption(sent)}\n")
            k += 1
            t += dur + GAP
        total = t - GAP + (3.0 if i == len(SLIDES) - 1 else PAD_END)
        lst = os.path.join(tmp, f"s{i:02}.txt")
        with open(lst, "w") as f:
            f.write("\n".join(f"file '{p}'" for p in parts))
        # concat sentences with gaps via adelay-free approach: apad each then concat filter
        inputs, filt = [], []
        for j, p in enumerate(parts):
            inputs += ["-i", p]
            filt.append(f"[{j}:a]apad=pad_dur={GAP}[a{j}]")
        cat = "".join(f"[a{j}]" for j in range(len(parts)))
        filt.append(f"{cat}concat=n={len(parts)}:v=0:a=1,adelay={int(pad0*1000)}:all=1,apad=whole_dur={total}[out]")
        audio = os.path.join(tmp, f"s{i:02}.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                        "-map", "[out]", "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "128k", audio], check=True)
        seg = os.path.join(tmp, f"s{i:02}.mp4")
        # animated build: title first, then each bullet (or the image) fades in as it is talked about
        nb = 1 if s.get("image") else len(s["bullets"])
        ns = len(starts)
        times = []
        for b in range(nb):
            tb = starts[min(ns - 1, (b * ns) // nb)] if nb > 1 else starts[0] + 0.3
            times.append(max(tb, (times[-1] + 0.6) if times else 0.5))
        vin, vf = ["-loop", "1", "-framerate", "30", "-t", f"{total:.3f}", "-i", os.path.join(tmp, f"s{i:02}_b0.png")], []
        render_slide(i, s, os.path.join(tmp, f"s{i:02}_b0.png"), shown=0)
        last = "0:v"
        for b in range(nb):
            pb = os.path.join(tmp, f"s{i:02}_b{b + 1}.png")
            render_slide(i, s, pb, shown=b + 1)
            vin += ["-loop", "1", "-framerate", "30", "-t", f"{total:.3f}", "-i", pb]
            vf.append(f"[{b + 1}:v]format=rgba,fade=t=in:st={times[b]:.2f}:d=0.45:alpha=1[f{b}]")
            vf.append(f"[{last}][f{b}]overlay=shortest=1[o{b}]")
            last = f"o{b}"
        vf.append(f"[{last}]fade=t=in:st=0:d=0.35,fade=t=out:st={total - 0.35:.2f}:d=0.35,format=yuv420p[v]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *vin, "-i", audio, "-filter_complex", ";".join(vf),
                        "-map", "[v]", "-map", f"{nb + 1}:a", "-t", f"{total:.3f}", "-r", "30", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "20", "-c:a", "copy", seg], check=True)
        segs.append(seg)
        clock += total
        print(f"slide {i + 1}/{len(SLIDES)}  {total:5.1f}s")
    srt_path = os.path.join(HERE, "gm-steering-column-inspection-training.srt")
    with open(srt_path, "w") as f:
        f.write("\n".join(srt))
    lst = os.path.join(tmp, "all.txt")
    with open(lst, "w") as f:
        f.write("\n".join(f"file '{p}'" for p in segs))
    # voice-only cut, then lay the music bed under it (ducked while the narrator talks)
    voice_cut = os.path.join(tmp, "voice.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", voice_cut], check=True)
    mix = (f"[1:a]volume=0.9,afade=t=in:st=0:d=0.6,afade=t=out:st={clock - 3:.2f}:d=3[m];"
           "[0:a]asplit[v1][v2];[m][v1]sidechaincompress=threshold=0.02:ratio=10:attack=30:release=700[md];"
           "[v2][md]amix=inputs=2:normalize=0:duration=first[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice_cut, "-stream_loop", "-1", "-i",
                    os.path.join(HERE, "music-bed.m4a"), "-i", srt_path, "-filter_complex", mix,
                    "-map", "0:v", "-map", "[a]", "-map", "2", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-t", f"{clock:.2f}",
                    "-movflags", "+faststart", a.out], check=True)
    print(f"done: {a.out}  ({clock / 60:.1f} min)")


if __name__ == "__main__":
    main()
