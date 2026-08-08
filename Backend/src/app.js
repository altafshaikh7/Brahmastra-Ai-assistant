const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const compression = require("compression");
const morgan = require("morgan");
require("dotenv").config();

const logger = require("./utils/logger");
const { errorHandler } = require("./middleware/errorMiddleware");

// Routes
const settingsRoutes = require("./routes/settingsRoutes");
const chatRoutes = require("./routes/chatRoutes");
const conversationRoutes = require("./routes/conversationRoutes");
const speechRoutes = require("./routes/speechRoutes");

const app = express();

// Security Middlewares
app.use(helmet());
app.use(compression());
app.use(cors());

// Body Parsers
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// HTTP request logging mapped to Winston stream
const morganFormat = process.env.NODE_ENV === "production" ? "combined" : "dev";
app.use(
  morgan(morganFormat, {
    stream: {
      write: (message) => logger.info(message.trim()),
    },
  })
);

// Health Check Route
app.get("/health", (req, res) => {
  res.status(200).json({
    success: true,
    status: "UP",
    message: "BRAHMASTRA AI Backend is fully operational 🚀",
    timestamp: new Date(),
  });
});

// Mounting API routes
app.use("/api/settings", settingsRoutes);
app.use("/api/chat", chatRoutes);
app.use("/api/conversations", conversationRoutes);
app.use("/api", speechRoutes); // exposes /api/speech-to-text and /api/text-to-speech

// 404 Route handler
app.use((req, res, next) => {
  const error = new Error(`Not Found - ${req.originalUrl}`);
  error.statusCode = 404;
  next(error);
});

// Centralized Error Handler Middleware
app.use(errorHandler);

module.exports = app;