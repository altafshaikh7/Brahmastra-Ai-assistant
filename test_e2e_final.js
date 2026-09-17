async function fetchWithRetry(url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    const res = await fetch(url, options);
    if (res.status === 429) {
      console.log(`[429 Too Many Requests] Retrying in ${Math.pow(2, i)} seconds...`);
      await new Promise(r => setTimeout(r, Math.pow(2, i) * 1000));
      continue;
    }
    return res;
  }
  return await fetch(url, options);
}

async function runTests() {
  const BASE_URL = "http://localhost:5000/api";
  console.log("Starting Final End-to-End Tests...");

  try {
    // 1. Register User A
    const emailA = `testuser_A_${Date.now()}@test.com`;
    console.log("Registering User A:", emailA);
    let res = await fetchWithRetry(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: "Test User A",
        email: emailA,
        password: "password123"
      })
    });
    let data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    const tokenA = data.data.token;
    console.log("✅ User A registered.");

    // 2. Chat with User A to set memory
    console.log("Testing Agent Chat (Setting memory for User A)...");
    res = await fetchWithRetry(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenA}` },
      body: JSON.stringify({ query: "Hello, my name is Altaf and my project is a cool AI agent." })
    });
    data = await res.json();
    if (!data.success) throw new Error(JSON.stringify(data));
    
    // Wait for memory extraction
    await new Promise(r => setTimeout(r, 2000));

    // 3. Register User B
    const emailB = `testuser_B_${Date.now()}@test.com`;
    console.log("Registering User B:", emailB);
    res = await fetchWithRetry(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: "Test User B",
        email: emailB,
        password: "password123"
      })
    });
    data = await res.json();
    const tokenB = data.data.token;
    console.log("✅ User B registered.");

    // 4. Test Isolation: User B tries to ask about User A's name
    console.log("Testing Isolation: User B asking for User A's name...");
    res = await fetchWithRetry(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenB}` },
      body: JSON.stringify({ query: "What is my name?" })
    });
    data = await res.json();
    console.log("User B Answer:", data.data.answer);

    // 5. Test Isolation: User A asks about their own name
    console.log("Testing Memory Retrieval: User A asking for their own name...");
    res = await fetchWithRetry(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenA}` },
      body: JSON.stringify({ query: "What is my name?" })
    });
    data = await res.json();
    console.log("User A Answer:", data.data.answer);

    // 6. Test Agent Brain Tools (Multi-step)
    console.log("Testing Agent Brain Tools (Multi-step)...");
    res = await fetchWithRetry(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenA}` },
      body: JSON.stringify({ query: "Calculate 20 * 5 and then tell me the current time." })
    });
    data = await res.json();
    console.log("Agent Brain Tools Answer:", data.data.answer);

    console.log("🎉 ALL TESTS COMPLETED");
  } catch (error) {
    console.error("❌ Test failed:", error.message);
    process.exit(1);
  }
}

runTests();
