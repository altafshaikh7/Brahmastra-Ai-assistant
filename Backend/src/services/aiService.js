const axios = require("axios");
const FormData = require("form-data");
const logger = require("../utils/logger");

const GROQ_API_KEY = process.env.GROQ_API_KEY;
if (!GROQ_API_KEY) {
  throw new Error("GROQ_API_KEY is missing");
}
const GROQ_BASE_URL = "https://api.groq.com/openai/v1";

/**
 * Transcribe audio buffer using Groq Whisper API.
 * Groq supports: flac, mp3, mp4, mpeg, mpga, m4a, ogg, opus, wav, webm
 *
 * @param {Buffer} fileBuffer
 * @param {string} filename  - Must have a valid extension (.webm, .wav, etc.)
 * @param {string} mimeType  - e.g. "audio/webm"
 * @returns {Promise<string>} Transcript text
 */
const transcribeAudio = async (fileBuffer, filename, mimeType) => {
  // Clean mimeType to avoid header parsing issues (e.g., strip ';codecs=opus')
  const cleanMime = (mimeType || "audio/webm").split(";")[0].trim().toLowerCase();
  
  logger.info(`[STT DEBUG] Calling Whisper API:`);
  logger.info(`  ├─ Filename:   ${filename}`);
  logger.info(`  ├─ Clean MIME: ${cleanMime}`);
  logger.info(`  └─ Buffer:     ${fileBuffer.length} bytes`);

  const formData = new FormData();

  formData.append("file", fileBuffer, {
    filename: filename,
    contentType: cleanMime,
    knownLength: fileBuffer.length,
  });
  formData.append("model", "whisper-large-v3");
  formData.append("temperature", "0");
  formData.append("prompt", "Brahmastra. Hello, thank you. This is an English, Hindi and Urdu conversation.");
  formData.append("response_format", "json");

  try {
    const startTime = Date.now();
    const response = await axios.post(
      `${GROQ_BASE_URL}/audio/transcriptions`,
      formData,
      {
        headers: {
          ...formData.getHeaders(),
          Authorization: `Bearer ${GROQ_API_KEY}`,
        },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 30000,
      }
    );

    const duration = Date.now() - startTime;
    logger.info(`[Whisper API Response OK] (${duration}ms):`);
    logger.info(`  └─ Raw Response Data: ${JSON.stringify(response.data)}`);

    const transcript = (response.data?.text || "").trim();
    logger.info(`[Whisper Final Transcript]: "${transcript}"`);
    return transcript;
  } catch (error) {
    if (error.response) {
      logger.error(`[Whisper API HTTP Error] Status: ${error.response.status}`);
      logger.error(`  └─ Response Body: ${JSON.stringify(error.response.data)}`);
    } else {
      logger.error(`[Whisper Network/Request Error]: ${error.message}`);
    }
    const errMsg = error.response?.data?.error?.message || error.message || "Whisper transcription failed";
    throw new Error(errMsg);
  }
};

/**
 * Generate chat response from Groq LLM.
 * @param {Array} messages - OpenAI-format message array
 * @param {string} model
 * @returns {Promise<string>} AI reply text
 */
const generateChatResponse = async (messages, model = "llama-3.1-8b-instant") => {
  const lastUserMsg = messages[messages.length - 1]?.content || "";
  logger.info(`[Chat Request] Model: ${model}, Messages: ${messages.length}`);
  logger.info(`  └─ User Query: "${lastUserMsg}"`);

  try {
    const startTime = Date.now();
    const response = await axios.post(
      `${GROQ_BASE_URL}/chat/completions`,
      {
        model,
        messages,
        temperature: 0.6,
        max_tokens: 80,
      },
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${GROQ_API_KEY}`,
        },
        timeout: 20000,
      }
    );

    const duration = Date.now() - startTime;
    const answer = response.data.choices[0].message.content.trim();
    logger.info(`[Chat Response OK] (${duration}ms): "${answer}"`);
    return answer;
  } catch (error) {
    if (error.response) {
      logger.error(`[Chat API Error] Status: ${error.response.status}, Body: ${JSON.stringify(error.response.data)}`);
    } else {
      logger.error(`[Chat Request Error]: ${error.message}`);
    }
    const errMsg = error.response?.data?.error?.message || error.message || "LLM completion failed";
    throw new Error(errMsg);
  }
};

module.exports = { transcribeAudio, generateChatResponse };
