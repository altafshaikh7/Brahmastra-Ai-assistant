const express = require("express");
const multer = require("multer");
const { protect } = require("../middleware/authMiddleware");
const {
  uploadDocument,
  getDocuments,
  searchDocuments,
  deleteDocument,
} = require("../controllers/documentController");

const router = express.Router();

// All document routes require authentication
router.use(protect);

// Multer config: store in memory buffer for processing
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = ["text/plain", "text/markdown", "application/pdf"];
    const allowedExts = [".txt", ".md", ".markdown", ".pdf"];
    const ext = file.originalname.toLowerCase().split(".").pop();

    if (allowedTypes.includes(file.mimetype) || allowedExts.includes(`.${ext}`)) {
      cb(null, true);
    } else {
      cb(new Error("Unsupported file type. Supported: TXT, Markdown, PDF"), false);
    }
  },
});

router.post("/upload", upload.single("file"), uploadDocument);
router.get("/", getDocuments);
router.post("/search", searchDocuments);
router.delete("/:id", deleteDocument);

module.exports = router;
