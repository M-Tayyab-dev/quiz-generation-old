---
title: Quiz AI Backend API
emoji: 🧠
colorFrom: green
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# Quiz AI Backend API (Hugging Face Space)

Production FastAPI backend for the Quiz AI Flutter mobile application.

## Endpoints
- `GET /health`: Health check
- `GET /profiles`: Supported profiles and languages
- `POST /documents`: Upload clean, text-based PDF, DOCX, or TXT
- `POST /documents/review`: Review & edit extracted text
- `POST /quizzes`: Generate MCQs (easy, medium, hard)
- `POST /quizzes/{id}/submit`: Grade quiz and provide topic-level feedback
- `GET /history`: Student quiz history
