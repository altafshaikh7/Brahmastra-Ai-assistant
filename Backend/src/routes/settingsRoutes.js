const express = require("express");
const settingsController = require("../controllers/settingsController");
const { apiLimiter } = require("../middleware/rateLimiter");

const router = express.Router();

router.route("/")
  .get(apiLimiter, settingsController.getSettings)
  .put(apiLimiter, settingsController.updateSettings);

module.exports = router;
