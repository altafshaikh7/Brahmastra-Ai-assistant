const logger = require("../utils/logger");

class AppError extends Error {
  constructor(message, statusCode) {
    super(message);
    this.statusCode = statusCode;
    this.status = `${statusCode}`.startsWith("4") ? "fail" : "error";
    this.isOperational = true;

    Error.captureStackTrace(this, this.constructor);
  }
}

const errorHandler = (err, req, res, next) => {
  err.statusCode = err.statusCode || 500;
  err.status = err.status || "error";

  logger.error(`[Error] ${err.statusCode} - ${err.message} - ${req.originalUrl} - ${req.method} - ${req.ip}`, {
    stack: err.stack
  });

  if (process.env.NODE_ENV === "development") {
    res.status(err.statusCode).json({
      success: false,
      status: err.status,
      error: err,
      message: err.message,
      stack: err.stack,
    });
  } else {
    // Production: Don't leak details
    if (err.isOperational) {
      res.status(err.statusCode).json({
        success: false,
        status: err.status,
        message: err.message,
      });
    } else {
      res.status(500).json({
        success: false,
        status: "error",
        message: "Something went wrong on our end.",
      });
    }
  }
};

module.exports = {
  AppError,
  errorHandler,
};
