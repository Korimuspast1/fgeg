#!/usr/bin/env python3
"""Generate AFTERLIGHT — an original 60-second instrumental at 108 BPM.

The arrangement follows only high-level traits measured from the reference audio:
tempo, broad tonal centre, dark spectral balance, stereo width, and energy arc.
It deliberately uses a newly written melody and no samples from the reference.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import (
    Chorus,
    Compressor,
    Delay,
    Gain,
    HighpassFilter,
    Limiter,
    LowShelfFilter,
    Pedalboard,
    Reverb,
)

SR = 44_100
BPM = 108.0
BEAT = 60.0 / BPM
BAR = 4.0 * BEAT
DURATION = 60.0
N = int(SR * DURATION)
RNG = np.random.default_rng(920241)


def midi_hz(note: float) -> float:
    return 440.0 * 2.0 ** ((note - 69.0) / 12.0)


def stereo_track() -> np.ndarray:
    return np.zeros((2, N), dtype=np.float32)


def equal_power_pan(pan: float) -> tuple[float, float]:
    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * math.pi / 4.0
    return math.cos(angle), math.sin(angle)


def add_mono(track: np.ndarray, signal: np.ndarray, start: float, pan: float = 0.0) -> None:
    a = max(0, int(round(start * SR)))
    if a >= N:
        return
    signal = signal[: N - a]
    left, right = equal_power_pan(pan)
    track[0, a : a + len(signal)] += signal * left
    track[1, a : a + len(signal)] += signal * right


def envelope(length: int, attack: float, release: float, sustain: float = 1.0) -> np.ndarray:
    env = np.full(length, sustain, dtype=np.float32)
    a = min(length, max(1, int(attack * SR)))
    r = min(length, max(1, int(release * SR)))
    env[:a] *= np.sin(np.linspace(0, math.pi / 2, a, dtype=np.float32)) ** 2
    env[-r:] *= np.cos(np.linspace(0, math.pi / 2, r, dtype=np.float32)) ** 2
    return env


def tone_signal(
    note: float,
    duration: float,
    amp: float,
    kind: str,
    attack: float = 0.01,
    release: float = 0.15,
) -> np.ndarray:
    length = max(1, int(duration * SR))
    t = np.arange(length, dtype=np.float64) / SR
    f = midi_hz(note)

    if kind == "bass":
        # Rounded sub with a faint upper harmonic for definition on small speakers.
        sig = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(2 * np.pi * 2 * f * t + 0.2)
        sig = np.tanh(1.35 * sig)
        env = envelope(length, attack, release) * np.exp(-0.12 * t)
    elif kind == "pluck":
        sig = np.zeros(length, dtype=np.float64)
        phases = (0.1, 1.7, 0.6, 2.2, 0.9)
        for harmonic, level, decay, phase in zip(
            (1, 2, 3, 4, 6), (1.0, 0.34, 0.20, 0.10, 0.045), (1.7, 2.8, 4.0, 5.4, 7.0), phases
        ):
            if harmonic * f < SR / 2:
                sig += level * np.sin(2 * np.pi * harmonic * f * t + phase) * np.exp(-decay * t)
        env = envelope(length, attack, release) * np.exp(-0.45 * t)
    elif kind == "lead":
        # Soft, vocal-like triangle timbre with a slow vibrato that enters after attack.
        vibrato = 0.012 * np.sin(2 * np.pi * 5.1 * t) * np.minimum(1.0, t / 0.24)
        phase = 2 * np.pi * np.cumsum(f * (1.0 + vibrato)) / SR
        sig = np.sin(phase)
        sig += 0.26 * np.sin(2 * phase + 0.5)
        sig += 0.10 * np.sin(3 * phase + 1.1)
        sig += 0.035 * np.sin(5 * phase + 0.2)
        env = envelope(length, attack, release) * (0.96 + 0.04 * np.sin(2 * np.pi * 0.6 * t))
    else:
        raise ValueError(kind)

    return (amp * sig * env).astype(np.float32)


def add_pad_note(track: np.ndarray, note: float, start: float, duration: float, amp: float, pan: float) -> None:
    a = int(round(start * SR))
    length = min(int(round(duration * SR)), N - a)
    if length <= 0:
        return
    t = np.arange(length, dtype=np.float64) / SR
    f = midi_hz(note)
    env = envelope(length, attack=min(0.55, duration * 0.22), release=min(0.8, duration * 0.30))
    # Independent micro-detuning on each side gives width without a copied mono centre.
    for channel, cents in ((0, -3.5 - 1.2 * pan), (1, 3.1 + 1.0 * pan)):
        detuned = f * 2 ** (cents / 1200)
        phase = 2 * np.pi * detuned * t + (0.45 if channel else 0.0)
        sig = np.zeros(length, dtype=np.float64)
        for h, level in ((1, 1.0), (2, 0.25), (3, 0.14), (4, 0.07), (5, 0.035)):
            if h * detuned < SR / 2:
                sig += level * np.sin(h * phase + 0.17 * h)
        movement = 0.93 + 0.07 * np.sin(2 * np.pi * (0.08 + 0.015 * channel) * t + pan)
        width_gain = (1.0 - 0.12 * abs(pan))
        track[channel, a : a + length] += (amp * width_gain * sig * env * movement).astype(np.float32)


def kick() -> np.ndarray:
    duration = 0.55
    t = np.arange(int(SR * duration), dtype=np.float64) / SR
    freq = 43.0 + 105.0 * np.exp(-t * 24.0)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 8.2)
    click = RNG.normal(0, 1, len(t)) * np.exp(-t * 75.0) * 0.08
    return (0.88 * np.tanh(1.7 * (body + click))).astype(np.float32)


def snare(soft: bool = False) -> np.ndarray:
    duration = 0.42
    t = np.arange(int(SR * duration), dtype=np.float64) / SR
    noise = RNG.normal(0, 1, len(t))
    # Fast one-pole difference removes the very low noise energy.
    bright = np.concatenate(([noise[0]], np.diff(noise)))
    body = np.sin(2 * np.pi * 182 * t + 0.2) * np.exp(-t * 16)
    burst = bright * np.exp(-t * (18 if soft else 12))
    sig = (0.13 if soft else 0.23) * burst + (0.11 if soft else 0.16) * body
    # Two micro-claps increase apparent width and human feel.
    if not soft:
        for offset in (0.018, 0.037):
            sh = int(offset * SR)
            sig[sh:] += 0.055 * bright[:-sh] * np.exp(-t[:-sh] * 20)
    return np.tanh(sig).astype(np.float32)


def hat(open_hat: bool = False) -> np.ndarray:
    duration = 0.28 if open_hat else 0.09
    t = np.arange(int(SR * duration), dtype=np.float64) / SR
    noise = RNG.normal(0, 1, len(t))
    hp = np.concatenate(([noise[0]], np.diff(noise)))
    metallic = 0.24 * np.sin(2 * np.pi * 7421 * t) + 0.18 * np.sin(2 * np.pi * 10331 * t + 0.8)
    decay = 13 if open_hat else 47
    return (0.11 * (hp + metallic) * np.exp(-t * decay)).astype(np.float32)


def transition_swell(duration: float, amp: float = 0.12) -> np.ndarray:
    length = int(SR * duration)
    t = np.arange(length, dtype=np.float64) / SR
    noise = RNG.normal(0, 1, length)
    # Smoothed noise, gradually brighter and louder.
    smooth = np.convolve(noise, np.ones(17) / 17, mode="same")
    rise = (t / max(duration, 1e-6)) ** 2.2
    tone = np.sin(2 * np.pi * (90 * t + 70 * t * t / duration))
    return (amp * rise * (0.75 * smooth + 0.25 * tone)).astype(np.float32)


def bar_time(bar: int, beat: float = 0.0) -> float:
    return bar * BAR + beat * BEAT


def build() -> np.ndarray:
    pad = stereo_track()
    arp = stereo_track()
    bass = stereo_track()
    lead = stereo_track()
    drums = stereo_track()
    atmosphere = stereo_track()

    # G minor / B-flat major palette. One chord per bar; the melody is newly composed.
    chords = {
        "Gm": (43, 50, 58, 62),
        "Eb": (39, 46, 55, 58),
        "Bb": (46, 53, 58, 62),
        "F": (41, 48, 57, 60),
    }
    progression = ("Gm", "Eb", "Bb", "F")

    # Pad carries the reference's dark, harmonic-dominant profile.
    for bar in range(27):
        chord_name = progression[bar % 4]
        energy = 0.045
        if 4 <= bar < 10:
            energy = 0.055
        elif 10 <= bar < 20:
            energy = 0.068
        elif bar >= 22:
            energy = 0.052 * max(0.45, (27 - bar) / 5)
        for idx, note in enumerate(chords[chord_name]):
            add_pad_note(pad, note, bar_time(bar), BAR * 1.08, energy, (-0.72, -0.24, 0.28, 0.75)[idx])
        # Quiet ninth/colour note on alternating bars.
        if bar % 4 in (0, 2) and bar < 24:
            colour = 69 if chord_name == "Gm" else 65
            add_pad_note(pad, colour, bar_time(bar, 0.08), BAR * 0.9, energy * 0.24, 0.55)

    # Felt-pluck arpeggio, deliberately asymmetrical so it breathes.
    arp_patterns = {
        "Gm": (58, 62, 67, 69, 67, 62, 58, 69),
        "Eb": (55, 58, 63, 67, 63, 58, 55, 62),
        "Bb": (58, 62, 65, 70, 65, 62, 58, 67),
        "F": (57, 60, 65, 67, 65, 60, 57, 64),
    }
    for bar in range(2, 24):
        density = 4 if bar < 4 or bar >= 20 else 8
        pattern = arp_patterns[progression[bar % 4]]
        for step in range(density):
            slot = step * (8 / density)
            note = pattern[int(slot)]
            start = bar_time(bar, slot * 0.5) + RNG.uniform(-0.008, 0.008)
            velocity = (0.050 if bar < 10 else 0.060) * (0.88 + 0.16 * RNG.random())
            add_mono(arp, tone_signal(note, BEAT * 0.72, velocity, "pluck", 0.004, 0.18), start, (-0.48, 0.42)[step % 2])

    # Bass rhythm changes with the arrangement while retaining the 108 BPM pulse.
    root_notes = {"Gm": 31, "Eb": 27, "Bb": 34, "F": 29}
    fifth_notes = {"Gm": 38, "Eb": 34, "Bb": 41, "F": 36}
    for bar in range(4, 23):
        chord = progression[bar % 4]
        if bar < 10:
            pattern = ((0.0, root_notes[chord], 1.45), (2.0, fifth_notes[chord], 1.25))
        elif bar < 20:
            pattern = (
                (0.0, root_notes[chord], 0.82),
                (1.5, fifth_notes[chord], 0.42),
                (2.0, root_notes[chord], 0.80),
                (3.25, fifth_notes[chord], 0.50),
            )
        else:
            pattern = ((0.0, root_notes[chord], 1.6), (2.5, fifth_notes[chord], 0.75))
        for beat, note, beats_long in pattern:
            add_mono(bass, tone_signal(note, beats_long * BEAT, 0.16, "bass", 0.012, 0.11), bar_time(bar, beat), 0.0)

    # Original four-bar theme and its higher-energy answer.
    theme = [
        (0.0, 67, 1.35), (1.5, 74, 0.42), (2.0, 70, 0.88), (3.0, 69, 0.38), (3.5, 67, 0.42),
        (4.0, 70, 0.90), (5.0, 67, 0.42), (5.5, 65, 0.42), (6.0, 63, 0.90), (7.0, 67, 0.86),
        (8.0, 65, 0.42), (8.5, 74, 0.42), (9.0, 72, 0.88), (10.0, 70, 0.90), (11.0, 74, 0.42), (11.5, 72, 0.42),
        (12.0, 69, 0.90), (13.0, 72, 0.42), (13.5, 69, 0.42), (14.0, 65, 1.55),
    ]
    # Main statement from bar 10, then a displaced answer from bar 14.
    for base_bar, transpose, gain in ((10, 0, 0.094), (14, 0, 0.102), (18, 12, 0.078)):
        max_beats = 16 if base_bar < 18 else 8
        for beat, note, length in theme:
            if beat >= max_beats:
                continue
            # The second statement alters selected intervals rather than copying exactly.
            altered = note + transpose
            if base_bar == 14 and int(beat * 2) % 5 == 0:
                altered -= 2
            add_mono(
                lead,
                tone_signal(altered, length * BEAT, gain, "lead", 0.045, 0.18),
                bar_time(base_bar, beat),
                -0.10 + 0.20 * math.sin(beat * 0.9),
            )

    # A restrained final phrase falls back into G, matching the reference's fading energy arc.
    outro_phrase = ((0.0, 74, 0.8), (1.0, 72, 0.8), (2.0, 70, 0.8), (3.0, 67, 1.6))
    for beat, note, length in outro_phrase:
        add_mono(lead, tone_signal(note, length * BEAT, 0.063, "lead", 0.06, 0.28), bar_time(22, beat), 0.18)

    # Drums: a quiet pulse is present from the opening (as in the reference),
    # expands in the centre, and becomes a distant heartbeat in the outro.
    kick_sample = kick()
    for bar in range(0, 25):
        if bar < 4:
            kick_beats, drum_level = (0.0, 2.0), 0.34
        elif bar < 10:
            kick_beats, drum_level = (0.0, 2.5), 0.86
        elif bar < 19:
            kick_beats, drum_level = (0.0, 1.0, 2.0, 3.0), 1.0
        elif bar < 22:
            kick_beats, drum_level = (0.0, 2.0), 0.78
        else:
            kick_beats, drum_level = (0.0, 2.0), 0.28 * (25 - bar) / 3
        for beat in kick_beats:
            add_mono(drums, kick_sample * drum_level, bar_time(bar, beat), 0.0)
        for beat in (1.0, 3.0):
            snare_level = 0.46 if bar < 4 else (1.0 if bar < 22 else 0.25 * (25 - bar) / 3)
            add_mono(drums, snare(soft=bar < 10 or bar >= 22) * snare_level, bar_time(bar, beat), RNG.uniform(-0.16, 0.16))
        hat_steps = 8 if bar < 10 or bar >= 19 else 16
        for step in range(hat_steps):
            beat = step * 4.0 / hat_steps
            accent = 1.0 if step % (hat_steps // 4) == 0 else 0.62
            section_level = 0.32 if bar < 4 else (1.0 if bar < 22 else 0.22 * (25 - bar) / 3)
            human = RNG.uniform(-0.006, 0.006)
            add_mono(
                drums,
                hat(open_hat=(step == hat_steps - 2 and 10 <= bar < 19)) * accent * section_level,
                bar_time(bar, beat) + human,
                (-0.46, 0.46)[step % 2],
            )

    # Transition swells and an almost subliminal tape/noise bed.
    for transition_bar in (4, 10, 18, 22):
        swell = transition_swell(BAR, 0.075 if transition_bar != 18 else 0.10)
        add_mono(atmosphere, swell, bar_time(transition_bar - 1), -0.35)
        add_mono(atmosphere, swell[::-1] * 0.45, bar_time(transition_bar), 0.38)
    texture = RNG.normal(0, 1, N).astype(np.float32)
    texture = np.convolve(texture, np.ones(11, dtype=np.float32) / 11, mode="same").astype(np.float32)
    slow = 0.55 + 0.45 * np.sin(2 * np.pi * np.arange(N) / SR * 0.07)
    atmosphere += (texture * slow * 0.0026)[None, :]

    # Musical side-chain breathing around every kick in the full arrangement.
    duck = np.ones(N, dtype=np.float32)
    for bar in range(4, 22):
        kick_beats = (0.0, 2.5) if bar < 10 else ((0.0, 1.0, 2.0, 3.0) if bar < 19 else (0.0, 2.0))
        for beat in kick_beats:
            a = int(bar_time(bar, beat) * SR)
            length = min(int(0.32 * SR), N - a)
            if length > 0:
                curve = 0.72 + 0.28 * (1 - np.exp(-np.arange(length) / (0.085 * SR)))
                duck[a : a + length] = np.minimum(duck[a : a + length], curve.astype(np.float32))
    pad *= duck
    arp *= duck
    bass *= (0.83 + 0.17 * duck)

    # Track-level spaces are intentionally different to preserve depth.
    pad = Pedalboard([
        Chorus(rate_hz=0.18, depth=0.22, centre_delay_ms=13.0, feedback=0.06, mix=0.22),
        Reverb(room_size=0.66, damping=0.62, wet_level=0.20, dry_level=0.90, width=1.0),
    ])(pad, SR)
    arp = Pedalboard([
        Delay(delay_seconds=BEAT * 0.75, feedback=0.19, mix=0.14),
        Reverb(room_size=0.48, damping=0.57, wet_level=0.16, dry_level=0.94, width=0.92),
    ])(arp, SR)
    lead = Pedalboard([
        Chorus(rate_hz=0.31, depth=0.12, centre_delay_ms=8.5, feedback=0.03, mix=0.13),
        Delay(delay_seconds=BEAT * 0.5, feedback=0.25, mix=0.17),
        Reverb(room_size=0.58, damping=0.53, wet_level=0.18, dry_level=0.93, width=1.0),
    ])(lead, SR)
    drums = Pedalboard([Compressor(threshold_db=-20, ratio=2.6, attack_ms=7, release_ms=95)])(drums, SR)

    mix = pad * 0.94 + arp * 0.92 + bass * 1.05 + lead + drums * 0.95 + atmosphere

    # Slow opening and closing fades; extra post-48 s taper follows the reference arc.
    fade = np.ones(N, dtype=np.float32)
    fade[: int(0.45 * SR)] = np.sin(np.linspace(0, math.pi / 2, int(0.45 * SR), dtype=np.float32)) ** 2
    fade[-int(2.1 * SR) :] = np.cos(np.linspace(0, math.pi / 2, int(2.1 * SR), dtype=np.float32)) ** 2
    mix *= fade[None, :]

    master = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=28.0),
        LowShelfFilter(cutoff_frequency_hz=145.0, gain_db=1.2, q=0.7),
        Compressor(threshold_db=-15.5, ratio=2.1, attack_ms=18, release_ms=150),
        Gain(gain_db=2.0),
        Limiter(threshold_db=-1.0, release_ms=90),
    ])(mix.astype(np.float32), SR)

    peak = float(np.max(np.abs(master)))
    if peak > 0.98:
        master *= 0.98 / peak
    return master.astype(np.float32)


def main() -> None:
    output = Path("afterlight_mix.wav")
    audio = build()
    sf.write(output, audio.T, SR, subtype="PCM_24")
    peak = 20 * math.log10(float(np.max(np.abs(audio))) + 1e-12)
    rms = 20 * math.log10(float(np.sqrt(np.mean(audio**2))) + 1e-12)
    print(f"Wrote {output}: {DURATION:.2f} s, {SR} Hz, stereo, peak {peak:.2f} dBFS, RMS {rms:.2f} dBFS")


if __name__ == "__main__":
    main()
