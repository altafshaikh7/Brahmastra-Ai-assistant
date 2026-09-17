const axios = require("axios");
const FormData = require("form-data");
const logger = require("../utils/logger");

const GROQ_BASE_URL = "https://api.groq.com/openai/v1";
const PYTHON_AI_URL = (process.env.PYTHON_AI_URL || "http://localhost:8000").replace(/\/$/, "");
const PYTHON_AI_TIMEOUT_MS = parseInt(process.env.PYTHON_AI_TIMEOUT_MS, 10) || 120000;
const PYTHON_AI_API_KEY = process.env.PYTHON_AI_API_KEY;
const PYTHON_AI_UNAVAILABLE_MSG = "Brahmastra AI service is temporarily unavailable.";

class PythonAiError extends Error {
  constructor(message, statusCode = 503) {
    super(message);
    this.name = "PythonAiError";
    this.statusCode = statusCode;
    this.isPythonAiError = true;
  }
}

const getGroqApiKey = () => {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error("GROQ_API_KEY is missing");
  }
  return apiKey;
};

/**
 * Extract the latest user message from an OpenAI-style messages array or plain string.
 * @param {string|Array<{role: string, content: string}>} messages
 * @returns {string}
 */
const extractUserMessage = (messages) => {
  if (typeof messages === "string") {
    return messages.trim();
  }

  if (!Array.isArray(messages) || messages.length === 0) {
    return "";
  }

  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    if (msg?.role === "user" && typeof msg.content === "string" && msg.content.trim()) {
      return msg.content.trim();
    }
  }

  return "";
};

/**
 * Parse a Python-AI /ai/chat response payload.
 * @param {object} data
 * @returns {string}
 */
const parsePythonAiChatResponse = (data) => {
  if (!data || data.success !== true || typeof data.response !== "string") {
    throw new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
  }

  const answer = data.response.trim();
  if (!answer) {
    throw new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
  }

  return answer;
};

/**
 * Map axios / network errors from Python-AI into safe user-facing errors.
 * Never exposes secrets or raw upstream payloads.
 * @param {Error} error
 * @returns {Error}
 */
const mapPythonAiError = (error) => {
  if (error.code === "ECONNREFUSED" || error.code === "ENOTFOUND" || error.code === "ECONNABORTED") {
    return new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
  }

  if (error.response) {
    const status = error.response.status;
    logger.error("[Python-AI HTTP Error]", {
      status,
      path: "/ai/chat",
    });

    if (status >= 500 || status === 429 || status === 503) {
      return new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
    }

    const detail = error.response.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return new PythonAiError(detail.trim(), status || 502);
    }

    if (typeof error.response.data?.message === "string" && error.response.data.message.trim()) {
      return new PythonAiError(error.response.data.message.trim(), status || 502);
    }

    return new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
  }

  logger.error("[Python-AI Request Error]", { message: error.message });
  return new PythonAiError(PYTHON_AI_UNAVAILABLE_MSG, 503);
};

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
  const cleanMime = (mimeType || "audio/webm").split(";")[0].trim().toLowerCase();

  logger.info("[STT] Calling Whisper API", {
    filename,
    mimeType: cleanMime,
    bytes: fileBuffer.length,
  });

  const formData = new FormData();

  formData.append("file", fileBuffer, {
    filename,
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
          Authorization: `Bearer ${getGroqApiKey()}`,
        },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 30000,
      }
    );

    const duration = Date.now() - startTime;
    logger.info("[Whisper API Response OK]", { durationMs: duration });

    const transcript = (response.data?.text || "").trim();
    logger.info("[Whisper Final Transcript]", { transcriptLength: transcript.length });
    return transcript;
  } catch (error) {
    if (error.response) {
      logger.error("[Whisper API HTTP Error]", { status: error.response.status });
    } else {
      logger.error("[Whisper Network/Request Error]", { message: error.message });
    }
    const errMsg = error.response?.data?.error?.message || error.message || "Whisper transcription failed";
    throw new Error(errMsg);
  }
};

/**
 * Generate chat response via Python-AI orchestration layer.
 * @param {string|Array<{role: string, content: string}>} messages - User query or OpenAI-format history
 * @param {string|null} [conversationId] - Optional Python-AI conversation id
 * @returns {Promise<string>} AI reply text
 */
const generateChatResponse = async (messages, conversationId = null) => {
  const userMessage = extractUserMessage(messages);
  if (!userMessage) {
    throw new Error("User message is required");
  }

  logger.info("[Chat Request] Forwarding to Python-AI", {
    pythonAiUrl: PYTHON_AI_URL,
    messageLength: userMessage.length,
    hasConversationId: Boolean(conversationId),
  });

  const payload = { message: userMessage };
  if (conversationId) {
    payload.conversation_id = conversationId;
  }

  try {
    const startTime = Date.now();
    const response = await axios.post(`${PYTHON_AI_URL}/ai/chat`, payload, {
      headers: {
        "Content-Type": "application/json",
        ...(PYTHON_AI_API_KEY ? { "X-Internal-API-Key": PYTHON_AI_API_KEY } : {}),
      },
      timeout: PYTHON_AI_TIMEOUT_MS,
      validateStatus: () => true,
    });

    const duration = Date.now() - startTime;

    if (response.status >= 400) {
      throw mapPythonAiError({ response });
    }

    const answer = parsePythonAiChatResponse(response.data);
    logger.info("[Chat Response OK]", {
      durationMs: duration,
      provider: response.data?.provider,
      model: response.data?.model,
      answerLength: answer.length,
    });
    return answer;
  } catch (error) {
    if (error.isPythonAiError) {
      throw error;
    }

    if (
      error.message === PYTHON_AI_UNAVAILABLE_MSG ||
      error.message === "User message is required"
    ) {
      throw error;
    }
    throw mapPythonAiError(error);
  }
};

module.exports = {
  transcribeAudio,
  generateChatResponse,
  extractUserMessage,
  parsePythonAiChatResponse,
  mapPythonAiError,
  PYTHON_AI_UNAVAILABLE_MSG,
  PythonAiError,
};
