const jwt = require("jsonwebtoken");
const User = require("../models/User");
const Settings = require("../models/Settings");
const logger = require("../utils/logger");

const generateToken = (id) => {
  return jwt.sign({ id }, process.env.JWT_SECRET || "default_jwt_secret", {
    expiresIn: process.env.JWT_EXPIRES_IN || "7d",
  });
};

/**
 * Register user
 */
const register = async (req, res, next) => {
  try {
    const { name, email, password } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ success: false, message: "Please provide all required fields" });
    }

    const userExists = await User.findOne({ email });

    if (userExists) {
      return res.status(400).json({ success: false, message: "User already exists" });
    }

    const user = await User.create({
      name,
      email,
      password,
    });

    if (user) {
      // Seed default settings for the new user
      await Settings.create({
        userId: user._id,
        color: "#0084ff",
        size: 1.0,
        sensitivity: 1.2,
        isDragging: false,
        position: { x: 0, y: 0 },
      });

      logger.info(`User registered: ${user._id}`);
      res.status(201).json({
        success: true,
        data: {
          _id: user._id,
          name: user.name,
          email: user.email,
          token: generateToken(user._id),
        },
      });
    } else {
      res.status(400).json({ success: false, message: "Invalid user data" });
    }
  } catch (error) {
    logger.error("Error in register controller:", error);
    next(error);
  }
};

/**
 * Login user
 */
const login = async (req, res, next) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ success: false, message: "Please provide email and password" });
    }

    // Check for user and include password in the query result
    const user = await User.findOne({ email }).select("+password");

    if (user && (await user.comparePassword(password))) {
      logger.info(`User logged in: ${user._id}`);
      res.status(200).json({
        success: true,
        data: {
          _id: user._id,
          name: user.name,
          email: user.email,
          token: generateToken(user._id),
        },
      });
    } else {
      res.status(401).json({ success: false, message: "Invalid credentials" });
    }
  } catch (error) {
    logger.error("Error in login controller:", error);
    next(error);
  }
};

/**
 * Get current user profile
 */
const getMe = async (req, res, next) => {
  try {
    const user = await User.findById(req.user._id);

    if (user) {
      res.status(200).json({
        success: true,
        data: {
          _id: user._id,
          name: user.name,
          email: user.email,
        },
      });
    } else {
      res.status(404).json({ success: false, message: "User not found" });
    }
  } catch (error) {
    logger.error("Error in getMe controller:", error);
    next(error);
  }
};

/**
 * Logout user
 */
const logout = async (req, res, next) => {
  try {
    res.status(200).json({ success: true, message: "User logged out successfully" });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  register,
  login,
  getMe,
  logout,
};
