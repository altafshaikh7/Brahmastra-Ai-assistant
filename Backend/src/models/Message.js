const mongoose = require("mongoose");

const MessageSchema = new mongoose.Schema({
  sender: {
    type: String,
    enum: ["user", "ai", "system"],
    required: true,
  },
  content: {
    type: String,
    required: true,
  },
  timestamp: {
    type: Date,
    default: Date.now,
  },
});

module.exports = {
  MessageSchema,
  Message: mongoose.model("Message", MessageSchema)
};
