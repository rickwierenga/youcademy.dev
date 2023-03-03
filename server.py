import json
import os
import uuid

from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, send_file
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_required, login_user, current_user, UserMixin, logout_user
from flask_sqlalchemy import SQLAlchemy
import redis
import rq

from worker import conn
from tasks import get_audio_clip_path, qid2qck, generate_presentation, answer_follow_up_question

app = Flask(__name__, template_folder='templates', static_folder='static')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'welcome'

app.config["SECRET_KEY"] = "supersecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
db = SQLAlchemy(app)
r = redis.Redis(host='localhost', port=6379, db=0)

q = rq.Queue(connection=conn)

class User(db.Model, UserMixin):
  __tablename__ = 'users'
  id = db.Column(db.Integer, primary_key=True)
  first_name = db.Column(db.String(80), nullable=False)
  last_name = db.Column(db.String(80), nullable=False)
  prof = db.Column(db.String(80), nullable=False)
  email = db.Column(db.String(80), unique=True, nullable=False)
  password_hash = db.Column(db.String(80), nullable=False)
  language_id = db.Column(db.String(2), nullable=False)

  def __repr__(self):
    return f"User({self.first_name} {self.last_name})"


with app.app_context():
  db.create_all()

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
  return redirect(url_for('welcome'))

def session_set(r, key: str, value): r.set(key, value)
def session_get(r, key: str): return r.get(key)
def session_has(r, key: str): return r.exists(key)
def session_del(r, key: str): return r.delete(key)


@app.route('/', methods=['GET', 'POST'])
@login_required
def query():
  if request.method == 'POST':
    query_text = request.form['query']
    qid = str(uuid.uuid4())
    q.enqueue_call(generate_presentation, args=(qid, query_text, current_user.prof, app.instance_path, current_user.language_id)) # TODO: add current user context
    presentation = {
      "status": "pending",
      "query_text": query_text,
    }
    session_set(r, qid2qck(qid), json.dumps(presentation))
    return redirect(url_for('slides', qid=qid))

  return render_template('query.html')


@app.route('/slides/<string:qid>')
@login_required
def slides(qid):
  return render_template('slides.html', qid=qid)

@app.route('/query/<string:qid>/<int:i>/audio')
def get_audio(qid, i):
  fn = get_audio_clip_path(app.instance_path, qid, i)
  if not os.path.isfile(fn):
    return jsonify(error="Not found"), 404
  return send_file(fn, mimetype='audio/mpeg')

def is_presentation_ready(slides):
  for slide in slides:
    if slide["image_status"] == "pending" or slide["audio_status"] == "pending":
      return False
  return True

@app.route('/debug/<string:qid>')
def get_debug(qid):
  data = session_get(r, qid2qck(qid))
  if data is None:
    return jsonify(status="error", error="can't find data for prompt"), 404
  presentation = json.loads(data)  
  return jsonify(**presentation)

@app.route('/data/<string:qid>')
def get_data(qid):
  data = session_get(r, qid2qck(qid))
  if data is None:
    return jsonify(status="error", error="can't find data for prompt"), 404
  presentation = json.loads(data)
  if presentation["status"] == "pending": # fixed loading data, hacky
    return jsonify(status="pending") # don't return the slides if the presentation is still loading.
  # else, must be real slides
  if not "slides" in presentation:
    return jsonify(status="pending")
  slides = presentation["slides"]
  # if not is_presentation_ready(slides):
  #   return jsonify(status="pending") # don't return the slides if the presentation is still loading.
  return jsonify(slides=slides, status="ready")

@app.route("/query/<string:qid>/<int:i>/follow-up", methods=["POST"])
# @login_required
def ask_follow_up_question(qid, i):
  pck = qid2qck(qid)
  presentation = r.get(pck)
  presentation = json.loads(presentation)  
  if presentation["slides"][i]["is_follow_up"]:
    return jsonify(error="Already a follow-up question", status="error"), 400
  
  print("set presentation to pending")
  presentation["status"] = "pending" # set action status to pending again
  session_set(r, pck, json.dumps(presentation))

  question = request.json.get("question")

  q.enqueue_call(answer_follow_up_question, args=(qid, i, question, app.instance_path, current_user.language_id))

  return jsonify(status="success")


@app.route('/welcome')
def welcome():
  if current_user.is_authenticated:
    return redirect(url_for('query'))
  return render_template('land.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    email = request.form['email']
    password = request.form['password']

    user = User.query.filter_by(email=email).first()
    if user is None:
      flash("Incorrect password", "danger")
      return render_template('login.html')
    
    if check_password_hash(user.password_hash, password):
      login_user(user, remember=True)
      return redirect(url_for('query'))

    flash("Incorrect password")

  return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    first_name = request.form['first-name']
    last_name = request.form['last-name']
    prof = request.form['prof']
    email = request.form['email']
    password = request.form['password']
    language_id = request.form['language']

    user = User.query.filter_by(email=email).first()
    if user is not None:
      flash("User already exists")
      return render_template('register.html') 
    
    new_user = User(
      first_name=first_name,
      last_name=last_name,
      prof=prof,
      language_id=language_id,
      email=email,
      password_hash=generate_password_hash(password)
    )
    db.session.add(new_user)

    try:
      db.session.commit()
      login_user(new_user)
      return redirect(url_for('query'))
    except Exception as e:
      print("Error creating user", e)
      flash("There was an issue creating your account")

  return render_template('register.html') 


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('welcome'))

@app.route("/edit-account", methods=["GET", "POST"])
@login_required
def edit_account():
  if request.method == "POST":
    first_name = request.form['first-name']
    last_name = request.form['last-name']
    prof = request.form['prof']
    language_id = request.form['language']

    current_user.first_name = first_name
    current_user.last_name = last_name
    current_user.prof = prof
    current_user.language_id = language_id

    try:
      db.session.commit()
      flash("Account updated")
    except Exception as e:
      print("Error creating user", e)
      flash("There was an issue updating your account")

  return render_template('edit.html')


if __name__ == '__main__':
    #app.run(port=4500)#, debug=True)
    app.run(port=4500, debug=True)
