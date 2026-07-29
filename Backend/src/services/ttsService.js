const axios = require("axios");
const logger = require("../utils/logger");

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const GOOGLE_TTS_MAX_CHARS = 200; // Google Translate TTS limit per request

/**
 * Split text into chunks under the Google TTS character limit
 */
const splitIntoChunks = (text, maxLen = GOOGLE_TTS_MAX_CHARS) => {
  const sentences = text.match(/[^.!?]+[.!?]*/g) || [text];
  const chunks = [];
  let current = "";

  for (const sentence of sentences) {
    if ((current + sentence).length <= maxLen) {
      current += sentence;
    } else {
      if (current) chunks.push(current.trim());
      // If a single sentence exceeds limit, hard-split it
      if (sentence.length > maxLen) {
        const words = sentence.split(" ");
        let part = "";
        for (const word of words) {
          if ((part + " " + word).trim().length <= maxLen) {
            part = (part + " " + word).trim();
          } else {
            if (part) chunks.push(part);
            part = word;
          }
        }
        if (part) current = part;
      } else {
        current = sentence;
      }
    }
  }
  if (current) chunks.push(current.trim());
  return chunks.filter(Boolean);
};

/**
 * Fetch a single TTS chunk from Google Translate
 */
const fetchGoogleTTSChunk = async (text) => {
  const url = `https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q=${encodeURIComponent(text)}`;
  const response = await axios.get(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://translate.google.com/",
      "Accept": "audio/mpeg, */*",
    },
    responseType: "arraybuffer",
    timeout: 10000,
  });
  return Buffer.from(response.data);
};

/**
 * Generate Speech Audio from Text.
 * Priority:
 *   1. OpenAI TTS (if OPENAI_API_KEY set)
 *   2. Google Translate TTS chunked (free fallback)
 * Returns a Buffer of mp3 audio data.
 */
const generateSpeech = async (text, voice = "alloy") => {
  try {
    logger.info(`[TTS] Synthesizing ${text.length} chars`);

    // --- 1. OpenAI TTS (best quality) ---
    if (OPENAI_API_KEY) {
      logger.info("[TTS] Using OpenAI TTS");
      const response = await axios.post(
        "https://api.openai.com/v1/audio/speech",
        { model: "tts-1", input: text, voice },
        {
          headers: {
            Authorization: `Bearer ${OPENAI_API_KEY}`,
            "Content-Type": "application/json",
          },
          responseType: "arraybuffer",
          timeout: 30000,
        }
      );
      logger.info(`[TTS] OpenAI returned ${response.data.byteLength} bytes`);
      return Buffer.from(response.data);
    }

    // --- 2. Google Translate TTS (chunked free fallback) ---
    logger.info("[TTS] Using Google Translate TTS (chunked)");
    const chunks = splitIntoChunks(text);
    logger.info(`[TTS] Split into ${chunks.length} chunk(s)`);

    const audioChunks = [];
    for (let i = 0; i < chunks.length; i++) {
      logger.info(`[TTS] Fetching chunk ${i + 1}/${chunks.length}: "${chunks[i].substring(0, 40)}..."`);
      try {
        const chunkBuf = await fetchGoogleTTSChunk(chunks[i]);
        if (chunkBuf.length > 100) {
          audioChunks.push(chunkBuf);
        }
      } catch (chunkErr) {
        logger.warn(`[TTS] Chunk ${i + 1} failed: ${chunkErr.message} — skipping`);
      }
    }

    if (audioChunks.length === 0) {
      throw new Error("All TTS chunks failed");
    }

    const combined = Buffer.concat(audioChunks);
    logger.info(`[TTS] Combined audio: ${combined.length} bytes`);
    return combined;
  } catch (error) {
    logger.error("[TTS] generateSpeech error:", error.message);
    throw new Error(error.message || "Text-to-Speech synthesis failed");
  }
};

module.exports = { generateSpeech };
