import React, { useEffect, useRef, useState, useCallback } from "react";
import { transcribeAudio } from "../services/speechApi";
import { sendChatMessage } from "../services/chatApi";
import { textToSpeech } from "../services/voiceApi";

const getSupportedMimeType = () => {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
    "audio/mp4",
    "", // browser default
  ];
  for (const mime of candidates) {
    if (mime === "" || MediaRecorder.isTypeSupported(mime)) {
      console.log(`[MediaRecorder Probe] Selected MIME: "${mime || 'default'}"`);
      return mime;
    }
  }
  return "";
};

const SpeechTerminal = ({ onStateChange }) => {
  const [text, setText] = useState("");
  const [aiText, setAiText] = useState("");
  const [status, setStatus] = useState("Ready");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const typingTimerRef = useRef(null);
  const mediaRecorderRef   = useRef(null);
  const chunksRef          = useRef([]);
  const streamRef          = useRef(null);
  const conversationIdRef  = useRef(null);
  const audioPlayerRef     = useRef(null);
  const recordStartRef     = useRef(0);
  const supportedMimeRef   = useRef("");

  const updateGlobalState = useCallback((updates) => {
    if (onStateChange) onStateChange(updates);
  }, [onStateChange]);

  // Init MIME
  useEffect(() => {
    supportedMimeRef.current = getSupportedMimeType();
  }, []);

  // ─── RECORDING CONTROLS ───

  const startRecording = async () => {
    console.log("[startRecording] Invoked. Requesting microphone access...");
    
    // Stop TTS playback if playing
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.src = "";
    }

    setAiText("");
    setText("Listening... (Click again to stop)");
    setStatus("Listening...");
    setIsRecording(true);
    updateGlobalState({ micStatus: "ACTIVE", status: "Listening..." });

    try {
      if (!streamRef.current) {
        console.log("[startRecording] Requesting getUserMedia...");
        streamRef.current = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true }
        });
        console.log("[startRecording] Microphone permission granted.");
      }

      const stream = streamRef.current;
      const opts = supportedMimeRef.current ? { mimeType: supportedMimeRef.current } : {};
      
      console.log(`[startRecording] Creating MediaRecorder with options:`, opts);
      const mr = new MediaRecorder(stream, opts);
      mediaRecorderRef.current = mr;
      chunksRef.current = [];
      recordStartRef.current = Date.now();

      mr.onstart = () => {
        console.log(`[MediaRecorder.onstart] Recording started. MIME: "${mr.mimeType}"`);
      };

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
          console.log(`[MediaRecorder.ondataavailable] Chunk size: ${e.data.size} bytes, Total chunks: ${chunksRef.current.length}`);
        }
      };

      mr.onerror = (err) => {
        console.error("[MediaRecorder.onerror] Error:", err);
      };

      mr.onstop = () => {
        console.log("[MediaRecorder.onstop] Fired.");
        handleRecordingStop();
      };

      console.log("[startRecording] Calling mr.start(250)...");
      mr.start(250);

    } catch (err) {
      console.error("[startRecording] Error initializing microphone or recorder:", err);
      setIsRecording(false);
      setStatus("Mic Error");
      setText("Microphone access denied or failed.");
    }
  };

  const stopRecording = () => {
    console.log("[stopRecording] Invoked.");
    setIsRecording(false);
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      console.log("[stopRecording] Calling mediaRecorder.stop()...");
      mediaRecorderRef.current.stop();
    } else {
      console.warn("[stopRecording] MediaRecorder is already inactive or null.");
    }
  };

  const handleRecordingStop = async () => {
    console.log("[handleRecordingStop] Invoked.");
    
    const durationMs = Date.now() - recordStartRef.current;
    const mimeType = mediaRecorderRef.current?.mimeType || supportedMimeRef.current || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });

    console.log(`[handleRecordingStop] Blob compiled. Size: ${blob.size} bytes, Duration: ${durationMs}ms, MIME: "${mimeType}"`);

    if (blob.size === 0) {
      console.error("[handleRecordingStop] ERROR: Blob size is 0 bytes! Microphone may be muted or blocked.");
      setStatus("Error");
      setText("Recording failed: 0 bytes recorded.");
      return;
    }

    if (durationMs < 300) {
      console.warn("[handleRecordingStop] Warning: Recording extremely short (<300ms).");
    }

    await runPipeline(blob, mimeType);
  };

  // ─── CLICK HANDLER ───

  const handleCardClick = () => {
    console.log(`[handleCardClick] Invoked. Current state isRecording = ${isRecording}`);
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // ─── PIPELINE ───

  const runPipeline = async (audioBlob, mimeType) => {
    console.log("[runPipeline] Invoked. Starting pipeline sequence...");
    setStatus("Transcribing...");
    setText("Uploading audio to backend...");
    updateGlobalState({ status: "Transcribing..." });

    try {
      // 1. STT
      console.log(`[runPipeline] Calling transcribeAudio() -> POST /api/speech-to-text`);
      const transcript = await transcribeAudio(audioBlob, mimeType);
      console.log(`[runPipeline] transcribeAudio() resolved. Transcript: "${transcript}"`);

      if (!transcript || transcript.trim().length === 0) {
        throw new Error("STT returned an empty transcript.");
      }

      setText(transcript.trim());
      setStatus("Thinking...");
      updateGlobalState({ status: "Thinking..." });

      // 2. Chat
      console.log(`[runPipeline] Calling sendChatMessage() -> POST /api/chat`);
      const chatData = await sendChatMessage(transcript.trim(), conversationIdRef.current);
      conversationIdRef.current = chatData.conversationId;
      const answer = chatData.answer;
      console.log(`[runPipeline] sendChatMessage() resolved. Answer: "${answer}"`);

      // 3. TTS
      setStatus("Speaking...");
      updateGlobalState({ status: "Speaking..." });

      console.log(`[runPipeline] Calling textToSpeech() -> POST /api/text-to-speech`);
      const voiceBlob = await textToSpeech(answer.trim());
      console.log(`[runPipeline] textToSpeech() resolved. MP3 Blob size: ${voiceBlob.size} bytes`);

      playAudio(answer.trim(), voiceBlob);

    } catch (err) {
      console.error("[runPipeline] Pipeline Error:", err.message || err);
      setStatus("Ready");
      setText(`Error: ${err.message || "Pipeline failed"}`);
      updateGlobalState({ status: "Ready" });
    }
  };

  const playAudio = (answerText, audioBlob) => {
    console.log("[playAudio] Invoked. Setting up HTMLAudioElement...");
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audioPlayerRef.current = audio;

    audio.onplay = () => {
      console.log("[Audio] Playback started.");
      setIsSpeaking(true);
      updateGlobalState({ isSpeaking: true, status: "Speaking..." });
    };

    audio.onended = () => {
      console.log("[Audio] Playback finished.");
      setIsSpeaking(false);
      setStatus("Ready");
      updateGlobalState({ isSpeaking: false, status: "Ready" });
      URL.revokeObjectURL(audioUrl);
      setTimeout(() => {
        setAiText("");
        setText("");
      }, 5000);
    };

    audio.onerror = (e) => {
      console.error("[Audio] Playback error:", e);
    };

    console.log("[playAudio] Calling audio.play()...");
    audio.play().catch((err) => {
      console.error("[Audio] Autoplay blocked or failed:", err);
      setIsSpeaking(true);
      setTimeout(() => audio.onended(), answerText.length * 50);
    });

    setAiText("");
    let i = 0;
    if (typingTimerRef.current) clearInterval(typingTimerRef.current);
    typingTimerRef.current = setInterval(() => {
      i++;
      setAiText(answerText.substring(0, i));
      if (i >= answerText.length) clearInterval(typingTimerRef.current);
    }, 20);
  };

  // ─── RENDER ───

  return (
    <div className="fixed bottom-3 left-0 right-0 z-50 flex justify-center px-4">
      <div
        onClick={handleCardClick}
        className="
          relative w-full max-w-xl overflow-hidden bg-black/80 backdrop-blur-2xl 
          border border-cyan-400/50 shadow-[0_0_50px_rgba(0,255,255,0.2)] 
          transition-all duration-300 cursor-pointer hover:border-cyan-400
        "
        style={{ clipPath: "polygon(5% 0%, 100% 0%, 100% 75%, 95% 100%, 0% 100%, 0% 25%)" }}
      >
        <div className="absolute inset-0 opacity-20 bg-gradient-to-br from-cyan-500 via-transparent to-purple-500" />
        
        {isRecording && (
          <div className="absolute inset-0 border-2 border-red-500 animate-pulse pointer-events-none" />
        )}

        <div className="relative z-10 px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex flex-col">
              <span className="text-cyan-300 text-[12px] tracking-[4px] uppercase font-bold font-mono">
                {isRecording ? "🔴 RECORDING ACTIVE" : "Brahmastra AI"}
              </span>
            </div>
            <div className="flex items-center gap-2 bg-cyan-950/40 px-2 py-1 rounded border border-cyan-400/20">
              <span className="text-[10px] uppercase font-mono text-cyan-200">
                {status}
              </span>
            </div>
          </div>

          <div className="h-[65px] flex flex-col justify-center">
            {aiText ? (
              <div className="flex flex-col gap-1">
                <span className="text-purple-400 font-mono text-[10px]">BRAHMASTRA AI:</span>
                <p className="text-white font-mono text-[14px] leading-tight">{aiText}</p>
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                <span className="text-cyan-500 font-mono text-[10px]">USER_INPUT:</span>
                <p className={`font-mono text-[14px] ${isRecording ? "text-red-400 font-bold" : "text-cyan-50"}`}>
                  {text || (
                    <span className="opacity-50">
                      [ CLICK HERE TO START RECORDING ]
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SpeechTerminal;