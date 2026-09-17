const mongoose = require("mongoose");

const MessageSchema = new mongoose.Schema({
  role: {
    type: String,
    enum: ["user", "assistant", "tool", "system"],
    required: true,
    default: function() {
      if (this.sender === "ai") return "assistant";
      return this.sender || "user";
    },
  },
  // Legacy read compatibility for conversations created before role was canonical.
  sender: {
    type: String,
    enum: ["user", "ai", "assistant", "tool", "system"],
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

MessageSchema.set("toJSON", {
  transform: (_doc, ret) => {
    delete ret.__v;
    return ret;
  },
});

module.exports = {
  MessageSchema,
  Message: mongoose.model("Message", MessageSchema)
};
