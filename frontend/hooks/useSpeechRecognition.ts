"use client";

import { useState, useCallback, useRef, useEffect } from "react";

// ── Browser API type declarations ────────────────────────────────────────────

interface SpeechRecognitionResultItem {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionResult {
  readonly [index: number]: SpeechRecognitionResultItem;
  readonly length: number;
  readonly isFinal: boolean;
}

interface SpeechRecognitionResultList {
  readonly [index: number]: SpeechRecognitionResult;
  readonly length: number;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: ((ev: Event) => void) | null;
  onstart: ((ev: Event) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

// ── Hook interface ────────────────────────────────────────────────────────────

interface UseSpeechRecognitionOptions {
  /** Called once with the final transcript when a complete utterance is detected. */
  onResult: (transcript: string) => void;
  /** Called when the browser reports a recognition error. */
  onError?: (error: string) => void;
  /** Called when the user starts speaking (first audio detected). Use to interrupt avatar TTS. */
  onSpeechStart?: () => void;
  /** BCP-47 language tag. Defaults to "en-US". */
  lang?: string;
}

export interface UseSpeechRecognitionReturn {
  /** Whether the microphone is currently active. */
  isListening: boolean;
  /** Whether continuous mode is currently active. */
  isContinuous: boolean;
  /** Live partial transcript (interim, before isFinal). Continuous mode only. */
  interimTranscript: string;
  /** Last finalised transcript. */
  transcript: string;
  /** False on Firefox or when running on the server. */
  isSupported: boolean;
  /** Start a single push-to-talk session. */
  startListening: () => void;
  /** Stop the current push-to-talk session. */
  stopListening: () => void;
  /** Toggle continuous listening mode on. Auto-restarts after each utterance. */
  startContinuous: () => void;
  /** Stop continuous listening mode. */
  stopContinuous: () => void;
}

// ── Hook implementation ───────────────────────────────────────────────────────

export function useSpeechRecognition({
  onResult,
  onError,
  onSpeechStart,
  lang = "en-US",
}: UseSpeechRecognitionOptions): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [isContinuous, setIsContinuous] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isSupported, setIsSupported] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const shouldRestartRef = useRef(false); // controls continuous auto-restart
  const onResultRef = useRef(onResult);
  const onErrorRef = useRef(onError);
  const onSpeechStartRef = useRef(onSpeechStart);

  // Keep refs up to date so callbacks inside recognition handlers see latest values
  useEffect(() => { onResultRef.current = onResult; }, [onResult]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onSpeechStartRef.current = onSpeechStart; }, [onSpeechStart]);

  useEffect(() => {
    setIsSupported(
      typeof window !== "undefined" &&
        ("SpeechRecognition" in window || "webkitSpeechRecognition" in window),
    );
  }, []);

  const _buildRecognition = useCallback(
    (continuous: boolean): SpeechRecognitionInstance => {
      const Ctor = (
        (window as unknown as Record<string, unknown>).SpeechRecognition ??
        (window as unknown as Record<string, unknown>).webkitSpeechRecognition
      ) as new () => SpeechRecognitionInstance;

      const r = new Ctor();
      r.lang = lang;
      r.continuous = continuous;
      r.interimResults = continuous; // only need interim in continuous mode
      r.maxAlternatives = 1;

      r.onstart = () => {
        setIsListening(true);
        setTranscript("");
        setInterimTranscript("");
        onSpeechStartRef.current?.();
      };

      r.onresult = (event: SpeechRecognitionEvent) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const text = result[0]?.transcript ?? "";
          if (result.isFinal) {
            const finalText = text.trim();
            if (finalText) {
              setTranscript(finalText);
              setInterimTranscript("");
              // In push-to-talk (non-continuous) mode, stop immediately on the
              // final result so the button snaps back to idle without waiting
              // for the natural onend event.
              if (!continuous) {
                recognitionRef.current?.stop();
                setIsListening(false);
              }
              onResultRef.current(finalText);
            }
          } else {
            interim += text;
          }
        }
        if (interim) setInterimTranscript(interim);
      };

      r.onerror = (event: SpeechRecognitionErrorEvent) => {
        if (event.error !== "no-speech" && event.error !== "aborted") {
          onErrorRef.current?.(event.error);
        }
        setIsListening(false);
        setInterimTranscript("");
      };

      r.onend = () => {
        setIsListening(false);
        setInterimTranscript("");
        // Auto-restart in continuous mode unless explicitly stopped
        if (shouldRestartRef.current) {
          try {
            recognitionRef.current?.start();
            setIsListening(true);
          } catch {
            // Ignore: can happen if the component is unmounting
          }
        }
      };

      return r;
    },
    [lang],
  );

  const startListening = useCallback(() => {
    if (!isSupported) return;
    recognitionRef.current?.abort();
    shouldRestartRef.current = false;
    const r = _buildRecognition(false);
    recognitionRef.current = r;
    r.start();
  }, [isSupported, _buildRecognition]);

  const stopListening = useCallback(() => {
    shouldRestartRef.current = false;
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startContinuous = useCallback(() => {
    if (!isSupported) return;
    recognitionRef.current?.abort();
    shouldRestartRef.current = true;
    setIsContinuous(true);
    const r = _buildRecognition(true);
    recognitionRef.current = r;
    r.start();
  }, [isSupported, _buildRecognition]);

  const stopContinuous = useCallback(() => {
    shouldRestartRef.current = false;
    setIsContinuous(false);
    recognitionRef.current?.stop();
    setIsListening(false);
    setInterimTranscript("");
  }, []);

  // Abort on unmount
  useEffect(() => {
    return () => {
      shouldRestartRef.current = false;
      recognitionRef.current?.abort();
    };
  }, []);

  return {
    isListening,
    isContinuous,
    interimTranscript,
    transcript,
    isSupported,
    startListening,
    stopListening,
    startContinuous,
    stopContinuous,
  };
}


