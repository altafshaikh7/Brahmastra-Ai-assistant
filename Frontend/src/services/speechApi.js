import api from "./api";

/**
 * Map MIME type to clean filename extension for Whisper API.
 */
const mimeToFilename = (mimeType) => {
  const base = (mimeType || "").split(";")[0].trim().toLowerCase();
  const map = {
    "audio/webm":  "recording.webm",
    "audio/ogg":   "recording.ogg",
    "audio/mp4":   "recording.mp4",
    "audio/mpeg":  "recording.mp3",
    "audio/wav":   "recording.wav",
    "audio/wave":  "recording.wav",
    "audio/flac":  "recording.flac",
  };
  return map[base] || "recording.webm";
};

/**
 * Send audio Blob to backend for transcription.
 * @param {Blob} audioBlob - Audio recording from MediaRecorder
 * @param {string} [mimeType] - MIME type of the audio recording
 * @returns {Promise<string>} Transcript text from Groq Whisper
 */
export const transcribeAudio = async (audioBlob, mimeType) => {
  const resolvedMime = mimeType || audioBlob.type || "audio/webm";
  const cleanMime = resolvedMime.split(";")[0].trim().toLowerCase();
  const filename = mimeToFilename(cleanMime);

  console.log(`[speechApi.js] Preparing STT Upload:`);
  console.log(`  ├─ Blob Size:    ${audioBlob.size} bytes`);
  console.log(`  ├─ Raw MimeType: "${resolvedMime}"`);
  console.log(`  ├─ Clean Mime:   "${cleanMime}"`);
  console.log(`  └─ Filename:     "${filename}"`);

  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  try {
    const response = await api.post("/api/speech-to-text", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 35000,
    });

    console.log(`[speechApi.js] STT Response Status: ${response.status} OK`);
    console.log(`[speechApi.js] STT Payload:`, response.data);

    const transcript = response.data?.data?.transcript || "";
    console.log(`[speechApi.js] Final Transcript: "${transcript}"`);
    return transcript;
  } catch (error) {
    if (error.response) {
      console.error(`[speechApi.js Error] Server responded with HTTP ${error.response.status}:`, error.response.data);
    } else {
      console.error(`[speechApi.js Error] Request failed:`, error.message);
    }
    throw error;
  }
};
