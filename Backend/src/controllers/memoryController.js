const Memory = require("../models/Memory");
const logger = require("../utils/logger");
const mongoose = require("mongoose");

// Secrets/sensitive patterns to filter out
const SENSITIVE_PATTERNS = [
  /\b[A-Za-z0-9+/]{32,}={0,2}\b/,       // Base64 tokens
  /\bpassword\s*[:=]\s*\S+/i,
  /\b(api[_-]?key|secret[_-]?key|access[_-]?token|jwt|bearer)\s*[:=]\s*\S+/i,
  /\bsk-[a-zA-Z0-9]{20,}/,               // OpenAI-style keys
  /\bgsk_[a-zA-Z0-9]{20,}/,              // Groq-style keys
  /\beyJ[a-zA-Z0-9_-]{10,}/,             // JWT tokens
];

const containsSensitiveData = (content) => {
  return SENSITIVE_PATTERNS.some((pattern) => pattern.test(content));
};

/**
 * Create a memory entry
 */
const createMemory = async (req, res, next) => {
  try {
    const { content, category, source, confidence } = req.body;
    const userId = req.user._id;

    if (!content || typeof content !== "string" || !content.trim()) {
      return res.status(400).json({ success: false, message: "Content is required" });
    }

    if (content.length > 2000) {
      return res.status(400).json({ success: false, message: "Content too long (max 2000 chars)" });
    }

    if (containsSensitiveData(content)) {
      return res.status(400).json({
        success: false,
        message: "Memory content appears to contain sensitive data (passwords, keys, tokens). Storing rejected.",
      });
    }

    // Check for duplicate/similar existing memory
    const existing = await Memory.findOne({
      userId,
      content: content.trim(),
    });

    if (existing) {
      // Update existing memory instead of creating duplicate
      existing.confidence = confidence || existing.confidence;
      existing.category = category || existing.category;
      await existing.save();
      return res.status(200).json({ success: true, data: existing, updated: true });
    }

    const memory = await Memory.create({
      userId,
      content: content.trim(),
      category: category || "user_fact",
      source: source || "agent_extracted",
      confidence: confidence || 0.8,
    });

    logger.info(`Memory created for user ${userId}: ${memory._id}`);
    return res.status(201).json({ success: true, data: memory });
  } catch (error) {
    logger.error("Error in createMemory:", error);
    next(error);
  }
};

/**
 * Get all memories for user, optionally filtered by category
 */
const getMemories = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { category, query, limit } = req.query;

    const filter = { userId };
    if (category) {
      filter.category = category;
    }

    let memories;
    if (query && typeof query === "string" && query.trim()) {
      // In the absence of a vector index, we return the most recent memories
      // so the Agent Brain can extract relevant facts from the context.
      memories = await Memory.find(filter)
        .sort({ updatedAt: -1 })
        .limit(Math.min(parseInt(limit) || 10, 50));
    } else {
      memories = await Memory.find(filter)
        .sort({ updatedAt: -1 })
        .limit(Math.min(parseInt(limit) || 50, 100));
    }

    return res.status(200).json({ success: true, data: memories });
  } catch (error) {
    logger.error("Error in getMemories:", error);
    next(error);
  }
};

/**
 * Update a memory entry
 */
const updateMemory = async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user._id;
    const { content, category, confidence } = req.body;

    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json({ success: false, message: "Invalid memory ID" });
    }

    if (content && containsSensitiveData(content)) {
      return res.status(400).json({
        success: false,
        message: "Memory content appears to contain sensitive data. Update rejected.",
      });
    }

    const memory = await Memory.findOne({ _id: id, userId });
    if (!memory) {
      return res.status(404).json({ success: false, message: "Memory not found" });
    }

    if (content) memory.content = content.trim();
    if (category) memory.category = category;
    if (confidence !== undefined) memory.confidence = confidence;

    await memory.save();
    logger.info(`Memory updated: ${id}`);
    return res.status(200).json({ success: true, data: memory });
  } catch (error) {
    logger.error("Error in updateMemory:", error);
    next(error);
  }
};

/**
 * Delete a memory entry
 */
const deleteMemory = async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user._id;

    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json({ success: false, message: "Invalid memory ID" });
    }

    const result = await Memory.findOneAndDelete({ _id: id, userId });
    if (!result) {
      return res.status(404).json({ success: false, message: "Memory not found" });
    }

    logger.info(`Memory deleted: ${id}`);
    return res.status(200).json({ success: true, message: "Memory deleted" });
  } catch (error) {
    logger.error("Error in deleteMemory:", error);
    next(error);
  }
};

module.exports = {
  createMemory,
  getMemories,
  updateMemory,
  deleteMemory,
  containsSensitiveData,
};
