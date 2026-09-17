const express = require("express");
const chatController = require("../controllers/chatController");
const { apiLimiter } = require("../middleware/rateLimiter");
const { protect } = require("../middleware/authMiddleware");

const router = express.Router();

router.post("/", protect, apiLimiter, chatController.postChat);

module.exports = router;
