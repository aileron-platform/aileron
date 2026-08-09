import { useCallback, useRef, useState } from 'react';
import { Mic, Square } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';

interface SpeechToTextButtonProps {
  className: string;
  disabled?: boolean;
  transcribeAudio?: (file: File) => Promise<{ text: string }>;
  onBusyChange: (busy: boolean) => void;
  onTranscript: (text: string) => void;
}

type VoiceState = 'idle' | 'recording' | 'processing';

export const SpeechToTextButton = ({
  className,
  disabled = false,
  transcribeAudio,
  onBusyChange,
  onTranscript,
}: SpeechToTextButtonProps) => {
  const { t } = useI18n();
  const [state, setState] = useState<VoiceState>('idle');
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const setBusyState = useCallback((nextState: VoiceState) => {
    setState(nextState);
    onBusyChange(nextState !== 'idle');
  }, [onBusyChange]);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    if (!transcribeAudio || disabled || state !== 'idle') {
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        setBusyState('processing');
        stopStream();
        const type = chunksRef.current[0]?.type || 'audio/webm';
        const file = new File(chunksRef.current, 'voice.webm', { type });
        try {
          const result = await transcribeAudio(file);
          const transcript = result.text.trim();
          if (transcript) {
            onTranscript(transcript);
          }
        } finally {
          recorderRef.current = null;
          chunksRef.current = [];
          setBusyState('idle');
        }
      };

      recorder.start();
      setBusyState('recording');
    } catch {
      recorderRef.current = null;
      chunksRef.current = [];
      stopStream();
      setBusyState('idle');
    }
  }, [disabled, onTranscript, setBusyState, state, stopStream, transcribeAudio]);

  const stopRecording = useCallback(() => {
    if (state !== 'recording') {
      return;
    }
    recorderRef.current?.stop();
  }, [state]);

  const unavailable = disabled || !transcribeAudio || typeof navigator.mediaDevices?.getUserMedia !== 'function';
  const ariaKey = unavailable
    ? 'aiChat.input.voice.unavailable'
    : state === 'recording'
      ? 'aiChat.input.voice.stop'
      : state === 'processing'
        ? 'aiChat.input.voice.processing'
        : 'aiChat.input.voice.start';

  return (
    <button
      type="button"
      aria-label={t(ariaKey)}
      className={className}
      disabled={unavailable || state === 'processing'}
      onClick={state === 'recording' ? stopRecording : startRecording}
    >
      {state === 'recording' ? (
        <Square className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Mic className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
};
