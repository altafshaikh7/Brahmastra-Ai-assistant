const mongoose = require("mongoose");

const documentChunkSchema = new mongoose.Schema({
  chunkIndex: { type: Number, required: true },
  content: { type: String, required: true },
  embedding: { type: [Number], default: [] },
  charStart: { type: Number, default: 0 },
  charEnd: { type: Number, default: 0 },
});

const documentSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      index: true,
    },
    filename: {
      type: String,
      required: true,
      maxlength: 255,
    },
    originalName: {
      type: String,
      required: true,
      maxlength: 255,
    },
    mimeType: {
      type: String,
      required: true,
      enum: ["text/plain", "text/markdown", "application/pdf"],
    },
    fileSize: {
      type: Number,
      required: true,
      max: 10 * 1024 * 1024, // 10MB limit
    },
    textContent: {
      type: String,
      default: "",
    },
    chunks: {
      type: [documentChunkSchema],
      default: [],
    },
    chunkSize: {
      type: Number,
      default: 500,
    },
    chunkOverlap: {
      type: Number,
      default: 100,
    },
    embeddingModel: {
      type: String,
      default: "",
    },
    embeddingDimension: {
      type: Number,
      default: 0,
    },
    status: {
      type: String,
      enum: ["pending", "processing", "ready", "error"],
      default: "pending",
    },
    errorMessage: {
      type: String,
      default: "",
    },
  },
  {
    timestamps: true,
  }
);

documentSchema.index({ userId: 1, status: 1 });
documentSchema.index({ userId: 1, createdAt: -1 });

module.exports = mongoose.model("Document", documentSchema);
