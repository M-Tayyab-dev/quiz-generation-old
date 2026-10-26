# GovtQuest AI Document Quiz Module

An AI-powered quiz generation system for GovtQuest that creates high-yield, source-grounded multiple choice questions (MCQs) from student study notes (PDF, DOCX, TXT).

The system features:
- **1 MCQ per screen player** with intuitive **Next** and **Back** navigation.
- **Per-question countdown timer** (default 1 minute / 60 seconds), configurable directly by administrators from the Admin Dashboard and synced in real-time via Cloud Firestore.
- **Detailed results screen** with a **"View Answers"** breakdown: correct answers highlighted in **Green**, student's incorrect choices in **Red**, complete with source quotes and explanations.
- **Firebase Firestore attempt history**: student quiz attempts and full question review data are saved automatically and can be reviewed anytime via **"Previous Quiz Attempts"**.
- **Dynamic user profile** in navigation drawers replacing static placeholders.
- **Clean PDF extraction** with automatic detection and rejection of unselectable scanned/handwritten PDFs.

---

## Documentation

For the complete technical breakdown — architecture diagrams, AI engine flow, Colab GPU guide, and local setup instructions — see:

👉 **[Master System Guide](docs/AI_QUIZ_SYSTEM_GUIDE.md)**

---

## Quickstart: How to Run Locally

### 1. Start the FastAPI Backend

Open PowerShell in the workspace root:

```powershell
# Activate Python environment
.\.venv\Scripts\Activate.ps1

# Start the FastAPI server
python -m ai_quiz_agent.api
```
*(The backend runs at `http://127.0.0.1:8000`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`)*

### 2. Start the Flutter App

In a separate PowerShell window:

```powershell
cd "flutter project"

# Run in Chrome browser
flutter run -d chrome

# Or run on Android emulator / connected physical device
flutter run
```

### 3. Connect App to Backend

1. On the **AI Quiz** screen in the Flutter app, tap the **Gear icon (⚙️)** in the top AppBar.
2. Enter the backend URL:
   - **Chrome Web**: `http://127.0.0.1:8000`
   - **Android Emulator**: `http://10.0.2.2:8000`
   - **Physical Phone (Colab GPU)**: `https://<YOUR-NGROK-SUBDOMAIN>.ngrok-free.app`
   - **Physical Phone (Local PC Wi-Fi)**: `http://<YOUR_PC_LOCAL_IP>:8000`
3. Token: `dev-insecure-token`
4. Tap **Save & Connect**.

---

## Supported Documents

- **Supported**: Clean text-based `.pdf`, typed Word (`.docx`), and `.txt` files up to 25 MB.
- **Rejected**: Scanned image PDFs and handwritten note photos are automatically detected by PyMuPDF and rejected with an explicit prompt to provide typed notes.

---

## Project Structure

- `flutter project/`: GovtQuest Flutter application (1 MCQ/screen, timer, answer review, Firestore history, dynamic user drawer, in-app connection modal).
- `ai_quiz_agent/`: FastAPI backend — PyMuPDF document extraction, prompt orchestration, distractor validation, and scoring.
- `docs/AI_QUIZ_SYSTEM_GUIDE.md`: Master documentation — architecture, AI engine pipeline, Colab GPU guide, sequence diagrams, and local setup.
- `Quiz_AI_Phi35.ipynb`: Colab notebook for running Phi-3.5-mini-instruct on a free T4 GPU with ngrok tunnel.
- `scripts/`: PowerShell startup scripts (`start_local.ps1`, `run_flutter_local.ps1`).
- `examples/`: Sample study notes for testing (clean PDF, DOCX, scanned PDF for rejection).
- `backups/`: Historical archives and preserved OCR reference code.
- `training/`: Optional LoRA fine-tuning pipeline.

### Repository & Branch Status

- Flutter branch: `tayyab`. Workspace root is not a Git repository.
- Static analysis: `flutter analyze` passes with zero errors on all modified Dart files.
