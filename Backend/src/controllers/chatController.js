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

    // Prepare history context for Groq
    const systemPrompt = {
      role: "system",
      content: "You are BRAHMASTRA AI, a high-end virtual assistant. Be extremely concise (max 15 words). No markdown. Respond in the exact language the user spoke (English for English, Hindi for Hindi, Urdu for Urdu). If ambiguous, default to English.",
    };

    // Get last 10 messages for context window
    const recentMessages = conversation.messages.slice(-10).map((msg) => ({
      role: msg.sender === "ai" ? "assistant" : "user",
      content: msg.content,
    }));

    const apiMessages = [systemPrompt, ...recentMessages];

    // Call AI Service
    const aiAnswer = await aiService.generateChatResponse(apiMessages);

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
        conversationId: conversation._id,
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
