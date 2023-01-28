from flask import Flask, request
import secrets

app = Flask(__name__)

@app.route('/transcribe', methods=['POST'])
@app.route('/transcribe/<session_id>', methods=['POST'])
def transcribe(session_id=None):
    if session_id is None:
        session_id = secrets.token_urlsafe(64)
    file = request.files['clip']
    if file.filename == '':
        return {'error': 'no file provided'}, 400
    return {'session_id': session_id, 'output': None}, 200

if __name__ == '__main__':
    app.run(port=3333)