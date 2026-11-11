import React, { useState, useRef, useEffect } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  Loader2,
  Sparkles,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Bot,
  User,
} from 'lucide-react';
import { api } from '../../services/api';

interface Message {
  sender: 'ai' | 'user';
  text: string;
  time: string;
}

interface VoiceAssistantProps {
  currentQuestion?: string;
  onVoiceResponse: (text: string) => void;
  isProcessing?: boolean;
}

export const VoiceAssistantWidget: React.FC<VoiceAssistantProps> = ({
  currentQuestion,
  onVoiceResponse,
  isProcessing = false,
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [inputText, setInputText] = useState('');
  const [lastSpokenText, setLastSpokenText] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'ai',
      text: 'Namaste! Main aapka AI Accounting Assistant hoon. Hindi, Marathi ya English mein boliye ya type kijiye.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // When a clarification question arrives, post it to chat and speak it
  useEffect(() => {
    if (currentQuestion && currentQuestion !== lastSpokenText) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'ai',
          text: currentQuestion,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      if (!isMuted) {
        speakText(currentQuestion);
      }
      setLastSpokenText(currentQuestion);
    }
  }, [currentQuestion, isMuted]);

  const speakText = async (text: string) => {
    try {
      setIsSpeaking(true);
      const res = await api.textToSpeech(text);
      if (res.audio_base64) {
        const audioSrc = `data:audio/wav;base64,${res.audio_base64}`;
        const audio = new Audio(audioSrc);
        audioPlayerRef.current = audio;
        audio.onended = () => setIsSpeaking(false);
        audio.play();
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
        stream.getTracks().forEach((track) => track.stop());

        setIsTranscribing(true);
        try {
          const res = await api.transcribeAudio(audioBlob);
          if (res.transcript) {
            handleUserMessage(res.transcript);
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
      alert('Microphone permission denied.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleUserMessage = (text: string) => {
    if (!text.trim()) return;
    setMessages((prev) => [
      ...prev,
      {
        sender: 'user',
        text,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    onVoiceResponse(text);
    setInputText('');
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Collapsed Pill Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2.5 px-4 py-3 bg-slate-900 text-white rounded-full shadow-2xl hover:bg-slate-800 transition-all border border-slate-700 hover:scale-105"
        >
          <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold">Hinglish Voice Assistant</span>
          <ChevronUp className="w-4 h-4 text-slate-400" />
        </button>
      )}

      {/* Expanded Right-Side Chat & Voice Box */}
      {isOpen && (
        <div className="w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col h-[480px] transition-all">
          {/* Header */}
          <div className="bg-slate-900 text-white p-3.5 flex items-center justify-between border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold leading-tight">AI Voice Assistant</h3>
                <span className="text-[10px] text-emerald-400 font-medium">Hinglish Voice Active</span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {currentQuestion && (
                <button
                  type="button"
                  onClick={() => speakText(currentQuestion)}
                  title="Replay Voice Question"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsMuted(!isMuted)}
                title={isMuted ? 'Unmute' : 'Mute'}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                {isMuted ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5 text-emerald-400" />}
              </button>

              <button
                onClick={() => setIsOpen(false)}
                title="Minimize"
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Conversation History */}
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-slate-50 text-xs">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex gap-2 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'ai' && (
                  <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-3.5 h-3.5" />
                  </div>
                )}
                <div
                  className={`max-w-[78%] rounded-2xl px-3 py-2 leading-relaxed ${
                    m.sender === 'user'
                      ? 'bg-slate-900 text-white rounded-tr-xs'
                      : 'bg-white text-slate-800 border border-slate-200/80 shadow-xs rounded-tl-xs'
                  }`}
                >
                  <p>{m.text}</p>
                  <span className={`text-[9px] block mt-1 ${m.sender === 'user' ? 'text-slate-400 text-right' : 'text-slate-400'}`}>
                    {m.time}
                  </span>
                </div>
                {m.sender === 'user' && (
                  <div className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            ))}

            {isSpeaking && (
              <div className="text-[11px] text-emerald-600 italic flex items-center gap-1.5 py-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                AI is speaking in Hinglish...
              </div>
            )}
            {isTranscribing && (
              <div className="text-[11px] text-blue-600 italic flex items-center gap-1.5 py-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Recognizing your voice...
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Live Voice Status Indicator */}
          {isRecording && (
            <div className="bg-rose-50 border-t border-rose-200 px-3 py-1.5 text-[11px] text-rose-700 font-semibold flex items-center justify-between animate-pulse">
              <span>Listening to your voice... (Boliye)</span>
              <span className="w-2 h-2 rounded-full bg-rose-600" />
            </div>
          )}

          {/* Input Footer */}
          <div className="p-2.5 bg-white border-t border-slate-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleUserMessage(inputText);
              }}
              className="flex items-center gap-1.5"
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type or click mic to speak..."
                className="flex-1 text-xs px-3 py-2 bg-slate-100 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />

              {/* Mic Action */}
              <button
                type="button"
                disabled={isTranscribing || isProcessing}
                onClick={isRecording ? stopRecording : startRecording}
                className={`p-2.5 rounded-xl text-white transition-all ${
                  isRecording ? 'bg-rose-600 hover:bg-rose-700 voice-pulse' : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
                title={isRecording ? 'Stop Recording' : 'Speak in Hinglish'}
              >
                {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>

              <button
                type="submit"
                disabled={!inputText.trim()}
                className="p-2.5 bg-slate-800 text-white rounded-xl hover:bg-slate-900 disabled:opacity-40"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

