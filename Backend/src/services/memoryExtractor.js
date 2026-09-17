/**
 * memoryExtractor.js
 *
 * Extracts durable, non-sensitive facts worth storing in long-term memory
 * from user messages. Runs as a background async operation (non-blocking).
 *
 * Rules:
 * - Only extracts from user messages, never AI responses
 * - Never stores sensitive data (passwords, tokens, keys)
 * - Stores user facts, preferences, instructions, project context
 * - Does not spam memory with conversational utterances
 */

const Memory = require("../models/Memory");
const { containsSensitiveData } = require("../controllers/memoryController");
const logger = require("../utils/logger");

/**
 * Patterns that indicate memory-worthy content in a user message.
 * These should be durable personal facts, not transient questions.
 */
const MEMORY_EXTRACTION_PATTERNS = [
  // Identity / name
  { regex: /\bmy\s+name\s+is\s+([A-Za-z][A-Za-z\s]{1,40})\b/i, category: "user_fact" },
  { regex: /\bi\s+am\s+(a\s+[a-z][\w\s]{3,60})\b/i, category: "user_fact" },
  { regex: /\bcall\s+me\s+([A-Za-z][A-Za-z\s]{1,40})\b/i, category: "user_fact" },

  // Preferences
  { regex: /\bi\s+(?:prefer|like|love|enjoy)\s+(.{5,120})/i, category: "preference" },
  { regex: /\bi\s+(?:don'?t|do\s+not)\s+(?:like|want|prefer)\s+(.{5,120})/i, category: "preference" },
  { regex: /\bmy\s+preferred\s+(?:language|tool|framework|stack|model)\s+is\s+(.{3,80})/i, category: "preference" },

  // Instructions
  { regex: /\balways\s+(?:respond|answer|reply|format|use)\s+(.{5,120})/i, category: "instruction" },
  { regex: /\bnever\s+(?:use|include|mention|say|do)\s+(.{5,120})/i, category: "instruction" },
  { regex: /\bremember\s+to\s+always\s+(.{5,120})/i, category: "instruction" },

  // Project context
  { regex: /\bmy\s+(?:project|app|application|system|product)\s+(?:is|uses?)\s+(.{5,200})/i, category: "project_context" },
  { regex: /\bwe\s+are\s+building\s+(.{5,200})/i, category: "project_context" },
  { regex: /\bmy\s+(?:current|main)\s+(?:goal|task|focus)\s+is\s+(.{5,200})/i, category: "project_context" },
];

// Minimum user message length to attempt extraction (skip very short messages)
const MIN_EXTRACTION_LENGTH = 20;

// Patterns that indicate this is just a question, not a statement of fact
const QUESTION_ONLY_PATTERNS = [
  /^(?:what|how|when|where|why|who|can|could|would|will|is|are|does|do|did|should|which)\b/i,
  /\?$/,
];

/**
 * Extract candidate memory content from a user message.
 * Returns an array of { content, category } objects.
 *
 * @param {string} message
 * @returns {{ content: string, category: string }[]}
 */
function extractMemoryCandidates(message) {
  if (!message || message.length < MIN_EXTRACTION_LENGTH) return [];

  // Skip pure question messages
  for (const pattern of QUESTION_ONLY_PATTERNS) {
    if (pattern.test(message.trim())) return [];
  }

  const candidates = [];

  for (const { regex, category } of MEMORY_EXTRACTION_PATTERNS) {
    const match = message.match(regex);
    if (match) {
      // Use the full matched segment for context
      const content = match[0].trim();
      if (content.length >= 10 && content.length <= 2000) {
        candidates.push({ content, category });
      }
    }
  }

  return candidates;
}

/**
 * Asynchronously extract and persist memory entries from a user message.
 * This is fire-and-forget — it does NOT block the chat response.
 *
 * @param {string} userId
 * @param {string} message
 */
async function extractAndSaveMemories(userId, message) {
  if (!userId || !message) return;

  try {
    const candidates = extractMemoryCandidates(message);
    if (candidates.length === 0) return;

    for (const { content, category } of candidates) {
      // Security: skip sensitive data
      if (containsSensitiveData(content)) continue;

      // Check for exact duplicate
      const existing = await Memory.findOne({ userId, content: content.trim() });
      if (existing) continue;

      await Memory.create({
        userId,
        content: content.trim(),
        category,
        source: "agent_extracted",
        confidence: 0.75,
      });

      logger.info(`Memory auto-extracted for user ${userId}: [${category}] ${content.substring(0, 60)}...`);
    }
  } catch (err) {
    // Never block the main flow
    logger.warn("Memory extraction error (non-blocking):", err.message);
  }
}

module.exports = { extractAndSaveMemories, extractMemoryCandidates };
