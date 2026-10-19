# 🤖 Ryuko: AI Live2D Desktop Companion

Ryuko is a sarcastic, rebellious, and highly capable anime-style virtual assistant that lives on your desktop. She combines a beautiful Live2D interface with a powerful Python backend, integrating local AI for voice recognition and conversation.

![Ryuko Preview](icono.png)

## ✨ Features

### 🧠 Intelligence & Personality
- **Sarcastic Persona**: A unique "tsundere" personality that makes interactions entertaining.
- **Long-term Memory**: Remembers facts about you across sessions.
- **Multilingual**: Fully supports English and Spanish.

### 🎙️ Voice & Audio
- **Local Ear**: High-precision voice recognition using `faster-whisper` (runs locally on your PC).
- **Versatile Voice**: Support for **ElevenLabs** (cloud), **Piper** (local neural), or **Windows System Speech**.
- **Audio Signals**: Small sound effects for notifications and emotional triggers.

### 🛠️ System Utilities
- **Productivity Suite**: 
  - **Pomodoro Timer**: Built-in focus and break cycles.
  - **Notes & To-do**: Create and manage lists via voice commands.
  - **Exact Calculator**: Handles math and unit conversions without LLM errors.
- **Clipboard Integration**: Ask Ryuko to summarize or translate whatever text you have copied.
- **Environment Awareness**: 
  - **Concentration Mode**: Detects full-screen apps to avoid interrupting your work.
  - **App Tracking**: Knows which window is active and makes contextual comments.
  - **Time-based Mood**: Her behavior changes based on the time of day (e.g., sleepier at 3 AM).

### 💻 PC Control
- **App Launcher**: Opens whitelisted applications, folders, and websites.
- **Media Control**: Controls Play/Pause, Next/Prev, and Volume via system multimedia keys.

### 💃 Live2D Integration
- **Dynamic Emotions**: Changes expressions based on the conversation.
- **Voice-Triggered Gestures**: Command her to wave, stretch, or yawn.

---

## ⚙️ Installation & Setup

### Prerequisites
- **Python 3.10+**
- **Ollama**: Install [Ollama](https://ollama.com/) and pull the required model:
  ```bash
  ollama pull qwen2.5:3b
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

## 🛠️ Customization

- **Language**: Change `IDIOMA = "en"` to `"es"` in `servidor.py`.
- **App Whitelist**: Edit `apps_permitidas.json` to define which programs Ryuko can open.
- **Premium Voice**: Add your API key to `elevenlabs.txt` to enable high-quality cloud synthesis.

---

## 📦 Building the Executable

To package Ryuko into a standalone `.exe` folder:
```bash
python -m PyInstaller servidor.spec --noconfirm --distpath dist --workpath build/pyinstaller
```
The result will be located in `dist/servidor/`.

## 📜 License
This project is developed for educational and personal use.
