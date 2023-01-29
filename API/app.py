from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import secrets
import whisper
import numpy as np
import ffmpeg
import openai
from dotenv import load_dotenv
import os

load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

model = whisper.load_model('base.en')

db = SQLAlchemy()

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String, unique=True, nullable=False)
    content = db.Column(db.String)

    def __init__(self):
        self.session_id = secrets.token_urlsafe(64)
        self.content = ''

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

def new_sesh():
    sesh = Session()
    db.session.add(sesh)
    db.session.commit()
    return sesh

def file_to_np(file):
    try:
        out, _ = (
            ffmpeg.input('pipe:', threads=0)
            .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=16000)
            .run(input=file.read(), capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

@app.route('/session', methods=['GET'])
def session():
    return {'session_id': new_sesh().session_id}, 200

@app.route('/delete/<session_id>', methods=['DELETE'])
def finalize(session_id):
    sesh = Session.query.filter_by(session_id=session_id).one_or_none()
    if sesh is None:
        return {'error': 'session does not exist'}, 400
    db.session.delete(sesh)
    db.session.commit()
    return {}, 200

@app.route('/transcribe', methods=['POST'])
@app.route('/transcribe/<session_id>', methods=['POST'])
def transcribe(session_id=None):
    if session_id is None:
        session_id = secrets.token_urlsafe(64)
    sesh = Session.query.filter_by(session_id=session_id).one_or_none()
    if sesh is None:
        sesh = new_sesh()
    file = request.files.get('clip')
    if file is None or file.filename == '':
        return {'error': 'no file provided', 'output': sesh.content, 'session_id': sesh.session_id}, 400
    file_data = file_to_np(file)
    content = model.transcribe(file_data)
    sesh.content += '\n' + content['text']
    db.session.commit()
    if request.get_json(force=True).get('summarize', False):
        gpt_prompt = f"Summarize this meeting transcript:\n\n{sesh.content}\n\nSummary:".strip()

        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=gpt_prompt,
            max_tokens=256,
            temperature=0.5,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        output = response['choices'][0]['text'].strip()
    else:
        output = sesh.content
    return {'session_id': sesh.session_id, 'output': output}, 200

if __name__ == '__main__':
    app.run(port=3333)