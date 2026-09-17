const express = require("express");
const chatController = require("../controllers/chatController");
const { apiLimiter } = require("../middleware/rateLimiter");
const { protect } = require("../middleware/authMiddleware");

const router = express.Router();

router.get("/", protect, apiLimiter, chatController.getConversations);
router.delete("/:id", protect, apiLimiter, chatController.deleteConversation);

module.exports = router;
