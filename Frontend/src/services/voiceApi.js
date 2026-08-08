import api from "./api";

/**
 * Convert text to speech audio via backend.
 * @param {string} text - Text to synthesize
 * @param {string} [voice] - Voice name (for OpenAI TTS)
 * @returns {Promise<Blob>} MP3 audio blob ready for playback
 */
export const textToSpeech = async (text, voice = "alloy") => {
  console.log(`[voiceApi] Requesting TTS for: "${text.substring(0, 60)}..."`);

  const response = await api.post(
    "/api/text-to-speech",
    { text, voice },
    {
      responseType: "blob",
      timeout: 30000,
    }
  );

  const blob = response.data;
  console.log(`[voiceApi] Received audio blob: ${blob.size}B, type=${blob.type}`);

  if (blob.size < 100) {
    throw new Error("TTS returned empty or invalid audio data");
  }

  // Ensure it's typed as audio/mpeg for browser playback
  if (blob.type && blob.type !== "audio/mpeg") {
    return new Blob([blob], { type: "audio/mpeg" });
  }

  return blob;
};
