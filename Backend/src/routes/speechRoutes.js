const express = require("express");
const multer = require("multer");
const speechController = require("../controllers/speechController");
const { speechLimiter } = require("../middleware/rateLimiter");
const { protect } = require("../middleware/authMiddleware");

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 15 * 1024 * 1024, // 15MB limit
  },
});

router.post("/speech-to-text", protect, speechLimiter, upload.single("audio"), speechController.postSpeechToText);
router.post("/text-to-speech", protect, speechLimiter, speechController.postTextToSpeech);

module.exports = router;
