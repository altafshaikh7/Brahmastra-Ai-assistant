const express = require("express");
const { protect } = require("../middleware/authMiddleware");
const {
  createMemory,
  getMemories,
  updateMemory,
  deleteMemory,
} = require("../controllers/memoryController");

const router = express.Router();

// All memory routes require authentication
router.use(protect);

router.post("/", createMemory);
router.get("/", getMemories);
router.put("/:id", updateMemory);
router.delete("/:id", deleteMemory);

module.exports = router;
