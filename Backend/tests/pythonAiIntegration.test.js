const { test } = require("node:test");
const assert = require("node:assert/strict");
const axios = require("axios");

const {
  extractUserMessage,
  generateChatResponse,
  parsePythonAiChatResponse,
  mapPythonAiError,
  PYTHON_AI_UNAVAILABLE_MSG,
} = require("../src/services/aiService");

test("extractUserMessage returns plain string input", () => {
  assert.equal(extractUserMessage("What time is it now?"), "What time is it now?");
});

test("extractUserMessage returns latest user message from history", () => {
  const messages = [
    { role: "system", content: "ignored" },
    { role: "user", content: "first" },
    { role: "assistant", content: "reply" },
    { role: "user", content: "What time is it now?" },
  ];
  assert.equal(extractUserMessage(messages), "What time is it now?");
});

test("parsePythonAiChatResponse extracts orchestrated answer", () => {
  const answer = parsePythonAiChatResponse({
    success: true,
    provider: "gemini",
    model: "gemini-flash-latest",
    response: "It is currently 17:30 UTC.",
    tokens: {},
    execution_time: 1.2,
    conversation_id: "conv_123",
  });
  assert.equal(answer, "It is currently 17:30 UTC.");
});

test("parsePythonAiChatResponse rejects invalid payload", () => {
  assert.throws(
    () => parsePythonAiChatResponse({ success: false, response: "nope" }),
    (err) => err.message === PYTHON_AI_UNAVAILABLE_MSG
  );
});

test("mapPythonAiError maps connection failures safely", () => {
  const err = mapPythonAiError({ code: "ECONNREFUSED", message: "connect refused" });
  assert.equal(err.message, PYTHON_AI_UNAVAILABLE_MSG);
});

test("mapPythonAiError maps upstream 503 safely", () => {
  const err = mapPythonAiError({
    response: { status: 503, data: { detail: "upstream down" } },
  });
  assert.equal(err.message, PYTHON_AI_UNAVAILABLE_MSG);
});

test("mapPythonAiError preserves client-safe 400 detail", () => {
  const err = mapPythonAiError({
    response: { status: 400, data: { detail: "Model is invalid" } },
  });
  assert.equal(err.message, "Model is invalid");
  assert.equal(err.statusCode, 400);
  assert.equal(err.isPythonAiError, true);
});

test("generateChatResponse forwards normal chat to Python-AI /ai/chat", async () => {
  const originalPost = axios.post;
  let capturedUrl;
  let capturedPayload;
  let capturedOptions;

  axios.post = async (url, payload, options) => {
    capturedUrl = url;
    capturedPayload = payload;
    capturedOptions = options;
    return {
      status: 200,
      data: {
        success: true,
        provider: "gemini",
        model: "gemini-flash-latest",
        response: "The current time is 10:30 PM.",
        tokens: {},
        execution_time: 0.5,
        conversation_id: "conv_123",
      },
    };
  };

  try {
    const answer = await generateChatResponse("What time is it now?");
    assert.equal(answer, "The current time is 10:30 PM.");
    assert.equal(capturedUrl, "http://localhost:8000/ai/chat");
    assert.deepEqual(capturedPayload, { message: "What time is it now?" });
    assert.equal(capturedOptions.headers["Content-Type"], "application/json");
    assert.equal(typeof capturedOptions.timeout, "number");
  } finally {
    axios.post = originalPost;
  }
});

test("generateChatResponse maps Python-AI connection errors to clean fallback", async () => {
  const originalPost = axios.post;
  axios.post = async () => {
    const err = new Error("connect ECONNREFUSED 127.0.0.1:8000");
    err.code = "ECONNREFUSED";
    throw err;
  };

  try {
    await assert.rejects(
      () => generateChatResponse("What time is it now?"),
      (err) => err.message === PYTHON_AI_UNAVAILABLE_MSG && err.statusCode === 503
    );
  } finally {
    axios.post = originalPost;
  }
});

test("generateChatResponse preserves mapped Python-AI HTTP status errors", async () => {
  const originalPost = axios.post;
  axios.post = async () => ({
    status: 400,
    data: { detail: "message field required" },
  });

  try {
    await assert.rejects(
      () => generateChatResponse("hello"),
      (err) => err.message === "message field required" && err.statusCode === 400
    );
  } finally {
    axios.post = originalPost;
  }
});

test("live Node to Python integration is opt-in", { skip: !process.env.RUN_LIVE_INTEGRATION }, async () => {
  const answer = await generateChatResponse("What time is it?", "integration-test-conversation");
  assert.equal(typeof answer, "string");
  assert.ok(answer.length > 0);
});
