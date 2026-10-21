# 🤖 Ryuko: AI Live2D Desktop Companion

Ryuko is a sarcastic, rebellious, and highly capable anime-style virtual assistant that lives on your desktop. She combines a beautiful Live2D interface with a powerful Python backend, integrating local AI for voice recognition, vision, and conversation.

![Ryuko Preview](icono.png)

## ✨ Features

### 🧠 Intelligence & Context
- **Sarcastic Persona**: A unique "tsundere" personality that makes interactions entertaining.
- **Long-term Memory**: Remembers facts about you across sessions.
- **Local RAG (Knowledge Base)**: Index your own `.txt`, `.pdf`, and `.md` files in the `/knowledge` folder. Ryuko can search your personal notes to answer specific questions.
- **Real-time Web Access**: Integrated web search allows Ryuko to discuss current events and find up-to-date information.
- **Multilingual**: Fully supports English and Spanish.

### 👁️ Vision & Awareness
- **Multimodal Vision**: Using the `llava` model, Ryuko can "see" your screen. Ask her to look at your desktop, and she can comment on what you are doing in real-time.
- **Environment Awareness**: 
  - **Concentration Mode**: Detects full-screen apps to avoid interrupting your work.
  - **App Tracking**: Knows which window is active and makes contextual comments.
  - **Time-based Mood**: Her behavior changes based on the time of day.

### 🎙️ Voice & Audio
- **Local Ear**: High-precision voice recognition using `faster-whisper` (runs locally).
- **Versatile Voice**: Support for **ElevenLabs** (cloud), **Piper** (local neural), or **Windows System Speech**.
- **Audio Signals**: Small sound effects for notifications and emotional triggers.

### 🛠️ System Utilities & Connectivity
- **Discord Bridge**: Ryuko can send proactive notifications to your Discord channel (e.g., reminder alerts).
- **Productivity Suite**: 
  - **Pomodoro Timer**: Built-in focus and break cycles.
  - **Notes & To-do**: Create and manage lists via voice commands.
  - **Exact Calculator**: Handles math and unit conversions without LLM errors.
- **Clipboard Integration**: Ask Ryuko to summarize or translate whatever text you have copied.
- **PC Control**: Open whitelisted applications, folders, and websites, or control system media.

### 💃 Live2D Integration
- **Dynamic Emotions**: Changes expressions based on the conversation.
- **Voice-Triggered Gestures**: Command her to wave, stretch, or yawn.

---

## ⚙️ Installation & Setup

### Prerequisites
- **Python 3.10+**
- **Ollama**: Install [Ollama](https://ollama.com/) and pull the required models:
  ```bash
  ollama pull qwen2.5:3b
  ollama pull llava
  ```

### Quick Start
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/ryuko.git
   cd ryuko
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python servidor.py
   ```
4. Open `http://127.0.0.1:8765` in your browser or use the desktop launcher.

---

## 🛠️ Customization & Configuration

- **Language**: Change `IDIOMA = "en"` to `"es"` in `servidor.py`.
- **Knowledge Base**: Drop your documents into the `/knowledge` folder.
- **App Whitelist**: Edit `apps_permitidas.json` to define which programs Ryuko can open.
- **Discord Bridge**: 
  - Create a bot at the Discord Developer Portal.
  - Place the token in `discord_token.txt`.
  - Add `"discord_channel_id": "YOUR_ID"` to `settings.json`.
- **Premium Voice**: Add your API key to `elevenlabs.txt`.

---

## 📦 Building the Executable
To package Ryuko into a standalone `.exe` folder:
```bash
python -m PyInstaller servidor.spec --noconfirm --distpath dist --workpath build/pyinstaller
```
The result will be located in `dist/servidor/`.

## 📜 License
This project is developed for educational and personal use.
