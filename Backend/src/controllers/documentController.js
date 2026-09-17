const Document = require("../models/Document");
const logger = require("../utils/logger");
const mongoose = require("mongoose");
const axios = require("axios");

const PYTHON_AI_URL = (process.env.PYTHON_AI_URL || "http://localhost:8000").replace(/\/$/, "");
const PYTHON_AI_API_KEY = process.env.PYTHON_AI_API_KEY;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const ALLOWED_MIME_TYPES = {
  "text/plain": [".txt"],
  "text/markdown": [".md", ".markdown"],
  "application/pdf": [".pdf"],
};

/**
 * Extract text from uploaded file buffer based on mime type
 */
const extractText = (buffer, mimeType) => {
  if (mimeType === "text/plain" || mimeType === "text/markdown") {
    return buffer.toString("utf-8");
  }
  if (mimeType === "application/pdf") {
    // Basic PDF text extraction: extract text between stream/endstream and BT/ET markers
    const raw = buffer.toString("latin1");
    const textParts = [];

    // Extract text objects between BT and ET
    const btEtRegex = /BT\s([\s\S]*?)ET/g;
    let match;
    while ((match = btEtRegex.exec(raw)) !== null) {
      const block = match[1];
      // Extract text from Tj and TJ operators
      const tjRegex = /\(([^)]*)\)\s*Tj/g;
      let tjMatch;
      while ((tjMatch = tjRegex.exec(block)) !== null) {
        textParts.push(tjMatch[1]);
      }
      // Extract text from TJ arrays
      const tjArrayRegex = /\[([^\]]*)\]\s*TJ/g;
      let tjArrMatch;
      while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
        const arrContent = tjArrMatch[1];
        const strRegex = /\(([^)]*)\)/g;
        let strMatch;
        while ((strMatch = strRegex.exec(arrContent)) !== null) {
          textParts.push(strMatch[1]);
        }
      }
    }

    // Decode common PDF escape sequences
    let text = textParts.join(" ");
    text = text
      .replace(/\\n/g, "\n")
      .replace(/\\r/g, "\r")
      .replace(/\\t/g, "\t")
      .replace(/\\\\/g, "\\")
      .replace(/\\([()])/g, "$1");

    return text.trim() || "[PDF text extraction produced no readable content. The PDF may use image-based content.]";
  }
  return "";
};

/**
 * Chunk text into overlapping segments
 */
const chunkText = (text, chunkSize = 500, chunkOverlap = 100) => {
  if (!text || text.length === 0) return [];

  const chunks = [];
  let start = 0;
  const step = Math.max(1, chunkSize - chunkOverlap);

  while (start < text.length) {
    const end = Math.min(start + chunkSize, text.length);
    const chunkContent = text.slice(start, end).trim();
    if (chunkContent.length > 0) {
      chunks.push({
        chunkIndex: chunks.length,
        content: chunkContent,
        charStart: start,
        charEnd: end,
        embedding: [],
      });
    }
    if (end >= text.length) break;
    start += step;
  }

  return chunks;
};

/**
 * Generate embeddings for chunks via Python-AI which uses the configured LLM provider
 */
const generateEmbeddings = async (chunks) => {
  if (!chunks || chunks.length === 0) return chunks;

  try {
    const texts = chunks.map((c) => c.content);
    const response = await axios.post(
      `${PYTHON_AI_URL}/ai/embeddings`,
      { texts },
      {
        headers: {
          "Content-Type": "application/json",
          ...(PYTHON_AI_API_KEY ? { "X-Internal-API-Key": PYTHON_AI_API_KEY } : {}),
        },
        timeout: 60000,
      }
    );

    if (response.data && response.data.success && Array.isArray(response.data.embeddings)) {
      const embeddings = response.data.embeddings;
      for (let i = 0; i < chunks.length && i < embeddings.length; i++) {
        chunks[i].embedding = embeddings[i];
      }
      return chunks;
    }
  } catch (error) {
    logger.warn("Embedding generation failed, documents will be stored without embeddings:", error.message);
  }

  return chunks;
};

/**
 * Upload and ingest a document
 */
const uploadDocument = async (req, res, next) => {
  try {
    const userId = req.user._id;

    if (!req.file) {
      return res.status(400).json({ success: false, message: "No file uploaded" });
    }

    const { originalname, mimetype, size, buffer } = req.file;

    // Normalize mime type for .md files
    let normalizedMime = mimetype;
    if (originalname.endsWith(".md") || originalname.endsWith(".markdown")) {
      normalizedMime = "text/markdown";
    }
    if (originalname.endsWith(".txt")) {
      normalizedMime = "text/plain";
    }

    if (!ALLOWED_MIME_TYPES[normalizedMime]) {
      return res.status(400).json({
        success: false,
        message: `Unsupported file type: ${normalizedMime}. Supported: TXT, Markdown, PDF`,
      });
    }

    if (size > MAX_FILE_SIZE) {
      return res.status(413).json({
        success: false,
        message: `File too large. Maximum size: ${MAX_FILE_SIZE / (1024 * 1024)}MB`,
      });
    }

    // Extract text
    const textContent = extractText(buffer, normalizedMime);
    if (!textContent || textContent.length === 0) {
      return res.status(422).json({
        success: false,
        message: "Could not extract text from the uploaded file.",
      });
    }

    // Chunk the text
    const chunkSize = parseInt(req.body.chunkSize) || 500;
    const chunkOverlap = parseInt(req.body.chunkOverlap) || 100;
    let chunks = chunkText(textContent, chunkSize, chunkOverlap);

    // Create document record
    const doc = new Document({
      userId,
      filename: `${Date.now()}_${originalname}`,
      originalName: originalname,
      mimeType: normalizedMime,
      fileSize: size,
      textContent,
      chunks,
      chunkSize,
      chunkOverlap,
      status: "processing",
    });

    await doc.save();

    // Generate embeddings asynchronously (non-blocking for response)
    generateEmbeddings(chunks)
      .then(async (embeddedChunks) => {
        doc.chunks = embeddedChunks;
        const hasEmbeddings = embeddedChunks.some((c) => c.embedding && c.embedding.length > 0);
        doc.embeddingModel = hasEmbeddings ? "configured_provider" : "none";
        doc.embeddingDimension = hasEmbeddings && embeddedChunks[0].embedding
          ? embeddedChunks[0].embedding.length : 0;
        doc.status = "ready";
        await doc.save();
        logger.info(`Document processing complete: ${doc._id}, chunks: ${embeddedChunks.length}`);
      })
      .catch(async (err) => {
        logger.error(`Document embedding failed: ${doc._id}`, err);
        doc.status = "ready"; // Still usable without embeddings via text search
        doc.errorMessage = "Embedding generation failed; text search still available.";
        await doc.save();
      });

    return res.status(201).json({
      success: true,
      data: {
        _id: doc._id,
        filename: doc.originalName,
        mimeType: doc.mimeType,
        fileSize: doc.fileSize,
        chunks: chunks.length,
        status: doc.status,
      },
    });
  } catch (error) {
    logger.error("Error in uploadDocument:", error);
    next(error);
  }
};

/**
 * List user's documents
 */
const getDocuments = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const documents = await Document.find({ userId })
      .select("originalName mimeType fileSize status chunkSize createdAt updatedAt")
      .sort({ createdAt: -1 });

    return res.status(200).json({ success: true, data: documents });
  } catch (error) {
    logger.error("Error in getDocuments:", error);
    next(error);
  }
};

/**
 * Search documents using text matching (and cosine similarity if embeddings available)
 */
const searchDocuments = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { query, topK } = req.body;

    if (!query || typeof query !== "string" || !query.trim()) {
      return res.status(400).json({ success: false, message: "Query is required" });
    }

    const k = Math.min(parseInt(topK) || 5, 20);
    const documents = await Document.find({ userId, status: "ready" });

    if (documents.length === 0) {
      return res.status(200).json({ success: true, data: [], message: "No documents found" });
    }

    // Try embedding-based search first
    let queryEmbedding = null;
    try {
      const response = await axios.post(
        `${PYTHON_AI_URL}/ai/embeddings`,
        { texts: [query.trim()] },
        {
          headers: {
            "Content-Type": "application/json",
            ...(PYTHON_AI_API_KEY ? { "X-Internal-API-Key": PYTHON_AI_API_KEY } : {}),
          },
          timeout: 30000,
        }
      );
      if (response.data?.success && response.data.embeddings?.[0]) {
        queryEmbedding = response.data.embeddings[0];
      }
    } catch {
      // Fall back to text search
    }

    const results = [];

    for (const doc of documents) {
      for (const chunk of doc.chunks) {
        let score = 0;

        if (queryEmbedding && chunk.embedding && chunk.embedding.length > 0) {
          // Cosine similarity
          score = cosineSimilarity(queryEmbedding, chunk.embedding);
        } else {
          // Text-based relevance: simple keyword matching
          const queryLower = query.toLowerCase();
          const contentLower = chunk.content.toLowerCase();
          const queryWords = queryLower.split(/\s+/).filter(Boolean);
          const matchCount = queryWords.filter((w) => contentLower.includes(w)).length;
          score = queryWords.length > 0 ? matchCount / queryWords.length : 0;
        }

        if (score > 0.1) {
          results.push({
            documentId: doc._id,
            filename: doc.originalName,
            chunkIndex: chunk.chunkIndex,
            content: chunk.content,
            score,
            charStart: chunk.charStart,
            charEnd: chunk.charEnd,
          });
        }
      }
    }

    // Sort by score descending, take top K
    results.sort((a, b) => b.score - a.score);
    const topResults = results.slice(0, k);

    return res.status(200).json({ success: true, data: topResults });
  } catch (error) {
    logger.error("Error in searchDocuments:", error);
    next(error);
  }
};

/**
 * Delete a document
 */
const deleteDocument = async (req, res, next) => {
  try {
    const { id } = req.params;
    const userId = req.user._id;

    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json({ success: false, message: "Invalid document ID" });
    }

    const result = await Document.findOneAndDelete({ _id: id, userId });
    if (!result) {
      return res.status(404).json({ success: false, message: "Document not found" });
    }

    logger.info(`Document deleted: ${id}`);
    return res.status(200).json({ success: true, message: "Document deleted" });
  } catch (error) {
    logger.error("Error in deleteDocument:", error);
    next(error);
  }
};

/**
 * Cosine similarity between two vectors
 */
function cosineSimilarity(a, b) {
  if (!a || !b || a.length !== b.length || a.length === 0) return 0;

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  return denominator === 0 ? 0 : dotProduct / denominator;
}

module.exports = {
  uploadDocument,
  getDocuments,
  searchDocuments,
  deleteDocument,
  extractText,
  chunkText,
  cosineSimilarity,
};
