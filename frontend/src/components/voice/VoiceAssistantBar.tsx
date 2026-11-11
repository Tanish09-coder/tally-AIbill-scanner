import React, { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Send, Loader2, Sparkles, RotateCcw } from 'lucide-react';
import { api } from '../../services/api';

interface VoiceAssistantBarProps {
  currentQuestion?: string;
  onVoiceResponse: (text: string) => void;
  isProcessing?: boolean;
}

export const VoiceAssistantBar: React.FC<VoiceAssistantBarProps> = ({
  currentQuestion,
  onVoiceResponse,
  isProcessing = false,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [inputText, setInputText] = useState('');
  const [lastSpokenText, setLastSpokenText] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Play spoken question automatically if unmuted
  useEffect(() => {
    if (currentQuestion && currentQuestion !== lastSpokenText && !isMuted) {
      speakText(currentQuestion);
      setLastSpokenText(currentQuestion);
    }
  }, [currentQuestion, isMuted]);

  const speakText = async (text: string) => {
    try {
      setIsSpeaking(true);
      const res = await api.textToSpeech(text);
      if (res.audio_base64) {
        const audioSrc = `data:audio/wav;base64,${res.audio_base64}`;
        if (audioPlayerRef.current) {
          audioPlayerRef.current.src = audioSrc;
          audioPlayerRef.current.play();
        } else {
          const audio = new Audio(audioSrc);
          audioPlayerRef.current = audio;
          audio.onended = () => setIsSpeaking(false);
          audio.play();
        }
      }
    } catch (err) {
      console.warn('TTS playback error:', err);
    } finally {
      setIsSpeaking(false);
    }
  };

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        // Stop audio tracks
        stream.getTracks().forEach((track) => track.stop());

        setIsTranscribing(true);
        try {
          const res = await api.transcribeAudio(audioBlob);
          if (res.transcript) {
            setInputText(res.transcript);
            onVoiceResponse(res.transcript);
          }
        } catch (err) {
          console.error('Speech transcription failed:', err);
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Microphone permission denied or not supported in this browser.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleSubmitText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onVoiceResponse(inputText);
    setInputText('');
  };

  return (
    <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur-md border-t border-slate-200 py-3 px-4 shadow-xl z-50">
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center gap-3">
        {/* Status / Live Prompt */}
        <div className="flex-1 min-w-0 flex items-center gap-2 w-full sm:w-auto">
          <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="text-xs truncate">
            {isRecording ? (
              <span className="text-emerald-700 font-semibold animate-pulse">
                Listening to your Hinglish voice... (Aap bol sakte hain)
              </span>
            ) : isTranscribing ? (
              <span className="text-blue-600 font-medium">Understanding speech (Transcribing)...</span>
            ) : isSpeaking ? (
              <span className="text-emerald-600 font-medium">AI is speaking...</span>
            ) : currentQuestion ? (
              <span className="text-slate-800 font-medium">{currentQuestion}</span>
            ) : (
              <span className="text-slate-400">Voice Assistant ready. Ask questions or speak answers.</span>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          {/* Replay Question */}
          {currentQuestion && (
            <button
              type="button"
              onClick={() => speakText(currentQuestion)}
              title="Replay Question"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}

          {/* Mute Toggle */}
          <button
            type="button"
            onClick={() => setIsMuted(!isMuted)}
            title={isMuted ? 'Unmute Assistant' : 'Mute Assistant'}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-rose-500" /> : <Volume2 className="w-4 h-4 text-emerald-600" />}
          </button>

          {/* Fallback Text Input */}
          <form onSubmit={handleSubmitText} className="flex items-center gap-1.5 flex-1 sm:w-64">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Or type here..."
              className="w-full text-xs px-3 py-2 bg-slate-100 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <button
              type="submit"
              disabled={!inputText.trim()}
              className="p-2 bg-slate-800 text-white rounded-xl hover:bg-slate-900 disabled:opacity-40"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Microphone Main Action */}
          <button
            type="button"
            disabled={isTranscribing || isProcessing}
            onClick={isRecording ? stopRecording : startRecording}
            className={`p-3 rounded-full text-white shadow-md transition-all ${
              isRecording
                ? 'bg-rose-600 hover:bg-rose-700 voice-glow'
                : 'bg-emerald-600 hover:bg-emerald-700'
            }`}
          >
            {isTranscribing ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : isRecording ? (
              <MicOff className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

