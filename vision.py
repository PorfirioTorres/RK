import pyautogui
import base64
from io import BytesIO
from pathlib import Path
import os
import ollama

# Configuration
BASE = Path(__file__).parent
TEMP_SCREENSHOT = BASE / "current_screen.png"

class RyukoVision:
    def __init__(self, model_name="llava"):
        self.model_name = model_name

    def capture_screen(self):
        """Captures a screenshot of the entire screen and returns it as a base64 string."""
        try:
            # Take screenshot
            screenshot = pyautogui.screenshot()

            # Convert to bytes
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()

            # Save a copy locally for debugging (optional)
            with open(TEMP_SCREENSHOT, "wb") as f:
                f.write(img_bytes)

            # Return base64 encoded string for Ollama
            return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            print(f"[Vision] Error capturing screen: {e}")
            return None

    def analyze_screen(self, prompt="What is the user doing right now? Describe it briefly."):
        """Sends the screenshot to Ollama LLaVA for analysis."""
        img_b64 = self.capture_screen()
        if not img_b64:
            return "I can't see your screen right now."

        try:
            # Call Ollama with the image
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                images=[img_b64]
            )
            return response['response'].strip()
        except Exception as e:
            print(f"[Vision] Error analyzing screen: {e}")
            return f"I tried to look, but I got an error: {e}"

# Global instance
vision = RyukoVision()
