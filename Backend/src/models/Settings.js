const mongoose = require("mongoose");

const SettingsSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    unique: true,
  },
  color: {
    type: String,
    default: "#0084ff",
  },
  size: {
    type: Number,
    default: 1.0,
  },
  sensitivity: {
    type: Number,
    default: 1.2,
  },
  isDragging: {
    type: Boolean,
    default: false,
  },
  position: {
    x: { type: Number, default: 0 },
    y: { type: Number, default: 0 }
  },
  updatedAt: {
    type: Date,
    default: Date.now,
  }
});

SettingsSchema.pre("save", function(next) {
  this.updatedAt = Date.now();
  next();
});

module.exports = mongoose.model("Settings", SettingsSchema);
