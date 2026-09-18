import { useEffect, useRef, useState } from "react";
import { sendChatMessageStream } from "../services/chatApi";
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

const BrahmastraTerminal = ({ onStateChange }) => {
  const [mode, setMode] = useState("chat");
  const [status, setStatus] = useState("READY");
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [agentActivities, setAgentActivities] = useState([]);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const conversationIdRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const supportedMimeRef = useRef("");
  const messagesEndRef = useRef(null);
  const activityEndRef = useRef(null);

  useEffect(() => {
    supportedMimeRef.current = getSupportedMimeType();
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioPlayerRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    activityEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [agentActivities]);

  const updateStatus = (nextStatus) => {
    setStatus(nextStatus);
    onStateChange?.({ statusText: nextStatus, isProcessing: nextStatus !== "READY" });
  };

  const handleEvent = (event) => {
    if (event.type === 'status') {
      updateStatus(event.status);
      if (event.status !== "THINKING" && event.status !== "RESPONDING") {
        let text = `Status: ${event.status}`;
        if (event.tool) text += ` (Tool: ${event.tool})`;
        if (event.message) text = event.message;
        setAgentActivities(prev => [...prev, { time: new Date().toLocaleTimeString(), text }]);
      }
    } else if (event.type === 'activity') {
      let text = event.message || `Activity: ${event.activity_type}`;
      if (event.activity_type === 'tool_start') {
        text = `Executing tool: ${event.tool}\nInput: ${JSON.stringify(event.input, null, 2)}`;
      } else if (event.activity_type === 'tool_end') {
        text = `Tool ${event.tool} completed.\nResult: ${event.result}`;
      }
      setAgentActivities(prev => [...prev, { time: new Date().toLocaleTimeString(), text }]);
    }
  };

  const processQuery = async (query) => {
    if (!query.trim() || isLoading) return;
    
    setMessages(prev => [...prev, { role: "user", content: query }]);
    setAgentActivities([{ time: new Date().toLocaleTimeString(), text: "Received request" }]);
    setIsLoading(true);
    updateStatus("PROCESSING");
    
    try {
      const result = await sendChatMessageStream(query, conversationIdRef.current, handleEvent);
      conversationIdRef.current = result.conversationId;
      setAgentActivities(prev => [...prev, { time: new Date().toLocaleTimeString(), text: "Generated response" }]);
      setMessages(prev => [...prev, { role: "assistant", content: result.answer }]);
      updateStatus("READY");
      return result.answer;
    } catch (error) {
      setMessages(prev => [...prev, { role: "system", content: error.message || "An error occurred." }]);
      updateStatus("ERROR");
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const submitChat = async (event) => {
    event?.preventDefault();
    const query = chatInput;
    setChatInput("");
    await processQuery(query);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitChat(e);
    }
  };

  const startRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    audioPlayerRef.current?.pause();
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
    } catch {
      setIsRecording(false);
      updateStatus("ERROR");
      setMessages(prev => [...prev, { role: "system", content: "Microphone access failed." }]);
    }
  };

  const runVoicePipeline = async (audioBlob, mimeType) => {
    try {
      updateStatus("TRANSCRIBING");
      const transcript = (await transcribeAudio(audioBlob, mimeType)).trim();
      if (!transcript) throw new Error("Speech-to-text returned no transcript.");
      
      const answer = await processQuery(transcript);
      
      if (answer) {
        updateStatus("RESPONDING");
        const audioBlobResponse = await textToSpeech(answer.trim());
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
      }
    } catch (error) {
      updateStatus("ERROR");
      setMessages(prev => [...prev, { role: "system", content: error.message || "Voice pipeline failed." }]);
    }
  };

  const handleExampleClick = (query) => {
    setChatInput(query);
  };

  return (
    <div className="fixed bottom-3 left-0 right-0 z-50 flex justify-center px-4 w-full">
      <section className="relative flex max-h-[min(85vh,700px)] w-full max-w-4xl flex-col overflow-hidden border border-cyan-400/50 bg-black/90 shadow-[0_0_50px_rgba(0,255,255,0.15)] backdrop-blur-2xl rounded-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-purple-500/5 pointer-events-none" />
        <div className="relative z-10 flex min-h-0 flex-1 flex-col px-4 py-4 sm:px-6">
          
          <header className="flex items-center justify-between border-b border-cyan-400/20 pb-3 flex-shrink-0">
            <span className="font-mono text-xs font-bold tracking-[0.28em] text-cyan-300">BRAHMĀSTRA AI</span>
            <span className="font-mono text-[10px] tracking-[0.2em] text-cyan-200">STATUS: {status}</span>
          </header>

          <div className="flex justify-center gap-8 py-3 font-mono text-xs flex-shrink-0">
            <button type="button" onClick={() => setMode("talk")} className={mode === "talk" ? "text-cyan-300 transition-colors" : "text-white/45 hover:text-white/70 transition-colors"}>
              🎙️ TALK {mode === "talk" && <span className="ml-1">[ACTIVE]</span>}
            </button>
            <button type="button" onClick={() => setMode("chat")} className={mode === "chat" ? "text-cyan-300 transition-colors" : "text-white/45 hover:text-white/70 transition-colors"}>
              💬 CHAT {mode === "chat" && <span className="ml-1">[ACTIVE]</span>}
            </button>
          </div>

          <div className="flex-1 flex flex-col md:flex-row gap-4 min-h-0 overflow-hidden">
            
            {/* Conversation Area */}
            <div className="flex-1 flex flex-col min-w-0 border-r-0 md:border-r border-cyan-400/20 md:pr-4">
              <div className="flex-1 overflow-y-auto space-y-4 font-sans text-sm pr-2 pb-2">
                {messages.length === 0 && (
                  <div className="h-full flex flex-col items-center justify-center text-center opacity-70">
                    <p className="text-cyan-100/60 font-mono text-xs mb-4">How can I assist you?</p>
                    <div className="flex flex-wrap justify-center gap-2 max-w-sm">
                      <button onClick={() => handleExampleClick("Calculate 245 * 67")} className="px-3 py-1.5 text-xs font-mono border border-cyan-500/30 rounded bg-cyan-950/20 hover:bg-cyan-900/40 text-cyan-200">Calculate 245 * 67</button>
                      <button onClick={() => handleExampleClick("Search the web for latest React release")} className="px-3 py-1.5 text-xs font-mono border border-cyan-500/30 rounded bg-cyan-950/20 hover:bg-cyan-900/40 text-cyan-200">Search latest React</button>
                      <button onClick={() => handleExampleClick("Remember that my favorite color is blue")} className="px-3 py-1.5 text-xs font-mono border border-cyan-500/30 rounded bg-cyan-950/20 hover:bg-cyan-900/40 text-cyan-200">Remember preference</button>
                    </div>
                  </div>
                )}
                {messages.map((message, index) => (
                  <div key={index} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
                    <span className="font-mono text-[10px] text-white/40 mb-1">
                      {message.role === "user" ? "USER" : message.role === "assistant" ? "BRAHMĀSTRA" : "SYSTEM"}
                    </span>
                    <div className={`px-4 py-3 rounded-lg max-w-[90%] whitespace-pre-wrap break-words ${message.role === "user" ? "bg-cyan-900/30 border border-cyan-500/20 text-cyan-50" : message.role === "assistant" ? "bg-purple-900/20 border border-purple-500/20 text-purple-50" : "bg-red-900/30 border border-red-500/30 text-red-100"}`}>
                      {message.content}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex flex-col items-start">
                    <span className="font-mono text-[10px] text-white/40 mb-1">BRAHMĀSTRA</span>
                    <div className="px-4 py-3 rounded-lg bg-purple-900/20 border border-purple-500/20 text-purple-200/70 font-mono text-xs animate-pulse">
                      {status}...
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Agent Activity Timeline */}
            <div className="w-full md:w-64 flex flex-col flex-shrink-0 min-h-[150px] md:min-h-0 bg-black/40 rounded border border-white/5">
              <div className="px-3 py-2 border-b border-white/5 font-mono text-[10px] text-cyan-500/70 tracking-widest uppercase">
                Agent Activity
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-3 font-mono text-[10px]">
                {agentActivities.length === 0 && <div className="text-white/20 italic">Waiting for request...</div>}
                {agentActivities.map((act, i) => (
                  <div key={i} className="flex flex-col break-words">
                    <span className="text-cyan-400/40">{act.time}</span>
                    <span className="text-white/80 whitespace-pre-wrap">{act.text}</span>
                  </div>
                ))}
                <div ref={activityEndRef} />
              </div>
            </div>

          </div>

          <div className="mt-4 border-t border-cyan-400/20 pt-4 flex-shrink-0">
            {mode === "chat" ? (
              <form onSubmit={submitChat} className="flex gap-2">
                <textarea 
                  value={chatInput} 
                  onChange={(e) => setChatInput(e.target.value)} 
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Brahmastra anything... (Shift+Enter for newline)" 
                  disabled={isLoading} 
                  rows={2}
                  className="min-w-0 flex-1 rounded border border-white/15 bg-white/5 px-3 py-2 font-mono text-sm text-white outline-none focus:border-cyan-400 resize-none" 
                />
                <button type="submit" disabled={isLoading || !chatInput.trim()} className="rounded border border-cyan-400/60 px-6 py-2 font-mono text-xs text-cyan-200 disabled:opacity-40 hover:bg-cyan-900/30 transition-colors">
                  Send
                </button>
              </form>
            ) : (
              <button type="button" onClick={startRecording} disabled={isLoading} className={`w-full rounded border px-4 py-4 text-xs font-mono tracking-[0.18em] transition-colors ${isRecording ? "border-red-500/70 bg-red-900/20 text-red-300 hover:bg-red-900/30" : "border-cyan-400/50 bg-cyan-900/10 text-cyan-200 hover:bg-cyan-900/20"} disabled:opacity-40`}>
                {isRecording ? "🔴 STOP RECORDING" : "🎙️ START RECORDING"}
              </button>
            )}
          </div>

        </div>
      </section>
    </div>
  );
};

export default BrahmastraTerminal;