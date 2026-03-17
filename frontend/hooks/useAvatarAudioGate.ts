"use client";

import { useState, useEffect, useRef } from "react";

// RMS amplitude above this (0–255 scale) counts as "avatar speaking".
// 8 comfortably clears silence/noise floor; raise if you get false positives.
const SPEAKING_THRESHOLD = 8;

// How long after amplitude drops below threshold before we declare silence (ms).
// Prevents rapid true/false flicker between words.
const SILENCE_DEBOUNCE_MS = 400;

/**
 * Monitors the output amplitude of an HTMLAudioElement via the Web Audio API.
 * Returns true while the avatar is actively playing audio above the threshold.
 *
 * Safe to call with null — returns false until an element is provided.
 * Automatically tears down the AudioContext when the element changes or on unmount.
 */
export function useAvatarAudioGate(audioEl: HTMLAudioElement | null): boolean {
  const [isAvatarSpeaking, setIsAvatarSpeaking] = useState(false);
  const rafRef = useRef<number>(0);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!audioEl) return;

    let cancelled = false;

    const ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.4;

    // createMediaElementSource may only be called once per element.
    // Route: source → analyser → destination so the audio still plays.
    const source = ctx.createMediaElementSource(audioEl);
    source.connect(analyser);
    analyser.connect(ctx.destination);

    const data = new Uint8Array(analyser.frequencyBinCount);

    function poll() {
      if (cancelled) return;

      // Resume AudioContext if the browser suspended it before a user gesture.
      if (ctx.state === "suspended") ctx.resume().catch(() => {});

      analyser.getByteFrequencyData(data);

      // Root Mean Square of frequency-bin magnitudes as an amplitude proxy.
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
      const rms = Math.sqrt(sum / data.length);

      if (rms > SPEAKING_THRESHOLD) {
        // Clear any pending silence timer — avatar is still talking.
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
        setIsAvatarSpeaking(true);
      } else if (!silenceTimerRef.current) {
        // Start debounce timer — only flip to silent after sustained quiet.
        silenceTimerRef.current = setTimeout(() => {
          silenceTimerRef.current = null;
          if (!cancelled) setIsAvatarSpeaking(false);
        }, SILENCE_DEBOUNCE_MS);
      }

      rafRef.current = requestAnimationFrame(poll);
    }

    rafRef.current = requestAnimationFrame(poll);

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      source.disconnect();
      analyser.disconnect();
      void ctx.close();
    };
  }, [audioEl]);

  return isAvatarSpeaking;
}
