const mongoose = require("mongoose");

const VoiceProfileSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    unique: true,
  },
  voiceName: {
    type: String,
    default: "Google US English",
  },
  pitch: {
    type: Number,
    default: 0.9,
  },
  rate: {
    type: Number,
    default: 1.05,
  },
  volume: {
    type: Number,
    default: 1.0,
  },
  updatedAt: {
    type: Date,
    default: Date.now,
  },
});

VoiceProfileSchema.pre("save", function(next) {
  this.updatedAt = Date.now();
  next();
});

module.exports = mongoose.model("VoiceProfile", VoiceProfileSchema);
