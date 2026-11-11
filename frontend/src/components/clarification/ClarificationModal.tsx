import React, { useState, useRef, useEffect } from 'react';
import { ClarificationQuestion, Bill } from '../../types';
import {
  X,
  Send,
  CheckCircle2,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Volume2,
  Mic,
  MicOff,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { api } from '../../services/api';

interface ClarificationModalProps {
  bill: Bill;
  questions: ClarificationQuestion[];
  onClose: () => void;
  onResolved: () => void;
}

export const ClarificationModal: React.FC<ClarificationModalProps> = ({
  bill,
  questions,
  onClose,
  onResolved,
}) => {
  const [questionList, setQuestionList] = useState<ClarificationQuestion[]>(questions);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answerText, setAnswerText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiFeedback, setAiFeedback] = useState<string | null>(null);

  // Audio TTS & Mic STT
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Synchronize if prop changes
  useEffect(() => {
    if (questions && questions.length > 0) {
      setQuestionList(questions);
    }
  }, [questions]);

  const totalCount = questionList.length;
  const activeQuestion = questionList[currentIndex] || questionList[0];
  const answeredCount = questionList.filter((q) => q.status === 'ANSWERED').length;

  // Audio TTS synthesis
  const handlePlayTTS = async (text: string) => {
    if (isSpeaking) {
      audioPlayerRef.current?.pause();
      setIsSpeaking(false);
      return;
    }
    setIsSpeaking(true);
    try {
      const res = await api.textToSpeech(text);
      if (res.audio_base64) {
        const audio = new Audio(`data:audio/wav;base64,${res.audio_base64}`);
        audioPlayerRef.current = audio;
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = () => setIsSpeaking(false);
        await audio.play();
      }
    } catch (err) {
      console.warn('TTS playback error:', err);
      setIsSpeaking(false);
    }
  };

  // Mic recording
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
            setAnswerText(res.transcript);
            // Optionally auto-submit answer if recognized
            await handleAnswer(res.transcript, true);
          }
        } catch (err) {
          console.error('Speech transcription failed:', err);
        } finally {
          setIsTranscribing(false);
          setIsRecording(false);
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
  };

  // Submit Answer & Immediately advance to Next Question
  const handleAnswer = async (responseValue: string, isVoice: boolean = false) => {
    if (!activeQuestion || !responseValue.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setAiFeedback(null);
    try {
      const res = await api.answerQuestion(activeQuestion.id, responseValue, isVoice);

      // Mark current question as ANSWERED in local state
      const updated = [...questionList];
      updated[currentIndex] = {
        ...updated[currentIndex],
        status: 'ANSWERED',
        answers: [
          ...(updated[currentIndex].answers || []),
          {
            id: Date.now(),
            question_id: activeQuestion.id,
            extracted_value: responseValue,
            confirmed_by_user: true,
            timestamp: new Date().toISOString(),
          },
        ],
      };
      setQuestionList(updated);
      setAnswerText('');

      const remainingPending = updated.filter((q) => q.status === 'PENDING').length;
      setAiFeedback(res.message || '✅ Answer recorded!');

      if (remainingPending === 0) {
        // All answered! Give quick celebration then resolve
        setTimeout(() => {
          onResolved();
        }, 1200);
      } else {
        // Automatically find next pending question, or next index
        const nextPendingIndex = updated.findIndex((q, i) => i > currentIndex && q.status === 'PENDING');
        const fallbackNext = updated.findIndex((q) => q.status === 'PENDING');
        const targetIndex = nextPendingIndex !== -1 ? nextPendingIndex : fallbackNext !== -1 ? fallbackNext : currentIndex;

        setTimeout(() => {
          setAiFeedback(null);
          setCurrentIndex(targetIndex);
          // Optional: Speak new question
          if (updated[targetIndex]?.question_hinglish) {
            // handlePlayTTS(updated[targetIndex].question_hinglish);
          }
        }, 800);
      }
    } catch (err: any) {
      console.error('Failed to submit answer:', err);
      setAiFeedback('⚠️ Could not save answer. Please retry.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Skip current question and go to next
  const handleSkip = () => {
    setAiFeedback(null);
    setAnswerText('');
    if (currentIndex < totalCount - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      // Loop back to first pending or 0
      const firstPending = questionList.findIndex((q) => q.status === 'PENDING');
      setCurrentIndex(firstPending !== -1 ? firstPending : 0);
    }
  };

  // All resolved state
  if (!activeQuestion || (totalCount > 0 && answeredCount === totalCount)) {
    return (
      <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl p-6 max-w-md w-full text-center shadow-2xl border border-slate-200">
          <div className="w-14 h-14 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-3 shadow-sm">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">All Clarifications Resolved!</h3>
          <p className="text-xs text-slate-600 mt-1 mb-5">
            Bill details and handwritten corrections have been verified. You can now preview and post the voucher directly to TallyPrime.
          </p>
          <button
            onClick={onResolved}
            className="w-full py-3 bg-emerald-600 text-white rounded-xl text-xs font-semibold hover:bg-emerald-700 flex items-center justify-center gap-2 shadow-md shadow-emerald-600/20 cursor-pointer"
          >
            <span>View Voucher & Post to Tally</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-4xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col md:flex-row max-h-[92vh]">
        {/* Bill Image Viewer */}
        <div className="md:w-1/2 bg-slate-900/95 p-4 border-r border-slate-800 flex flex-col justify-between items-center text-white">
          <div className="w-full flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="font-semibold text-slate-200">Original Scanned Bill</span>
            <span>Invoice #{bill.invoice_number || bill.id}</span>
          </div>
          <div className="w-full flex-1 flex items-center justify-center overflow-hidden rounded-xl bg-slate-950 border border-slate-800 shadow-inner max-h-[380px] md:max-h-[460px]">
            <img
              src={`/${bill.file_path.replace(/\\/g, '/')}`}
              alt="Original Invoice"
              className="max-h-full max-w-full object-contain"
            />
          </div>
          <span className="text-[11px] text-slate-400 mt-2 text-center">
            Reference handwriting and printed totals while answering questions.
          </span>
        </div>

        {/* Question & Interaction Area */}
        <div className="md:w-1/2 p-5 sm:p-6 flex flex-col justify-between bg-white overflow-y-auto">
          <div>
            {/* Header with Close and Progress */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                  Question {currentIndex + 1} of {totalCount}
                </span>
                <span className="text-[11px] text-slate-500 font-medium">
                  ({answeredCount} answered)
                </span>
              </div>
              <button
                onClick={onClose}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Question Quick-Jump Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-3 scrollbar-none">
              {questionList.map((q, idx) => {
                const isAnswered = q.status === 'ANSWERED';
                const isActive = idx === currentIndex;
                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => {
                      setAiFeedback(null);
                      setAnswerText('');
                      setCurrentIndex(idx);
                    }}
                    className={`h-7 px-2.5 rounded-lg text-xs font-semibold flex items-center gap-1 transition cursor-pointer shrink-0 border ${
                      isActive
                        ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs ring-2 ring-emerald-500/30'
                        : isAnswered
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200'
                    }`}
                    title={q.question_hinglish}
                  >
                    <span>Q{idx + 1}</span>
                    {isAnswered && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
                  </button>
                );
              })}
            </div>

            {/* AI Hinglish Question Card */}
            <div className="p-4 bg-emerald-50/80 border border-emerald-200/90 rounded-2xl mb-4 relative shadow-2xs">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-emerald-900 text-xs font-bold">
                  <Sparkles className="w-4 h-4 text-emerald-600" />
                  <span>AI Hinglish Assistant</span>
                </div>
                <button
                  type="button"
                  onClick={() => handlePlayTTS(activeQuestion.question_hinglish)}
                  disabled={isSpeaking}
                  className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-emerald-700 hover:bg-emerald-100 text-[11px] font-semibold transition disabled:opacity-50 cursor-pointer"
                  title="Listen in Hindi audio voice"
                >
                  <Volume2 className={`w-3.5 h-3.5 ${isSpeaking ? 'animate-pulse text-emerald-600' : ''}`} />
                  <span>{isSpeaking ? 'Playing...' : 'Listen'}</span>
                </button>
              </div>

              <p className="text-sm font-semibold text-slate-900 leading-relaxed">
                "{activeQuestion.question_hinglish}"
              </p>

              {activeQuestion.status === 'ANSWERED' && activeQuestion.answers && activeQuestion.answers.length > 0 && (
                <div className="mt-3 pt-2 border-t border-emerald-200/70 text-xs text-emerald-900 flex items-center gap-1.5 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>
                    Your Answer: <strong>"{activeQuestion.answers[activeQuestion.answers.length - 1].extracted_value}"</strong>
                  </span>
                </div>
              )}
            </div>

            {/* Real-time Feedback Banner */}
            {aiFeedback && (
              <div className="p-3 bg-teal-50 border border-teal-200 text-teal-900 text-xs font-medium rounded-xl mb-3 flex items-center gap-2 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0" />
                <span>{aiFeedback}</span>
              </div>
            )}
          </div>

          {/* Answer Form & Quick Controls */}
          <div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAnswer(answerText);
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Your Answer (Type or Speak in Hindi/English):
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={answerText}
                    onChange={(e) => setAnswerText(e.target.value)}
                    placeholder="e.g. 72380, printed total, Sugar, 25 bags..."
                    disabled={isSubmitting || isTranscribing}
                    className="w-full pl-3.5 pr-20 py-2.5 text-xs sm:text-sm bg-white border border-slate-300 rounded-xl focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 text-slate-900 placeholder-slate-400 shadow-2xs"
                  />
                  <div className="absolute right-1.5 flex items-center gap-1">
                    {/* Voice Mic Input */}
                    <button
                      type="button"
                      onClick={isRecording ? stopRecording : startRecording}
                      disabled={isTranscribing}
                      className={`p-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                        isRecording
                          ? 'bg-rose-500 text-white animate-pulse'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                      title={isRecording ? 'Stop recording' : 'Speak your answer in Hindi/English'}
                    >
                      {isTranscribing ? (
                        <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                      ) : isRecording ? (
                        <MicOff className="w-4 h-4" />
                      ) : (
                        <Mic className="w-4 h-4" />
                      )}
                    </button>

                    {/* Submit Button */}
                    <button
                      type="submit"
                      disabled={isSubmitting || !answerText.trim()}
                      className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 disabled:opacity-40 transition flex items-center gap-1 shadow-2xs cursor-pointer"
                    >
                      {isSubmitting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <>
                          <span>Submit</span>
                          <Send className="w-3 h-3" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </form>

            {/* Bottom Navigation & Skip Controls */}
            <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-200 text-xs">
              <button
                type="button"
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentIndex === 0}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 disabled:opacity-40 font-medium cursor-pointer"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSkip}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 font-medium cursor-pointer"
                >
                  Skip & Next
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (currentIndex < totalCount - 1) {
                      setCurrentIndex((prev) => prev + 1);
                    } else {
                      onResolved();
                    }
                  }}
                  className="flex items-center gap-1 px-3.5 py-1.5 rounded-lg bg-slate-900 text-white hover:bg-slate-800 font-semibold cursor-pointer"
                >
                  <span>{currentIndex < totalCount - 1 ? 'Next' : 'Finish'}</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
