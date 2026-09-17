const axios = require("axios");

async function runTests() {
  const BASE_URL = "http://localhost:5000/api";
  console.log("Starting End-to-End Tests...");

  try {
    // 1. Register a new user
    const email = `testuser_${Date.now()}@test.com`;
    console.log("Registering user:", email);
    let res = await axios.post(`${BASE_URL}/auth/register`, {
      name: "Integration Test User",
      email,
      password: "password123"
    });
    const token = res.data.data.token;
    console.log("✅ User registered successfully. Token length:", token.length);

    // 2. Auth /me endpoint
    console.log("Testing /auth/me...");
    res = await axios.get(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log("✅ /auth/me verified. User ID:", res.data.data._id);

    // 3. Test Agent Chat (Web Research / Calculator / Conversational)
    console.log("Testing Agent Chat (Conversational)...");
    res = await axios.post(`${BASE_URL}/chat`, {
      query: "Hello, my name is John Doe and my project is a cool AI agent."
    }, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log("✅ Chat response:", res.data.data.answer);

    // 4. Test Memory Retrieval (indirectly by asking the agent)
    console.log("Testing Memory Persistence & Retrieval (Waiting 1s for bg extraction)...");
    await new Promise(r => setTimeout(r, 1000));
    res = await axios.post(`${BASE_URL}/chat`, {
      query: "What is my name and what is my project?"
    }, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log("✅ Memory response:", res.data.data.answer);

    // 5. Test Tools (Calculator)
    console.log("Testing Calculator Tool...");
    res = await axios.post(`${BASE_URL}/chat`, {
      query: "What is 452 multiplied by 19?"
    }, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log("✅ Tool response:", res.data.data.answer);

    console.log("🎉 ALL TESTS PASSED SUCCESSFULLY");
  } catch (error) {
    console.error("❌ Test failed:", error.response ? error.response.data : error.message);
    process.exit(1);
  }
}

runTests();
