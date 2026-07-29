const express = require("express");
const chatController = require("../controllers/chatController");
const { apiLimiter } = require("../middleware/rateLimiter");

const router = express.Router();

router.get("/", apiLimiter, chatController.getConversations);
router.delete("/:id", apiLimiter, chatController.deleteConversation);

module.exports = router;
