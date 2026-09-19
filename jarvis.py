import urllib.request
import urllib.error
import urllib.parse
import json
import datetime
import webbrowser
import subprocess
import os
import ast
import operator

import speech_recognition as sr
import pyttsx3


# ---------------- CONFIGURATION ----------------

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"

conversation = []


# ---------------- TTS ----------------

engine = pyttsx3.init()
engine.setProperty("rate", 175)
engine.setProperty("volume", 1.0)


def speak(text):
    print("JARVIS:", text)
    engine.say(text)
    engine.runAndWait()


# ---------------- SPEECH RECOGNITION ----------------

recognizer = sr.Recognizer()

def listen():
    try:
        with sr.Microphone() as source:
            print("\nListening...")

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=None
            )

        print("Recognizing...")

        text = recognizer.recognize_google(audio)

        print("You:", text)

        return text

    except sr.WaitTimeoutError:
        print("JARVIS: I didn't hear anything.")
        return ""

    except sr.UnknownValueError:
        print("JARVIS: Sorry, I couldn't understand that.")
        return ""

    except sr.RequestError:
        print("JARVIS: Speech recognition service is unavailable.")
        return ""

    except Exception as e:
        print("Microphone error:", e)
        return ""


# ---------------- CALCULATOR ----------------

operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression):
    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node):

            if isinstance(node, ast.Expression):
                return evaluate(node.body)

            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value

                raise ValueError("Invalid number")

            if isinstance(node, ast.BinOp):

                left = evaluate(node.left)
                right = evaluate(node.right)

                operation = operators.get(type(node.op))

                if operation is None:
                    raise ValueError("Operator not allowed")

                return operation(left, right)

            if isinstance(node, ast.UnaryOp):

                value = evaluate(node.operand)

                operation = operators.get(type(node.op))

                if operation is None:
                    raise ValueError("Operator not allowed")

                return operation(value)

            raise ValueError("Invalid expression")

        return evaluate(tree)

    except Exception:
        return None


# ---------------- OPEN APPLICATIONS ----------------

def open_application(name):

    name = name.lower()

    try:

        if name == "notepad":
            subprocess.Popen("notepad.exe")

        elif name == "calculator":
            subprocess.Popen("calc.exe")

        elif name == "explorer":
            subprocess.Popen("explorer.exe")

        elif name == "chrome":

            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ]

            opened = False

            for path in chrome_paths:

                if os.path.exists(path):
                    subprocess.Popen(path)
                    opened = True
                    break

            if not opened:
                subprocess.Popen("start chrome", shell=True)

        elif name in ["vscode", "visual studio code"]:
            subprocess.Popen("code")

        elif name == "jarvis folder":
            os.startfile(r"C:\Users\bipla\Jarvis")

        else:
            return False

        return True

    except Exception as e:

        print("Could not open application:", e)

        return False


# ---------------- COMMAND HANDLER ----------------

def handle_command(command):

    command = command.lower().strip()

    # Exit
    if command in [
        "exit",
        "quit",
        "bye",
        "goodbye",
        "shutdown",
        "shut down"
    ]:

        speak("Goodbye. JARVIS shutting down.")

        return False


    # Time
    if "time" in command:

        current_time = datetime.datetime.now().strftime(
            "%I:%M %p"
        )

        speak(
            "The current time is " +
            current_time
        )

        return True


    # Date
    if "date" in command or "today" in command:

        current_date = datetime.datetime.now().strftime(
            "%A, %B %d, %Y"
        )

        speak(
            "Today is " +
            current_date
        )

        return True


    # YouTube
    if "youtube" in command:

        webbrowser.open(
            "https://www.youtube.com"
        )

        speak("Opening YouTube.")

        return True


    # Google
    if command == "google":

        webbrowser.open(
            "https://www.google.com"
        )

        speak("Opening Google.")

        return True


    # GitHub
    if "github" in command:

        webbrowser.open(
            "https://github.com"
        )

        speak("Opening GitHub.")

        return True


    # WhatsApp
    if "whatsapp" in command:

        webbrowser.open(
            "https://web.whatsapp.com"
        )

        speak("Opening WhatsApp Web.")

        return True


    # Gmail
    if "gmail" in command or "email" in command:

        webbrowser.open(
            "https://mail.google.com"
        )

        speak("Opening Gmail.")

        return True


    # Search Google
    if command.startswith("search "):

        query = command[7:].strip()

        url = (
            "https://www.google.com/search?q="
            + urllib.parse.quote(query)
        )

        webbrowser.open(url)

        speak(
            "Searching Google for " +
            query
        )

        return True


    # Search YouTube
    if command.startswith("play "):

        query = command[5:].strip()

        url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(query)
        )

        webbrowser.open(url)

        speak(
            "Searching YouTube for " +
            query
        )

        return True


    # Website
    if command.startswith("open website "):

        website = command.replace(
            "open website ",
            "",
            1
        ).strip()

        if not website.startswith("http"):
            website = "https://" + website

        webbrowser.open(website)

        speak("Opening the website.")

        return True


    # Calculator
    if command.startswith("calculate "):

        expression = command.replace(
            "calculate ",
            "",
            1
        )

        result = safe_calculate(expression)

        if result is None:

            speak(
                "I could not calculate that."
            )

        else:

            speak(
                "The answer is " +
                str(result)
            )

        return True


    # Applications
    apps = [
        "notepad",
        "calculator",
        "explorer",
        "chrome",
        "vscode",
        "visual studio code",
        "jarvis folder"
    ]

    for app in apps:

        if command == "open " + app:

            if open_application(app):

                speak(
                    "Opening " +
                    app
                )

            else:

                speak(
                    "I could not open " +
                    app
                )

            return True


    return None


# ---------------- OLLAMA AI ----------------

def ask_ollama(user_message):

    conversation.append(
        {
            "role": "user",
            "content": user_message
        }
    )


    system_prompt = """
You are JARVIS, a professional local AI assistant running on Windows.

IMPORTANT RULES:

1. Answer the user in the same language they use.
2. If the user speaks Nepali, answer naturally in Nepali.
3. If the user speaks English, answer in English.
4. Keep normal voice responses concise, usually 1-5 sentences.
5. For mathematics, give the correct formula and calculation clearly.
6. For programming and technical questions, be accurate and practical.
7. Never invent facts, names, dates, studies, songs, people, or statistics.
8. If you do not understand a question, say so instead of guessing.
9. If a question is ambiguous, ask the user to clarify.
10. Do not pretend that you performed an action unless the program actually performed it.
11. You are assisting a university student with mathematics, computer science,
    programming, statistics, data analysis, and general computer tasks.
12. Be professional, natural, and direct.
"""


    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]


    messages.extend(
        conversation[-10:]
    )


    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }


    try:

        data = json.dumps(
            payload
        ).encode("utf-8")


        request = urllib.request.Request(

            OLLAMA_URL,

            data=data,

            headers={
                "Content-Type": "application/json"
            },

            method="POST"
        )


        with urllib.request.urlopen(
            request,
            timeout=120
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )


        answer = result[
            "message"
        ][
            "content"
        ].strip()


        conversation.append(
            {
                "role": "assistant",
                "content": answer
            }
        )


        return answer


    except urllib.error.URLError:

        return (
            "I cannot connect to Ollama. "
            "Please make sure Ollama is running."
        )


    except Exception as e:

        print(
            "Ollama error:",
            e
        )

        return (
            "Something went wrong "
            "while contacting my AI model."
        )


# ---------------- MAIN PROGRAM ----------------

def main():

    print()

    print("=" * 55)

    print(
        "                 JARVIS AI ASSISTANT"
    )

    print("=" * 55)

    print(
        "Model:",
        MODEL
    )

    print(
        "Voice: Enabled"
    )

    print(
        "Status: Online"
    )

    print(
        "Say 'exit' to shut down."
    )

    print("=" * 55)


    speak(
        "JARVIS is online. How may I assist you?"
    )


    while True:

        command = listen()


        if not command:
            continue


        result = handle_command(
            command
        )


        if result is False:
            break


        if result is True:
            continue


        speak(
            "Let me think."
        )


        answer = ask_ollama(
            command
        )


        speak(
            answer
        )


if __name__ == "__main__":
    main()
