const Settings = require("../models/Settings");
const logger = require("../utils/logger");

/**
 * Get visualizer settings
 */
const getSettings = async (req, res, next) => {
  try {
    const userId = req.user._id;
    let settings = await Settings.findOne({ userId });

    if (!settings) {
      settings = await Settings.create({
        userId,
        color: "#0084ff",
        size: 1.0,
        sensitivity: 1.2,
        isDragging: false,
        position: { x: 0, y: 0 }
      });
      logger.info(`Seeded default settings for user: ${userId}`);
    }

    return res.status(200).json({
      success: true,
      data: settings,
    });
  } catch (error) {
    logger.error("Error in getSettings controller:", error);
    next(error);
  }
};

/**
 * Update visualizer settings
 */
const updateSettings = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { color, size, sensitivity, isDragging, position } = req.body;

    const updatedSettings = await Settings.findOneAndUpdate(
      { userId },
      {
        $set: {
          color,
          size,
          sensitivity,
          isDragging,
          position,
        },
      },
      { new: true, runValidators: true }
    );

    if (!updatedSettings) {
      return res.status(404).json({ success: false, message: "Settings not found" });
    }

    logger.info(`Updated settings for user: ${userId}`);
    return res.status(200).json({
      success: true,
      data: updatedSettings,
    });
  } catch (error) {
    logger.error("Error in updateSettings controller:", error);
    next(error);
  }
};

module.exports = {
  getSettings,
  updateSettings,
};
