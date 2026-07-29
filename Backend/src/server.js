require("dotenv").config();

const app = require("./app");
const connectDB = require("./config/db");

const DEFAULT_PORT = parseInt(process.env.PORT, 10) || 5000;

// Connect Database
connectDB();

const startServer = (port) => {
  const server = app.listen(port, () => {
    console.log(`🚀 Server running on http://localhost:${port}`);
  });

  server.on("error", (err) => {
    if (err.code === "EADDRINUSE") {
      console.warn(`⚠️ Port ${port} is currently in use. Attempting port ${port + 1}...`);
      setTimeout(() => {
        startServer(port + 1);
      }, 500);
    } else {
      console.error("❌ Server error:", err);
      process.exit(1);
    }
  });

  // Graceful shutdown handling
  const handleShutdown = (signal) => {
    console.log(`\n🛑 Received ${signal}. Closing HTTP server gracefully...`);
    server.close(() => {
      console.log("✅ HTTP server closed.");
      process.exit(0);
    });
  };

  process.once("SIGINT", () => handleShutdown("SIGINT"));
  process.once("SIGTERM", () => handleShutdown("SIGTERM"));
};

startServer(DEFAULT_PORT);