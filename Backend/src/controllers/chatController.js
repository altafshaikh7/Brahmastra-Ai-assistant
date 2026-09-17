const Conversation = require("../models/Conversation");
const aiService = require("../services/aiService");
const { extractAndSaveMemories } = require("../services/memoryExtractor");
const logger = require("../utils/logger");
const mongoose = require("mongoose");

const MAX_MESSAGE_LENGTH = 10000;

/**
 * Send user query to LLM and record in conversation history
 */
const postChat = async (req, res, next) => {
  try {
    const { query, conversationId } = req.body;
    if (typeof query !== "string" || !query.trim()) {
      return res.status(400).json({ success: false, message: "Query is required" });
    }
    if (query.length > MAX_MESSAGE_LENGTH) {
      return res.status(413).json({ success: false, message: "Query is too long" });
    }

    const userId = req.user._id;

    let conversation;
    if (conversationId && !mongoose.Types.ObjectId.isValid(conversationId)) {
      return res.status(400).json({ success: false, message: "Invalid conversationId" });
    }

    if (conversationId) {
      conversation = await Conversation.findOne({ _id: conversationId, userId });
      if (!conversation) {
        return res.status(404).json({ success: false, message: "Conversation not found" });
      }
    }

    if (!conversation) {
      // Create new conversation
      const title = query.length > 30 ? `${query.substring(0, 30)}...` : query;
      conversation = new Conversation({
        userId,
        title: title,
        messages: [],
      });
    }

    // Append User Message
    const context = conversation.messages.map((message) => ({
      role: message.role || (message.sender === "ai" ? "assistant" : message.sender),
      content: message.content,
    }));

    conversation.messages.push({
      role: "user",
      content: query,
    });

    // The Node conversation id is the canonical id shared with Python-AI.
    const canonicalConversationId = String(conversation._id);

    // Extract the JWT from the Authorization header to forward to Python-AI
    // so the Agent Brain can call authenticated memory/document APIs on behalf of this user.
    const userToken = req.headers.authorization?.split(" ")[1] || null;

    // Forward to Python-AI orchestration (tool selection + execution handled there)
    let aiAnswer;
    try {
      aiAnswer = await aiService.generateChatResponse(query, canonicalConversationId, context, userToken);
    } catch (error) {
      if (error.isPythonAiError || error.message === aiService.PYTHON_AI_UNAVAILABLE_MSG) {
        return res.status(error.statusCode || 503).json({
          success: false,
          message: error.message || aiService.PYTHON_AI_UNAVAILABLE_MSG,
        });
      }
      throw error;
    }

    // Append AI Message
    conversation.messages.push({
      role: "assistant",
      content: aiAnswer,
    });

    await conversation.save();

    // Trigger asynchronous memory extraction (fire-and-forget, non-blocking)
    extractAndSaveMemories(userId, query).catch(err => 
      logger.warn("Non-blocking memory extraction failed:", err.message)
    );

    return res.status(200).json({
      success: true,
      data: {
        answer: aiAnswer,
        conversationId: canonicalConversationId,
      },
    });
  } catch (error) {
    logger.error("Error in postChat controller:", error);
    next(error);
  }
};

/**
 * Get all conversations for user
 */
const getConversations = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const conversations = await Conversation.find({ userId })
      .select("title messages createdAt updatedAt")
      .sort({ updatedAt: -1 });

    return res.status(200).json({
      success: true,
      data: conversations,
    });
  } catch (error) {
    logger.error("Error in getConversations controller:", error);
    next(error);
  }
};

/**
 * Delete a specific conversation
 */
const deleteConversation = async (req, res, next) => {
  try {
    const { id } = req.params;
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json({ success: false, message: "Invalid conversationId" });
    }
    const userId = req.user._id;

    const result = await Conversation.findOneAndDelete({ _id: id, userId });
    if (!result) {
      return res.status(404).json({
        success: false,
        message: "Conversation not found",
      });
    }

    logger.info(`Deleted conversation: ${id}`);
    return res.status(200).json({
      success: true,
      message: "Conversation deleted successfully",
    });
  } catch (error) {
    logger.error("Error in deleteConversation controller:", error);
    next(error);
  }
};

module.exports = {
  postChat,
  getConversations,
  deleteConversation,
};
