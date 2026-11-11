#!/usr/bin/env python3
"""Monte-Carlo check of the SNR estimator used in raw/ris_control_code/CBA2.m.

CBA2.m averages NumFramesInBurst=5 captures of 1024 samples and reports
10*log10(mean(|avg|^2)/var(avg)). With mu = mean(avg) this equals
10*log10(P / (P - |mu|^2)): it depends only on how much of the averaged
power is a constant (DC) component, not on the received signal's SNR.
"""
import numpy as np
rng = np.random.default_rng(0)
N, F, TRIALS = 1024, 5, 200

def script_snr(frames):
    avg = np.mean(frames, axis=0)
    return 10 * np.log10(np.mean(np.abs(avg) ** 2) / np.var(avg))

# Assumptions: complex baseband; the received LTE signal is modelled as zero-mean circular complex Gaussian
# (a standard approximation for an OFDM waveform whose DC subcarrier is unused); thermal noise is white complex
# Gaussian; the receiver adds a constant complex (DC) term whose amplitude is given relative to the RMS of
# signal+noise. Two cases: bursts not time-aligned (independent waveform per burst, as in the script, which
# does not synchronise to the LTE frame) and, as a bound, perfectly aligned bursts (same waveform, new noise).
print("alignment,true_snr_db,dc_to_rms,script_snr_db_mean,script_snr_db_sd")
for aligned in (False, True):
    for snr_db in (0, 10, 20, 30):
        for dc in (0.0, 1.0, 3.0, 10.0):
            out = []
            for _ in range(TRIALS):
                fr = []
                s0 = np.sqrt(10 ** (snr_db / 10) / 2) * (rng.standard_normal(N) + 1j * rng.standard_normal(N))
                for _ in range(F):
                    s = s0 if aligned else np.sqrt(10 ** (snr_db / 10) / 2) * (rng.standard_normal(N) + 1j * rng.standard_normal(N))
                    n = np.sqrt(.5) * (rng.standard_normal(N) + 1j * rng.standard_normal(N))
                    x = s + n
                    fr.append(x + dc * np.sqrt(np.mean(np.abs(x) ** 2)))
                out.append(script_snr(fr))
            print(f"{'aligned' if aligned else 'unaligned'},{snr_db},{dc},{np.mean(out):.2f},{np.std(out):.2f}")
