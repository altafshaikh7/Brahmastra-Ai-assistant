const User = require("../models/User");
const Settings = require("../models/Settings");
const logger = require("../utils/logger");

// Helper to get or create default user and settings
const getOrCreateDefaultUserAndSettings = async () => {
  let user = await User.findOne();
  if (!user) {
    user = await User.create({ name: "Default User" });
    logger.info(`Seeded default user: ${user._id}`);
  }
  let settings = await Settings.findOne({ userId: user._id });
  if (!settings) {
    settings = await Settings.create({
      userId: user._id,
      color: "#0084ff",
      size: 1.0,
      sensitivity: 1.2,
      isDragging: false,
      position: { x: 0, y: 0 }
    });
    logger.info(`Seeded default settings for user: ${user._id}`);
  }
  return { user, settings };
};

/**
 * Get visualizer settings
 */
const getSettings = async (req, res, next) => {
  try {
    const { settings } = await getOrCreateDefaultUserAndSettings();
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
    const { user } = await getOrCreateDefaultUserAndSettings();
    const { color, size, sensitivity, isDragging, position } = req.body;

    const updatedSettings = await Settings.findOneAndUpdate(
      { userId: user._id },
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

    logger.info(`Updated settings for user: ${user._id}`);
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
  getOrCreateDefaultUserAndSettings,
};
