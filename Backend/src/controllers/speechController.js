const aiService = require("../services/aiService");
const ttsService = require("../services/ttsService");
const logger = require("../utils/logger");

/**
 * Handle speech to text audio file transcription
 * Groq Whisper supports: mp4, mpeg, mpga, m4a, wav, webm, ogg
 */
const postSpeechToText = async (req, res, next) => {
  try {
    if (!req.file) {
      logger.warn("[STT] No file received in 'audio' field");
      return res.status(400).json({
        success: false,
        message: "Audio file is required in 'audio' field",
      });
    }

    const { size, mimetype, originalname, buffer } = req.file;
    logger.info(`[STT Controller] Received audio upload:`);
    logger.info(`  ├─ Original Name: "${originalname}"`);
    logger.info(`  ├─ File Size:     ${size} bytes`);
    logger.info(`  └─ Content-Type:  "${mimetype}"`);

    // Minimum audio buffer size check (prevent sending empty or corrupted headers)
    if (size < 300) {
      logger.warn(`[STT Controller] Audio clip too small (${size}B < 300B)`);
      return res.status(400).json({
        success: false,
        message: "Audio clip is too short. Please speak clearly for at least 1 second.",
      });
    }

    // Map MIME type to correct file extension Groq Whisper expects
    const baseMime = (mimetype || "audio/webm").split(";")[0].trim().toLowerCase();
    const mimeToExt = {
      "audio/webm":  "recording.webm",
      "audio/ogg":   "recording.ogg",
      "audio/mp4":   "recording.mp4",
      "audio/mpeg":  "recording.mp3",
      "audio/wav":   "recording.wav",
      "audio/wave":  "recording.wav",
      "audio/x-wav": "recording.wav",
    };

    const correctedFilename = mimeToExt[baseMime] || originalname || "recording.webm";
    logger.info(`[STT Controller] Formatted filename for Whisper: "${correctedFilename}" (${baseMime})`);

    const transcript = await aiService.transcribeAudio(
      buffer,
      correctedFilename,
      baseMime
    );

    logger.info(`[STT Controller] Returning transcript to client: "${transcript}"`);

    return res.status(200).json({
      success: true,
      data: { transcript },
    });
  } catch (error) {
    logger.error(`[STT Controller Error] ${error.message}`);
    return res.status(500).json({
      success: false,
      message: error.message || "Speech transcription failed",
    });
  }
};

/**
 * Handle text to speech generation
 */
const postTextToSpeech = async (req, res, next) => {
  try {
    const { text, voice } = req.body;

    if (!text || text.trim().length === 0) {
      logger.warn("[TTS Controller] Empty text parameter");
      return res.status(400).json({
        success: false,
        message: "Text parameter is required for TTS",
      });
    }

    logger.info(`[TTS Controller] Received request: "${text.substring(0, 60)}..."`);

    const audioBuffer = await ttsService.generateSpeech(text.trim(), voice);

    logger.info(`[TTS Controller] Sending audio stream (${audioBuffer.length} bytes) to client`);

    res.set({
      "Content-Type": "audio/mpeg",
      "Content-Length": audioBuffer.length,
      "Accept-Ranges": "bytes",
      "Cache-Control": "no-cache",
    });

    return res.status(200).send(audioBuffer);
  } catch (error) {
    logger.error(`[TTS Controller Error] ${error.message}`);
    return res.status(500).json({
      success: false,
      message: error.message || "TTS synthesis failed",
    });
  }
};

module.exports = {
  postSpeechToText,
  postTextToSpeech,
};
