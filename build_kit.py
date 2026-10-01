#!/usr/bin/env python3
"""
build_kit.py — сборка готового драм-кита из собственного трека.

Отличие от drum_slicer.py: тот нарезает ВСЁ подряд, а этот отбирает лучшие
экземпляры каждого класса и упаковывает их как playable-кит:

  Kit/
    Kick/   Snare/   HatClosed/   HatOpen/   Perc/
    Loops/  (один такт перкуссии в темпе трека)
    MyTrack_Kit.sfz   — маппинг на MIDI-ноты (GM-совместимый)
    README.txt

Критерии отбора ваншота:
  * «чистота хвоста» — до следующего транзиента должно быть достаточно места;
  * пик и уровень атаки;
  * непохожесть на уже отобранные (MFCC-дистанция), чтобы в ките не было
    24 одинаковых копии одного и того же удара.
"""
import argparse
import json
import os
import shutil
import zipfile

import numpy as np
import librosa
import soundfile as sf

from drum_slicer import (load_audio, isolate_drums, detect_transients,
                         features, classify_all, envelope)

# целевые размеры секций кита и MIDI-ноты (General MIDI drum map)
KIT_PLAN = {
    "Kick":      dict(src="kick",  n=6, note=36, len_ms=600),
    "Snare":     dict(src="snare", n=6, note=38, len_ms=500),
    "HatClosed": dict(src="hat",   n=4, note=42, len_ms=160),
    "HatOpen":   dict(src="hat",   n=2, note=46, len_ms=450),
    "Perc":      dict(src="perc",  n=4, note=39, len_ms=400),
}


def quality(seg, sr, headroom_samples):
    """Оценка пригодности хита для кита."""
    peak = float(np.max(np.abs(seg)))
    if peak < 1e-4:
        return -1.0
    rms = float(np.sqrt(np.mean(seg ** 2)))
    attack = float(np.max(np.abs(seg[: int(0.01 * sr)])) / (peak + 1e-12))
    room = min(1.0, headroom_samples / (0.25 * sr))  # есть ли место под хвост
    crest = peak / (rms + 1e-12)
    return 0.4 * room + 0.3 * attack + 0.2 * min(crest / 8.0, 1.0) + 0.1 * peak


def timbre(seg, sr):
    m = librosa.feature.mfcc(y=seg, sr=sr, n_mfcc=13)
    return np.mean(m, axis=1)


def pick_diverse(cands, n, min_dist=18.0):
    """Жадный отбор: лучший по качеству + достаточно непохожий на выбранные."""
    chosen = []
    for c in sorted(cands, key=lambda x: -x["q"]):
        if len(chosen) >= n:
            break
        if all(np.linalg.norm(c["mfcc"] - o["mfcc"]) > min_dist for o in chosen):
            chosen.append(c)
    # добиваем лучшими из оставшихся, если уникальных не хватило
    if len(chosen) < n:
        for c in sorted(cands, key=lambda x: -x["q"]):
            if c not in chosen:
                chosen.append(c)
            if len(chosen) >= n:
                break
    return chosen


def write_sfz(path, mapping, kit_name):
    lines = [f"// {kit_name} — автособранный кит из собственного трека",
             "<control>", "default_path=", "", "<global> ampeg_release=0.3", ""]
    for note, files in sorted(mapping.items()):
        n = len(files)
        for i, f in enumerate(files):
            lo = int(round(1 + i * 126 / n))
            hi = int(round((i + 1) * 126 / n))
            lines += ["<region>", f"sample={f.replace('/', os.sep) if os.sep != '/' else f}",
                      f"key={note}", f"lovel={lo}", f"hivel={hi}", ""]
    open(path, "w").write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="mytrack.mp3")
    ap.add_argument("-o", "--outdir", default="MyTrack_DrumKit")
    ap.add_argument("--sr", type=int, default=44100)
    args = ap.parse_args()

    print(f"[1/5] Анализ {args.input} ...")
    y, sr = load_audio(args.input, args.sr)
    y_perc = isolate_drums(y)
    onsets, _ = detect_transients(y_perc, sr)
    tempo, _ = librosa.beat.beat_track(y=y_perc, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    print(f"      {len(y)/sr:.1f} c, {len(onsets)} транзиентов, ~{tempo:.1f} BPM")

    # признаки + классы
    segs = []
    for i, start in enumerate(onsets):
        nxt = onsets[i + 1] if i + 1 < len(onsets) else len(y_perc)
        raw = y_perc[start:min(len(y_perc), start + int(0.8 * sr))]
        if len(raw) < int(0.02 * sr) or np.max(np.abs(raw)) < 1e-4:
            continue
        segs.append(dict(start=int(start), head=int(nxt - start), raw=raw,
                         f=features(raw[: int(0.3 * sr)], sr)))
    labels = classify_all([s["f"] for s in segs])
    for s, l in zip(segs, labels):
        s["label"] = l
        s["q"] = quality(s["raw"], sr, s["head"])
        s["mfcc"] = timbre(s["raw"][: int(0.2 * sr)], sr)

    print("[2/5] Отбор лучших экземпляров ...")
    if os.path.isdir(args.outdir):
        shutil.rmtree(args.outdir)
    os.makedirs(args.outdir)

    manifest, mapping = [], {}
    hats_used = set()
    for folder, plan in KIT_PLAN.items():
        pool = [s for s in segs if s["label"] == plan["src"] and s["q"] > 0]
        if plan["src"] == "hat":
            # открытые хэты = длинный хвост, закрытые = короткий
            pool = sorted(pool, key=lambda s: -s["head"]) if folder == "HatOpen" \
                else sorted(pool, key=lambda s: s["head"])
            pool = [s for s in pool if s["start"] not in hats_used][: plan["n"] * 4]
        if not pool:
            continue
        picks = pick_diverse(pool, plan["n"])
        d = os.path.join(args.outdir, folder)
        os.makedirs(d, exist_ok=True)
        files = []
        for i, s in enumerate(picks, 1):
            hats_used.add(s["start"])
            L = min(len(s["raw"]), int(sr * plan["len_ms"] / 1000), max(s["head"], int(0.05 * sr)) + int(0.08 * sr))
            seg = envelope(s["raw"][:L], sr, fade_out_ms=min(40.0, plan["len_ms"] / 6))
            name = f"{folder}_{i:02d}.wav"
            sf.write(os.path.join(d, name), seg, sr, subtype="PCM_24")
            rel = f"{folder}/{name}"
            files.append(rel)
            manifest.append(dict(file=rel, midi_note=plan["note"],
                                 source_t_sec=round(s["start"] / sr, 3),
                                 len_ms=round(L / sr * 1000, 1),
                                 centroid_hz=round(s["f"]["centroid"], 1),
                                 score=round(s["q"], 3)))
        mapping[plan["note"]] = files
        print(f"      {folder}: {len(files)}")

    print("[3/5] Экспорт лупа ...")
    os.makedirs(os.path.join(args.outdir, "Loops"), exist_ok=True)
    bar = int(sr * 4 * 60.0 / tempo)
    # берём такт из самой «плотной» по энергии части перкуссии
    hop = int(0.25 * sr)
    best, best_e = 0, -1
    for st in range(0, max(1, len(y_perc) - bar), hop):
        e = float(np.sum(y_perc[st:st + bar] ** 2))
        if e > best_e:
            best_e, best = e, st
    # выравниваем начало на ближайший транзиент
    if len(onsets):
        best = int(onsets[np.argmin(np.abs(onsets - best))])
    loop = y_perc[best:best + bar]
    loop = envelope(loop, sr, fade_in_ms=3, fade_out_ms=6)
    loop_name = f"Loops/DrumLoop_1bar_{round(tempo)}bpm.wav"
    sf.write(os.path.join(args.outdir, loop_name), loop, sr, subtype="PCM_24")

    print("[4/5] SFZ-маппинг и документация ...")
    write_sfz(os.path.join(args.outdir, "MyTrack_Kit.sfz"), mapping, "MyTrack Kit")
    json.dump(dict(source=os.path.basename(args.input), tempo_bpm=round(tempo, 2),
                   sample_rate=sr, bit_depth=24, loop=loop_name, samples=manifest),
              open(os.path.join(args.outdir, "kit_manifest.json"), "w"),
              ensure_ascii=False, indent=2)

    readme = f"""MyTrack Drum Kit
================
Собран автоматически из собственного трека «{os.path.basename(args.input)}».

Темп источника : ~{tempo:.1f} BPM
Формат         : WAV 44.1 kHz / 24 bit, моно, нормализовано до -1 dBFS
Всего сэмплов  : {len(manifest)} + 1 луп

Структура
---------
Kick/  Snare/  HatClosed/  HatOpen/  Perc/   — ваншоты
Loops/                                       — один такт в темпе трека
MyTrack_Kit.sfz                              — маппинг для sfz-сэмплеров
kit_manifest.json                            — таймкоды и метрики каждого сэмпла

MIDI-раскладка (General MIDI)
-----------------------------
36 Kick | 38 Snare | 42 Hat Closed | 46 Hat Open | 39 Perc
Внутри каждой ноты сэмплы разложены по velocity-слоям.

Как загрузить
-------------
* sforzando / Sfizz / Plogue: открыть MyTrack_Kit.sfz.
* Battery, Kontakt, Ableton Drum Rack, FL Slicer: перетащить папки вручную.

Источник — собственная запись пользователя; сторонний материал не использовался.
"""
    open(os.path.join(args.outdir, "README.txt"), "w").write(readme)

    print("[5/5] Упаковка ...")
    zip_path = args.outdir + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(args.outdir):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                z.write(p, os.path.join(os.path.basename(args.outdir),
                                        os.path.relpath(p, args.outdir)))
    print(f"Готово: {zip_path} ({os.path.getsize(zip_path)/1e6:.2f} МБ)")


if __name__ == "__main__":
    main()
