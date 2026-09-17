const mongoose = require("mongoose");

const memorySchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    category: {
      type: String,
      enum: ["user_fact", "preference", "instruction", "project_context"],
      required: true,
      default: "user_fact",
    },
    content: {
      type: String,
      required: true,
      maxlength: 2000,
    },
    source: {
      type: String,
      enum: ["agent_extracted", "user_explicit"],
      default: "agent_extracted",
    },
    confidence: {
      type: Number,
      min: 0,
      max: 1,
      default: 0.8,
    },
  },
  {
    timestamps: true,
  }
);

// Compound index for efficient user-scoped queries
memorySchema.index({ userId: 1, category: 1 });
memorySchema.index({ userId: 1, updatedAt: -1 });

module.exports = mongoose.model("Memory", memorySchema);
