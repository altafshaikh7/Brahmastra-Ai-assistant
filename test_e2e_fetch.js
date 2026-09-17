async function runTests() {
  const BASE_URL = "http://localhost:5000/api";
  console.log("Starting End-to-End Tests...");

  try {
    // 1. Register a new user
    const email = `testuser_${Date.now()}@test.com`;
    console.log("Registering user:", email);
    let res = await fetch(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: "Integration Test User",
        email,
        password: "password123"
      })
    });
    let data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    const token = data.data.token;
    console.log("✅ User registered successfully. Token length:", token.length);

    // 2. Auth /me endpoint
    console.log("Testing /auth/me...");
    res = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    console.log("✅ /auth/me verified. User ID:", data.data._id);

    // 3. Test Agent Chat (Web Research / Calculator / Conversational)
    console.log("Testing Agent Chat (Conversational)...");
    res = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` 
      },
      body: JSON.stringify({ query: "Hello, my name is John Doe and my project is a cool AI agent." })
    });
    data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    console.log("✅ Chat response:", data.data.answer);

    // 4. Test Memory Retrieval (indirectly by asking the agent)
    console.log("Testing Memory Persistence & Retrieval (Waiting 1s for bg extraction)...");
    await new Promise(r => setTimeout(r, 1000));
    res = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` 
      },
      body: JSON.stringify({ query: "What is my name and what is my project?" })
    });
    data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    console.log("✅ Memory response:", data.data.answer);

    // 5. Test Tools (Calculator)
    console.log("Testing Calculator Tool...");
    res = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}` 
      },
      body: JSON.stringify({ query: "What is 452 multiplied by 19?" })
    });
    data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    console.log("✅ Tool response:", data.data.answer);

    console.log("🎉 ALL TESTS PASSED SUCCESSFULLY");
  } catch (error) {
    console.error("❌ Test failed:", error.message);
    process.exit(1);
  }
}

runTests();
