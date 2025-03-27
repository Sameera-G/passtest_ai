import secrets
from flask import Flask, render_template, request, redirect, session, jsonify
import requests
from firebase_config import auth, db
import os
import re

import os
from dotenv import load_dotenv

load_dotenv()
print(os.environ.get("FIREBASE_CREDENTIALS_JSON"))


# App configuration
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# API Keys
FIREBASE_WEB_API_KEY = 'AIzaSyDim0vEzAlzko2TYPDY5CeK_rrOWJE2mSU'
GEMINI_API_KEY = 'AIzaSyBj7eCwjGTASkDAoryKOpjvpJ2qqI5hdPM'

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user(email=email, password=password)
            session['user'] = user.uid
            return redirect('/payment')
        except Exception as e:
            return f"Signup Failed: {str(e)}"
    return render_template('signup.html')

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        return redirect('/home')
    return render_template('dummy_payment.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        try:
            r = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}",
                json=payload)
            r.raise_for_status()
            user_data = r.json()
            session['user'] = user_data['localId']
            return redirect('/home')
        except requests.exceptions.HTTPError:
            return f"Login Failed: {r.json().get('error', {}).get('message', 'Unknown error')}"
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/login')
    return render_template('home.html')

@app.route('/reading')
def reading():
    return render_template('reading.html')

@app.route('/generate_content', methods=['POST'])
def generate_content():
    prompt = (
        "Generate an IELTS reading passage of approximately 500 words and 6 questions related to it. "
        "First 3 questions should be answerable using True, False, Not Given. "
        "Last 3 should be answered using one word from the passage. Do not include instructions inside the passage."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        content = result['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"success": True, "content": content})
    else:
        return jsonify({"success": False, "error": response.text})

@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    answers = request.json.get("answers", [])
    original_questions = request.json.get("questions", [])
    passage = request.json.get("passage", "")

    prompt = (
        f"Passage:\n{passage}\n\n"
        f"Questions:\n{original_questions}\n\n"
        f"Answers:\n{answers}\n\n"
        "See the paragraph and questions and answers, and check the accuracy of the answers according to the text "
        "and give the accuracy percentage of the answers."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        content = result['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"success": True, "score": content, "correct_answers": []})
    else:
        return jsonify({"success": False, "error": response.text})
    
@app.route('/submit_listening', methods=['POST'])
def submit_listening():
    data = request.json
    answers = data.get("answers", [])
    questions = data.get("questions", [])
    audio = data.get("audio", "")  # This is just a reference, not audio content

    prompt = (
        f"You are evaluating IELTS listening answers.\n"
        f"Audio file used (reference): {audio}\n\n"
        f"Questions:\n{questions}\n\n"
        f"Answers:\n{answers}\n\n"
        "Please compare the answers to what would be expected from the audio context "
        "and return the accuracy percentage of the answers. Also include the correct answers."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        content = result['candidates'][0]['content']['parts'][0]['text']
        return jsonify({
            "success": True,
            "score": content,
            "correct_answers": []  # Optional: parse correct answers if you structure it better
        })
    else:
        return jsonify({"success": False, "error": response.text})


@app.route('/listening')
def listening():
    return render_template('listening.html')

@app.route('/generate_listening_audio', methods=['POST'])
def generate_listening_audio():
    from gtts import gTTS
    import uuid

    prompt = "Generate text related to IELTS listening test content. Then provide 6 questions related to the content."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        full_text = result['candidates'][0]['content']['parts'][0]['text']

        lines = full_text.split('\n')
        content_lines = []
        questions = []

        for line in lines:
            if re.match(r'^\d+\.', line.strip()):
                questions.append(re.sub(r'^\d+\.\s*', '', line.strip()))
            elif line.strip():
                content_lines.append(line.strip())

        passage = ' '.join(content_lines)
        filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join("static/audio", filename)
        tts = gTTS(passage)
        tts.save(audio_path)

        return jsonify({
            "success": True,
            "audio_path": f"/static/audio/{filename}",
            "questions": questions[:6]
        })
    else:
        return jsonify({"success": False, "error": response.text})


@app.route('/writing')
def writing():
    return render_template('writing.html')

@app.route('/generate_writing_questions', methods=['POST'])
def generate_writing_questions():
    prompt = (
    "Generate two IELTS writing questions:\n"
    "Task 1: A letter writing task (choose randomly from formal, informal, or semi-formal situations).\n"
    "Task 2: An essay writing task (choose randomly from opinion, discussion, advantage/disadvantage, or solution essay).\n"
    "Do not provide answers. Format each task on a separate line."
)


    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = { "contents": [{"parts": [{"text": prompt}]}] }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        text = result['candidates'][0]['content']['parts'][0]['text']
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        task1 = lines[0] if len(lines) > 0 else "Describe the graph below."
        task2 = lines[1] if len(lines) > 1 else "Some people think university education should be free. Discuss both views and give your opinion."
        return jsonify({"success": True, "task1": task1, "task2": task2})
    else:
        return jsonify({"success": False, "error": response.text})

@app.route('/submit_writing', methods=['POST'])
def submit_writing():
    data = request.json
    task1 = data.get("task1", "")
    task2 = data.get("task2", "")
    answer1 = data.get("answer1", "")
    answer2 = data.get("answer2", "")

    prompt = (
        f"You are evaluating two IELTS writing answers.\n\n"
        f"Task 1: {task1}\nAnswer 1: {answer1}\n\n"
        f"Task 2: {task2}\nAnswer 2: {answer2}\n\n"
        f"Please provide a score out of 100% based on IELTS writing criteria (task response, coherence, vocabulary, grammar). "
        f"Also give a short analysis or feedback."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = { "contents": [{"parts": [{"text": prompt}]}] }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        text = result['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"success": True, "score": text, "analysis": text})
    else:
        return jsonify({"success": False, "error": response.text})


@app.route('/speaking')
def speaking():
    return render_template('speaking.html')

if __name__ == '__main__':
    app.run(debug=True)
