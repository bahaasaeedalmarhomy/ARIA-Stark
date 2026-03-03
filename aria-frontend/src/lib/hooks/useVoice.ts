"use client";

import { useEffect, useRef } from "react";
import { useARIAStore } from "@/lib/store/aria-store";
import { createAudioWebSocket } from "@/lib/ws/audioWebSocket";
import { BACKEND_URL } from "@/lib/constants";

// ─────────────────────────────────────────────────────────────────
// Browser capability check
// ─────────────────────────────────────────────────────────────────

export function isVoiceSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    !!navigator.mediaDevices &&
    "getUserMedia" in navigator.mediaDevices &&
    "WebSocket" in window
  );
}

// ─────────────────────────────────────────────────────────────────
// PCM helpers
// ─────────────────────────────────────────────────────────────────

/**
 * Downsamples a Float32 PCM buffer from `fromRate` to `toRate` using nearest-
 * neighbour interpolation, then converts to Int16.
 * Note: ScriptProcessorNode captures at the AudioContext sample rate (often
 * 44100 or 48000). Gemini Live requires 16 kHz — this function handles the
 * conversion.
 */
// VAD constants
const VAD_ONSET_THRESHOLD = 0.15; // normalized amplitude 0–1
const VAD_SILENCE_DEBOUNCE_MS = 800; // ms of silence before clearing vadActive

export function downsampleAndConvert(
  input: Float32Array,
  fromRate: number,
  toRate: number
): Int16Array {
  const ratio = fromRate / toRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Int16Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = Math.floor(i * ratio);
    const sample = Math.max(-1, Math.min(1, input[srcIndex]));
    output[i] = sample < 0 ? sample * 32768 : sample * 32767;
  }
  return output;
}

// ─────────────────────────────────────────────────────────────────
// useVoice hook
// ─────────────────────────────────────────────────────────────────

export function useVoice() {
  const sessionId = useARIAStore((state) => state.sessionId);

  // Refs for capture pipeline
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const vadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Barge-in dedup ref — prevents multiple HTTP calls per utterance during speaking state
  const bargeInSentRef = useRef(false);

  // Refs for playback pipeline
  const playbackContextRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const speakingEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // WebSocket ref
  const wsRef = useRef<WebSocket | null>(null);

  // ── Amplitude RAF loop ─────────────────────────────────────────

  function startAmplitudeLoop(analyser: AnalyserNode) {
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    function tick() {
      analyser.getByteFrequencyData(dataArray);
      const mean =
        dataArray.reduce((sum, v) => sum + v, 0) / dataArray.length;
      const amplitude = mean / 255;
      useARIAStore.setState({ audioAmplitude: amplitude });

      // VAD threshold detection — provides 200ms visual acknowledgment (AC5)
      // Also triggers barge-in when user speaks during ARIA narration (Story 4.4)
      const { voiceStatus, vadActive, sessionId: currentSessionId, taskStatus } = useARIAStore.getState();
      if ((voiceStatus === "listening" || voiceStatus === "speaking") && amplitude > VAD_ONSET_THRESHOLD) {
        if (!vadActive) {
          useARIAStore.setState({ vadActive: true });
        }

        // Barge-in trigger: fire ONCE per utterance when ARIA is speaking during execution
        if (voiceStatus === "speaking" && taskStatus === "running" && !bargeInSentRef.current) {
          bargeInSentRef.current = true;
          useARIAStore.setState({ voiceStatus: "paused" }); // immediate visual feedback
          // Fire-and-forget — this is inside RAF/non-React context (no await available)
          fetch(`${BACKEND_URL}/api/task/${currentSessionId}/barge-in`, { method: "POST" }).catch(
            () => undefined // network errors are non-fatal here
          );
        }

        if (vadTimerRef.current) clearTimeout(vadTimerRef.current);
        vadTimerRef.current = setTimeout(() => {
          useARIAStore.setState({ vadActive: false });
          bargeInSentRef.current = false; // reset for next utterance
          vadTimerRef.current = null;
        }, VAD_SILENCE_DEBOUNCE_MS);
      }

      rafIdRef.current = requestAnimationFrame(tick);
    }

    rafIdRef.current = requestAnimationFrame(tick);
  }

  function stopAmplitudeLoop() {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
  }

  // ── PCM playback ───────────────────────────────────────────────

  function playPcmChunk(rawBytes: ArrayBuffer) {
    const playbackContext = playbackContextRef.current;
    if (!playbackContext) return;

    // Resume suspended context (iOS/Safari autoplay policy)
    if (playbackContext.state === "suspended") {
      playbackContext.resume().catch(() => undefined);
    }

    const int16 = new Int16Array(rawBytes);
    const SAMPLE_RATE = 24000; // Gemini Live output is 24 kHz PCM L16
    const buffer = playbackContext.createBuffer(1, int16.length, SAMPLE_RATE);
    const channelData = buffer.getChannelData(0);
    for (let i = 0; i < int16.length; i++) {
      channelData[i] = int16[i] / 32768; // normalize to –1…1
    }

    const source = playbackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackContext.destination);

    const startTime = Math.max(
      playbackContext.currentTime,
      nextPlayTimeRef.current
    );
    source.start(startTime);
    nextPlayTimeRef.current = startTime + buffer.duration;

    // First chunk → mark speaking; clear any pending "back to listening" timer
    if (speakingEndTimerRef.current) {
      clearTimeout(speakingEndTimerRef.current);
      speakingEndTimerRef.current = null;
    }
    useARIAStore.setState({ voiceStatus: "speaking" });
    source.onended = () => {
      // Only reset if no more chunks are queued (nextPlayTime already passed)
      if (
        playbackContextRef.current &&
        nextPlayTimeRef.current <= playbackContextRef.current.currentTime + 0.05
      ) {
        // Debounce to prevent flickering with bursty chunk delivery
        speakingEndTimerRef.current = setTimeout(() => {
          if (useARIAStore.getState().voiceStatus === "speaking") {
            useARIAStore.setState({ voiceStatus: "listening" });
          }
          speakingEndTimerRef.current = null;
        }, 300);
      }
    };
  }

  // ── Connect ────────────────────────────────────────────────────

  async function connectMicrophone() {
    if (!isVoiceSupported()) return;
    if (!sessionId) return;

    // Guard against double-connect (rapid clicks before state propagates)
    const currentState = useARIAStore.getState();
    if (
      currentState.isVoiceConnecting ||
      currentState.voiceStatus === "listening" ||
      currentState.voiceStatus === "speaking"
    ) {
      return;
    }

    useARIAStore.setState({ isVoiceConnecting: true, voiceStatus: "connecting" });

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000, // hint only — browser may ignore
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // ── Capture AudioContext ─────────────────────────────────
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);

      // AnalyserNode for VoiceWaveform amplitude
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);
      analyserRef.current = analyser;
      startAmplitudeLoop(analyser);

      // ScriptProcessorNode for raw PCM → WebSocket
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        const pcm16 = downsampleAndConvert(
          float32,
          audioContext.sampleRate,
          16000
        );
        ws.send(pcm16.buffer);
      };

      // Must connect to destination or Chrome silences the processor
      source.connect(processor);
      // Route through zero-gain node to suppress mic echo through speakers
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      processor.connect(silentGain);
      silentGain.connect(audioContext.destination);

      // ── Playback AudioContext ────────────────────────────────
      const playbackContext = new AudioContext({ sampleRate: 24000 });
      playbackContextRef.current = playbackContext;
      nextPlayTimeRef.current = 0;

      // ── WebSocket ────────────────────────────────────────────
      const ws = createAudioWebSocket(sessionId);
      wsRef.current = ws;
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        useARIAStore.setState({
          voiceStatus: "listening",
          isVoiceConnecting: false,
        });
      };

      ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          playPcmChunk(event.data);
        }
      };

      ws.onerror = () => {
        disconnect("disconnected");
      };

      ws.onclose = () => {
        disconnect("disconnected");
      };
    } catch {
      // getUserMedia permission denied or other error
      useARIAStore.setState({
        voiceStatus: "disconnected",
        isVoiceConnecting: false,
      });
    }
  }

  // ── Disconnect ─────────────────────────────────────────────────

  function disconnect(
    status: "idle" | "disconnected" = "idle"
  ) {
    // Stop amplitude loop
    stopAmplitudeLoop();

    // Clear speaking-end debounce timer
    if (speakingEndTimerRef.current) {
      clearTimeout(speakingEndTimerRef.current);
      speakingEndTimerRef.current = null;
    }

    // Stop media tracks
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    // Disconnect and close audio nodes
    processorRef.current?.disconnect();
    processorRef.current = null;
    analyserRef.current?.disconnect();
    analyserRef.current = null;

    // Close capture AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }

    // Close playback AudioContext (prevent leak on reconnect)
    if (playbackContextRef.current) {
      playbackContextRef.current.close().catch(() => undefined);
      playbackContextRef.current = null;
    }

    // Close WebSocket cleanly
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000);
      }
      wsRef.current = null;
    }

    // Clear VAD timer and reset vadActive
    if (vadTimerRef.current) {
      clearTimeout(vadTimerRef.current);
      vadTimerRef.current = null;
    }

    bargeInSentRef.current = false; // reset barge-in dedup ref

    useARIAStore.setState({
      voiceStatus: status,
      isVoiceConnecting: false,
      audioAmplitude: 0,
      vadActive: false,
    });
  }

  function disconnectMicrophone() {
    disconnect();
  }

  // ── Cleanup on unmount ─────────────────────────────────────────

  useEffect(() => {
    if (!isVoiceSupported()) {
      useARIAStore.setState({ voiceStatus: "disconnected" });
    }

    return () => {
      stopAmplitudeLoop();
      if (speakingEndTimerRef.current) clearTimeout(speakingEndTimerRef.current);
      if (vadTimerRef.current) clearTimeout(vadTimerRef.current);
      bargeInSentRef.current = false;
      useARIAStore.setState({ vadActive: false });
      streamRef.current?.getTracks().forEach((t) => t.stop());
      processorRef.current?.disconnect();
      analyserRef.current?.disconnect();
      audioContextRef.current?.close().catch(() => undefined);
      wsRef.current?.close(1000);
      playbackContextRef.current?.close().catch(() => undefined);
    };
  }, []);

  return {
    isSupported: isVoiceSupported(),
    connectMicrophone,
    disconnectMicrophone,
  };
}
