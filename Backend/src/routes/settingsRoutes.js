const express = require("express");
const settingsController = require("../controllers/settingsController");
const { apiLimiter } = require("../middleware/rateLimiter");
const { protect } = require("../middleware/authMiddleware");

const router = express.Router();

router.route("/")
  .get(protect, apiLimiter, settingsController.getSettings)
  .put(protect, apiLimiter, settingsController.updateSettings);

module.exports = router;
