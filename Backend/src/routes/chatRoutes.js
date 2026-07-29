const express = require("express");
const chatController = require("../controllers/chatController");
const { apiLimiter } = require("../middleware/rateLimiter");

const router = express.Router();

router.post("/", apiLimiter, chatController.postChat);

module.exports = router;
