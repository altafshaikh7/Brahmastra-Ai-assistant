import api from "./api";

/**
 * Send query to chatbot
 * @param {string} query
 * @param {string} [conversationId]
 * @returns {Promise<{answer: string, conversationId: string}>}
 */
export const sendChatMessage = async (query, conversationId) => {
  const response = await api.post("/api/chat", { query, conversationId });
  return response.data.data;
};

/**
 * Get all conversations
 * @returns {Promise<Array>}
 */
export const getConversations = async () => {
  const response = await api.get("/api/conversations");
  return response.data.data;
};

/**
 * Delete a specific conversation thread
 * @param {string} id
 * @returns {Promise<object>}
 */
export const deleteConversation = async (id) => {
  const response = await api.delete(`/api/conversations/${id}`);
  return response.data;
};
