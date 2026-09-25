#!/usr/bin/env python3
"""
Нарезает один длинный mp3 (сгенерированный в SpeechGen.io голосом Babek,
где фразы разделены паузами) на отдельные файлы audio/<key>.mp3,
в порядке, заданном poryadok.json.

Использование:
    python3 narezka.py --file combined.mp3 --party 1
    python3 narezka.py --file combined.mp3 --party 2 --pause 1.0
"""
import argparse
import json
import re
import subprocess
import sys
import os

def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True
    )
    return float(out.stdout.strip())

def detect_silence(path, min_pause, noise_db):
    out = subprocess.run(
        ["ffmpeg", "-i", path, "-af",
         f"silencedetect=noise={noise_db}dB:d={min_pause}", "-f", "null", "-"],
        capture_output=True, text=True
    )
    log = out.stderr
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", log)]
    return list(zip(starts, ends))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="объединённый mp3 из SpeechGen")
    ap.add_argument("--party", required=True, choices=["1", "2", "3"], help="какой список ключей из poryadok.json")
    ap.add_argument("--pause", type=float, default=0.5, help="минимальная пауза между фразами, сек")
    ap.add_argument("--noise", type=float, default=-38, help="порог тишины, dB")
    ap.add_argument("--pad", type=float, default=0.12, help="запас по краям сегмента, сек")
    ap.add_argument("--force", action="store_true", help="резать, даже если число сегментов не совпало")
    ap.add_argument("--poryadok", default="poryadok.json")
    ap.add_argument("--outdir", default="audio")
    args = ap.parse_args()

    with open(args.poryadok, encoding="utf-8") as f:
        order = json.load(f)[args.party]

    total = duration(args.file)
    silences = detect_silence(args.file, args.pause, args.noise)

    bounds = [0.0]
    for s, e in silences:
        bounds.append(s)
        bounds.append(e)
    bounds.append(total)

    segments = []
    for i in range(0, len(bounds) - 1, 2):
        start, end = bounds[i], bounds[i + 1]
        if end - start > 0.15:
            segments.append((max(0, start - args.pad), min(total, end + args.pad)))

    print(f"Найдено фрагментов: {len(segments)}, ожидается: {len(order)}")
    if len(segments) != len(order) and not args.force:
        print("Числа не совпадают — проверь --pause/--noise, либо запусти с --force.")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)
    n = min(len(segments), len(order))
    for i in range(n):
        start, end = segments[i]
        key = order[i]
        out_path = os.path.join(args.outdir, f"{key}.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", args.file,
             "-ss", str(start), "-to", str(end), "-c", "copy", out_path],
            check=True
        )
        print(f"  {key}.mp3  ({end-start:.2f}s)")

    print(f"Готово: {n} файлов в {args.outdir}/")

if __name__ == "__main__":
    main()
