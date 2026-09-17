import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "../services/chatApi";
import { transcribeAudio } from "../services/speechApi";
import { textToSpeech } from "../services/voiceApi";

const getSupportedMimeType = () => {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
    "audio/mp4",
    "",
  ];
  return candidates.find((mime) => mime === "" || MediaRecorder.isTypeSupported(mime)) || "";
};

const SpeechTerminal = ({ onStateChange }) => {
  const [mode, setMode] = useState("talk");
  const [status, setStatus] = useState("READY");
  const [userInput, setUserInput] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const conversationIdRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const supportedMimeRef = useRef("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    supportedMimeRef.current = getSupportedMimeType();
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioPlayerRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isChatLoading]);

  const updateStatus = (nextStatus) => {
    setStatus(nextStatus);
    onStateChange?.({ statusText: nextStatus, isProcessing: nextStatus !== "READY" });
  };

  const handleChatResult = (query, result) => {
    conversationIdRef.current = result.conversationId;
    setMessages((current) => [
      ...current,
      { role: "user", content: query },
      { role: "assistant", content: result.answer },
    ]);
    setUserInput(query);
    setAiResponse(result.answer);
  };

  const submitChat = async (event) => {
    event?.preventDefault();
    const query = chatInput.trim();
    if (!query || isChatLoading) return;

    setChatInput("");
    setIsChatLoading(true);
    updateStatus("PROCESSING");
    try {
      updateStatus("THINKING");
      const result = await sendChatMessage(query, conversationIdRef.current);
      handleChatResult(query, result);
      updateStatus("RESPONDING");
      updateStatus("READY");
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "user", content: query },
        { role: "system", content: error.response?.data?.message || "The assistant is unavailable." },
      ]);
      updateStatus("ERROR");
    } finally {
      setIsChatLoading(false);
    }
  };

  const startRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    audioPlayerRef.current?.pause();
    setAiResponse("");
    setUserInput("");
    setIsRecording(true);
    updateStatus("LISTENING");

    try {
      if (!streamRef.current) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true },
        });
      }

      const recorder = new MediaRecorder(
        streamRef.current,
        supportedMimeRef.current ? { mimeType: supportedMimeRef.current } : undefined,
      );
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        setIsRecording(false);
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        await runVoicePipeline(blob, recorder.mimeType || "audio/webm");
      };
      recorder.start(250);
    } catch (error) {
      setIsRecording(false);
      setUserInput(error.message || "Microphone access failed.");
      updateStatus("ERROR");
    }
  };

  const runVoicePipeline = async (audioBlob, mimeType) => {
    try {
      updateStatus("TRANSCRIBING");
      const transcript = (await transcribeAudio(audioBlob, mimeType)).trim();
      if (!transcript) throw new Error("Speech-to-text returned no transcript.");
      setUserInput(transcript);

      updateStatus("PROCESSING");
      updateStatus("THINKING");
      const result = await sendChatMessage(transcript, conversationIdRef.current);
      conversationIdRef.current = result.conversationId;
      setAiResponse(result.answer);
      setMessages((current) => [
        ...current,
        { role: "user", content: transcript },
        { role: "assistant", content: result.answer },
      ]);

      updateStatus("RESPONDING");
      const audioBlobResponse = await textToSpeech(result.answer.trim());
      const audioUrl = URL.createObjectURL(audioBlobResponse);
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;
      audio.onplay = () => onStateChange?.({ isSpeaking: true });
      audio.onended = () => {
        onStateChange?.({ isSpeaking: false });
        URL.revokeObjectURL(audioUrl);
        updateStatus("READY");
      };
      await audio.play();
    } catch (error) {
      setUserInput(error.message || "Voice pipeline failed.");
      updateStatus("ERROR");
    }
  };

  const renderChatHistory = () => (
    <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 text-left text-xs font-mono">
      {messages.length === 0 && <p className="text-cyan-100/45">No messages in this conversation.</p>}
      {messages.map((message, index) => (
        <div key={`${message.role}-${index}`} className="border-b border-white/5 pb-2">
          <span className={message.role === "user" ? "text-cyan-300" : "text-purple-300"}>
            {message.role === "user" ? "USER" : message.role === "assistant" ? "BRAHMĀSTRA" : "SYSTEM"}
          </span>
          <p className="mt-1 whitespace-pre-wrap text-white/85">{message.content}</p>
        </div>
      ))}
      {isChatLoading && <p className="text-cyan-300">BRAHMĀSTRA: THINKING...</p>}
      <div ref={messagesEndRef} />
    </div>
  );

  return (
    <div className="fixed bottom-3 left-0 right-0 z-50 flex justify-center px-4">
      <section className="relative flex max-h-[min(72vh,620px)] w-full max-w-2xl flex-col overflow-hidden border border-cyan-400/50 bg-black/85 shadow-[0_0_50px_rgba(0,255,255,0.2)] backdrop-blur-2xl [clip-path:polygon(3%_0%,100%_0%,100%_88%,97%_100%,0%_100%,0%_12%)]">
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 via-transparent to-purple-500/10" />
        <div className="relative z-10 flex min-h-0 flex-1 flex-col px-5 py-4 sm:px-7">
          <header className="flex items-center justify-between border-b border-cyan-400/20 pb-3">
            <span className="font-mono text-xs font-bold tracking-[0.28em] text-cyan-300">BRAHMĀSTRA AI</span>
            <span className="font-mono text-[10px] tracking-[0.2em] text-cyan-200">{status}</span>
          </header>

          <div className="flex justify-center gap-8 py-3 font-mono text-xs">
            <button type="button" onClick={() => setMode("talk")} className={mode === "talk" ? "text-cyan-300" : "text-white/45"}>
              🎙️ TALK {mode === "talk" && <span className="ml-1">[ACTIVE]</span>}
            </button>
            <button type="button" onClick={() => setMode("chat")} className={mode === "chat" ? "text-cyan-300" : "text-white/45"}>
              💬 CHAT {mode === "chat" && <span className="ml-1">[ACTIVE]</span>}
            </button>
          </div>

          {mode === "chat" ? (
            <>
              {renderChatHistory()}
              <form onSubmit={submitChat} className="mt-3 flex gap-2 border-t border-cyan-400/20 pt-3">
                <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask Brahmastra anything..." disabled={isChatLoading} className="min-w-0 flex-1 rounded border border-white/15 bg-white/5 px-3 py-2 font-mono text-xs text-white outline-none focus:border-cyan-400" />
                <button type="submit" disabled={isChatLoading || !chatInput.trim()} className="rounded border border-cyan-400/60 px-4 py-2 font-mono text-xs text-cyan-200 disabled:opacity-40">Send</button>
              </form>
            </>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              <div><span className="text-cyan-500">USER_INPUT:</span><p className="mt-1 min-h-5 whitespace-pre-wrap text-cyan-50">{userInput || "[ CLICK TO START RECORDING ]"}</p></div>
              <div><span className="text-cyan-500">AI_CORE:</span><p className="mt-1 text-cyan-200">{status}</p></div>
              <div><span className="text-purple-400">AI_RESPONSE:</span><p className="mt-1 min-h-5 whitespace-pre-wrap text-white">{aiResponse || "READY"}</p></div>
              <button type="button" onClick={startRecording} className={`w-full border px-4 py-3 text-xs tracking-[0.18em] ${isRecording ? "border-red-400 text-red-300" : "border-cyan-400/50 text-cyan-200"}`}>
                {isRecording ? "🔴 STOP RECORDING" : "🎙️ START RECORDING"}
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default SpeechTerminal;