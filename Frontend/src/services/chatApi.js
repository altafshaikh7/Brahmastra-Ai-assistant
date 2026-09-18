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

/**
 * Send query to chatbot via stream
 * @param {string} query
 * @param {string} [conversationId]
 * @param {function} onEvent
 * @returns {Promise<{answer: string, conversationId: string}>}
 */
export const sendChatMessageStream = async (query, conversationId, onEvent) => {
  const token = localStorage.getItem("token");
  const response = await fetch(`${api.defaults.baseURL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    },
    body: JSON.stringify({ query, conversationId }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("token");
      window.dispatchEvent(new Event('unauthorized'));
    }
    const err = await response.text();
    let msg = "Chat stream failed";
    try {
      const parsed = JSON.parse(err);
      msg = parsed.message || msg;
    } catch {
      // Response was not JSON, use default message
    }
    throw new Error(msg);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        const dataStr = part.slice(6);
        if (dataStr === "[DONE]") continue;
        try {
          const event = JSON.parse(dataStr);
          if (event.type === 'final') {
            finalResult = event.result;
          } else if (event.type === 'error') {
            throw new Error(event.error);
          } else {
            if (onEvent) onEvent(event);
          }
        } catch (parseErr) {
          if (parseErr.message && !parseErr.message.includes("Unexpected")) {
            throw parseErr;
          }
          console.warn("Error parsing SSE event", parseErr);
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error("Stream ended without final result");
  }
  return finalResult;
};
