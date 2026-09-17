const Conversation = require("../models/Conversation");
const { getOrCreateDefaultUserAndSettings } = require("./settingsController");
const aiService = require("../services/aiService");
const logger = require("../utils/logger");

/**
 * Send user query to LLM and record in conversation history
 */
const postChat = async (req, res, next) => {
  try {
    const { query, conversationId } = req.body;
    if (!query) {
      return res.status(400).json({ success: false, message: "Query is required" });
    }

    const { user } = await getOrCreateDefaultUserAndSettings();

    let conversation;
    if (conversationId) {
      conversation = await Conversation.findOne({ _id: conversationId, userId: user._id });
    }

    if (!conversation) {
      // Create new conversation
      const title = query.length > 30 ? `${query.substring(0, 30)}...` : query;
      conversation = new Conversation({
        userId: user._id,
        title: title,
        messages: [],
      });
    }

    // Append User Message
    conversation.messages.push({
      sender: "user",
      content: query,
    });

    // The Node conversation id is the canonical id shared with Python-AI.
    const canonicalConversationId = String(conversation._id);

    // Forward to Python-AI orchestration (tool selection + execution handled there)
    let aiAnswer;
    try {
      aiAnswer = await aiService.generateChatResponse(query, canonicalConversationId);
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
      sender: "ai",
      content: aiAnswer,
    });

    await conversation.save();

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
 * Get all conversations for default user
 */
const getConversations = async (req, res, next) => {
  try {
    const { user } = await getOrCreateDefaultUserAndSettings();
    const conversations = await Conversation.find({ userId: user._id })
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
    const { user } = await getOrCreateDefaultUserAndSettings();

    const result = await Conversation.findOneAndDelete({ _id: id, userId: user._id });
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
