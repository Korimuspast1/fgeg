#!/usr/bin/env python3
"""
drum_slicer.py — анализ трека и нарезка drum one-shot'ов.

Пайплайн:
 1. загрузка аудио (локальный файл из репозитория);
 2. изоляция ударных: HPSS (гармоника/перкуссия) через librosa;
 3. детект транзиентов (onset detection) по перкуссивному слою;
 4. классификация каждого хита на kick / snare / hat по спектральным признакам
    (спектральный центроид, доля низкочастотной энергии, zero-crossing rate);
 5. нарезка one-shot'ов с фейдами, нормализация, экспорт в WAV;
 6. упаковка в ZIP + отчёт analysis_report.json.

Использование:
    python drum_slicer.py mytrack.mp3 -o oneshots
"""
import argparse
import json
import os
import zipfile

import numpy as np
import librosa
import soundfile as sf


def load_audio(path, sr=44100):
    y, sr = librosa.load(path, sr=sr, mono=True)
    return y, sr


def isolate_drums(y, margin=2.0):
    """HPSS: оставляем перкуссивную составляющую."""
    y_harm, y_perc = librosa.effects.hpss(y, margin=(1.0, margin))
    return y_perc


def detect_transients(y_perc, sr):
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr, aggregate=np.median)
    frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, backtrack=True,
        pre_max=20, post_max=20, pre_avg=100, post_avg=100, delta=0.15, wait=10,
    )
    return librosa.frames_to_samples(frames), onset_env


def band_energy(seg, sr, lo, hi):
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    m = (freqs >= lo) & (freqs < hi)
    return float(np.sum(S[m] ** 2))


def features(seg, sr):
    total = band_energy(seg, sr, 20, sr / 2) + 1e-12
    low = band_energy(seg, sr, 20, 150) / total
    mid = band_energy(seg, sr, 150, 2000) / total
    high = band_energy(seg, sr, 5000, sr / 2) / total
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=seg, sr=sr)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(seg)))
    return dict(low=low, mid=mid, high=high, centroid=centroid, zcr=zcr)


def classify_all(feats_list):
    """Адаптивная классификация: пороги берём из статистики самого трека,
    чтобы не зависеть от сведения/мастеринга конкретного материала."""
    if not feats_list:
        return []
    cen = np.array([f["centroid"] for f in feats_list])
    low = np.array([f["low"] for f in feats_list])
    high = np.array([f["high"] for f in feats_list])
    c_lo, c_hi = np.percentile(cen, 30), np.percentile(cen, 70)
    low_med = np.median(low)
    high_hi = np.percentile(high, 70)

    labels = []
    for f in feats_list:
        if f["centroid"] <= c_lo and f["low"] >= low_med:
            labels.append("kick")
        elif f["centroid"] >= c_hi or f["high"] >= high_hi:
            labels.append("hat")
        elif f["mid"] > 0.25:
            labels.append("snare")
        else:
            labels.append("perc")
    return labels


def envelope(seg, sr, fade_in_ms=2.0, fade_out_ms=25.0):
    seg = seg.copy()
    fi = max(1, int(sr * fade_in_ms / 1000))
    fo = max(1, int(sr * fade_out_ms / 1000))
    fi = min(fi, len(seg) // 2)
    fo = min(fo, len(seg) // 2)
    seg[:fi] *= np.linspace(0, 1, fi)
    seg[-fo:] *= np.linspace(1, 0, fo)
    peak = np.max(np.abs(seg)) + 1e-12
    return (seg / peak) * 0.89  # нормализация ~ -1 dBFS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default="oneshots")
    ap.add_argument("--sr", type=int, default=44100)
    ap.add_argument("--len-ms", type=float, default=400, help="макс. длина ваншота")
    ap.add_argument("--max-per-class", type=int, default=24)
    args = ap.parse_args()

    print(f"[1/6] Загрузка {args.input} ...")
    y, sr = load_audio(args.input, args.sr)
    print(f"      длительность: {len(y)/sr:.1f} c, sr={sr}")

    print("[2/6] Изоляция ударных (HPSS) ...")
    y_perc = isolate_drums(y)

    print("[3/6] Детект транзиентов ...")
    onsets, _ = detect_transients(y_perc, sr)
    tempo, beats = librosa.beat.beat_track(y=y_perc, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    print(f"      найдено транзиентов: {len(onsets)}, темп ~{tempo:.1f} BPM")

    print("[4/6] Классификация и нарезка ...")
    os.makedirs(args.outdir, exist_ok=True)
    maxlen = int(sr * args.len_ms / 1000)

    segs = []
    for i, start in enumerate(onsets):
        end = min(len(y_perc), start + maxlen)
        if i + 1 < len(onsets):
            end = min(end, onsets[i + 1] + int(0.02 * sr))
        seg = y_perc[start:end]
        if len(seg) < int(0.02 * sr) or np.max(np.abs(seg)) < 1e-4:
            continue
        segs.append((start, seg, features(seg, sr)))

    labels = classify_all([f for _, _, f in segs])
    counters, report = {}, []
    for (start, seg, feats), label in zip(segs, labels):
        n = counters.get(label, 0)
        if n >= args.max_per_class:
            continue
        counters[label] = n + 1
        d = os.path.join(args.outdir, label)
        os.makedirs(d, exist_ok=True)
        name = f"{label}_{n+1:02d}.wav"
        sf.write(os.path.join(d, name), envelope(seg, sr), sr, subtype="PCM_24")
        report.append(dict(file=f"{label}/{name}", t_sec=round(start / sr, 3),
                           len_ms=round(len(seg) / sr * 1000, 1), label=label,
                           **{k: round(v, 4) for k, v in feats.items()}))

    print("      " + ", ".join(f"{k}: {v}" for k, v in sorted(counters.items())))

    print("[5/6] Отчёт ...")
    meta = dict(source=os.path.basename(args.input), sample_rate=sr,
                duration_sec=round(len(y) / sr, 2), tempo_bpm=round(tempo, 2),
                transients=int(len(onsets)), counts=counters, slices=report)
    with open(os.path.join(args.outdir, "analysis_report.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("[6/6] Упаковка в ZIP ...")
    zip_path = args.outdir.rstrip("/") + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(args.outdir):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, args.outdir))
    print(f"Готово: {zip_path} ({os.path.getsize(zip_path)/1e6:.2f} МБ)")


if __name__ == "__main__":
    main()
