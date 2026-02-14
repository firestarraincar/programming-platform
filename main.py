# platform.py - Полная платформа программирования с тестами
# Установка: pip install flask flask-login sqlalchemy
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import os
import smtplib
import subprocess
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SMTP_SERVER'] = 'smtp.gmail.com'
app.config['SMTP_PORT'] = 587
app.config['SMTP_USERNAME'] = 'aleksejzardeckij74@gmail.com'
app.config['SMTP_PASSWORD'] = 'tnmc vrrc brwr avfz'
app.config['ADMIN_EMAIL'] = 'aleksejzardeckij74@gmail.com'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Integer, default=1500)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, default=1)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tags = db.Column(db.String(200))
    test_cases = db.Column(db.Text)  # JSON с тестами
    solution_code = db.Column(db.Text)
    input_format = db.Column(db.Text)
    output_format = db.Column(db.Text)
    sample_input = db.Column(db.Text)
    sample_output = db.Column(db.Text)
    time_limit = db.Column(db.Integer, default=2000)  # ms
    memory_limit = db.Column(db.Integer, default=256)  # MB
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Contest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    problems = db.Column(db.Text)  # JSON список ID задач
    participants = db.Column(db.Text, default='[]')  # JSON список ID участников
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'))
    contest_id = db.Column(db.Integer, db.ForeignKey('contest.id'))
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(20), default='python')
    verdict = db.Column(db.String(50), default='Pending')
    score = db.Column(db.Integer, default=0)
    passed_tests = db.Column(db.Integer, default=0)
    total_tests = db.Column(db.Integer, default=0)
    execution_time = db.Column(db.Float)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProblemProposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tags = db.Column(db.String(200))
    test_cases = db.Column(db.Text)
    input_format = db.Column(db.Text)
    output_format = db.Column(db.Text)
    sample_input = db.Column(db.Text)
    sample_output = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContestProposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    proposed_problems = db.Column(db.Text)
    duration_hours = db.Column(db.Integer, default=2)
    status = db.Column(db.String(20), default='pending')
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['SMTP_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT'])
        server.starttls()
        server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False


# Система тестирования
def run_python_code(code, input_data, timeout=2):
    """Запускает Python код с входными данными"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            python_file = f.name

        start_time = datetime.now()
        process = subprocess.run(
            ['python', python_file],
            input=input_data.encode(),
            capture_output=True,
            timeout=timeout
        )
        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        os.unlink(python_file)

        return {
            'success': True,
            'output': process.stdout.decode('utf-8', errors='ignore'),
            'error': process.stderr.decode('utf-8', errors='ignore'),
            'returncode': process.returncode,
            'execution_time': execution_time
        }

    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Timeout ({timeout}s)', 'timeout': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def normalize_output(output):
    """Нормализует вывод для сравнения"""
    return output.strip().replace('\r\n', '\n').replace('\r', '\n')


def test_solution(problem_id, code):
    """Тестирует решение задачи"""
    problem = Problem.query.get(problem_id)
    if not problem:
        return {'error': 'Problem not found'}

    try:
        test_cases = json.loads(problem.test_cases)['tests']
    except:
        test_cases = []

    results = []
    total_score = 0
    max_score = 0
    all_passed = True
    details = []

    for i, test in enumerate(test_cases):
        test_input = test['input']
        expected_output = test['output']
        test_points = test.get('points', 100 / len(test_cases))
        max_score += test_points

        result = run_python_code(code, test_input, timeout=problem.time_limit / 1000)

        test_result = {
            'test_id': i + 1,
            'input': test_input,
            'expected': expected_output,
            'points': test_points
        }

        if not result['success']:
            test_result['status'] = 'RE'
            test_result['message'] = result['error']
            test_result['actual'] = ''
            all_passed = False
            details.append(f"Test {i + 1}: Runtime Error - {result['error']}")

        elif result.get('timeout'):
            test_result['status'] = 'TL'
            test_result['message'] = f'Time limit exceeded ({problem.time_limit}ms)'
            test_result['actual'] = ''
            all_passed = False
            details.append(f"Test {i + 1}: Time Limit")

        else:
            actual_output = result['output']
            normalized_actual = normalize_output(actual_output)
            normalized_expected = normalize_output(expected_output)

            if normalized_actual == normalized_expected:
                test_result['status'] = 'OK'
                test_result['message'] = 'Passed'
                test_result['actual'] = actual_output
                test_result['execution_time'] = result['execution_time']
                total_score += test_points
                details.append(f"Test {i + 1}: ✅ Passed ({result['execution_time']:.1f}ms)")
            else:
                test_result['status'] = 'WA'
                test_result['message'] = 'Wrong Answer'
                test_result['actual'] = actual_output
                all_passed = False
                details.append(f"Test {i + 1}: ❌ Wrong Answer")

        results.append(test_result)

    # Определяем вердикт
    if all_passed:
        verdict = "Accepted"
    elif any(r['status'] == 'TL' for r in results):
        verdict = "Time Limit Exceeded"
    elif any(r['status'] == 'RE' for r in results):
        verdict = "Runtime Error"
    else:
        verdict = "Wrong Answer"

    return {
        'verdict': verdict,
        'score': total_score,
        'max_score': max_score,
        'passed': sum(1 for r in results if r['status'] == 'OK'),
        'total': len(results),
        'results': results,
        'details': '\n'.join(details),
        'execution_time': results[-1]['execution_time'] if results and 'execution_time' in results[-1] else 0
    }


# Роуты
@app.route('/')
def index():
    active_contests = Contest.query.filter(
        Contest.is_approved == True,
        Contest.end_time > datetime.utcnow()
    ).order_by(Contest.start_time).limit(5).all()

    popular_problems = Problem.query.filter_by(is_approved=True).order_by(
        db.func.random()
    ).limit(10).all()

    leaderboard = User.query.order_by(User.rating.desc()).limit(20).all()

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Программирование Платформа</title>
        <style>
            body {{ font-family: Arial; max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4a6fa5; color: white; padding: 20px; border-radius: 10px; }}
            .nav {{ margin: 20px 0; }}
            .nav a {{ margin-right: 15px; text-decoration: none; color: #333; font-weight: bold; }}
            .card {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .btn {{ background: #4a6fa5; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }}
            .difficulty-1 {{ color: #2ecc71; }}
            .difficulty-2 {{ color: #f39c12; }}
            .difficulty-3 {{ color: #e74c3c; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Программирование Платформа</h1>
            <p>Соревнуйтесь, решайте задачи, улучшайте навыки</p>
            {"<p>Привет, " + current_user.username + "! Рейтинг: " + str(current_user.rating) + "</p>" if current_user.is_authenticated else ""}
        </div>

        <div class="nav">
            <a href="/">Главная</a>
            <a href="/problems">Задачи</a>
            <a href="/contests">Турниры</a>
            <a href="/propose_problem">Предложить задачу</a>
            <a href="/propose_contest">Предложить турнир</a>
            <a href="/submissions">Мои посылки</a>
            {"<a href='/admin'>Админ</a>" if current_user.is_authenticated and current_user.is_admin else ""}
            {"<a href='/logout'>Выход</a>" if current_user.is_authenticated else "<a href='/login'>Вход</a> | <a href='/register'>Регистрация</a>"}
        </div>

        <div style="display: flex; gap: 20px;">
            <div style="flex: 2;">
                <h2>Активные турниры</h2>
                {''.join([f"<div class='card'><h3>{c.title}</h3><p>{c.description[:100]}...</p><a href='/contest/{c.id}' class='btn'>Участвовать</a></div>" for c in active_contests]) if active_contests else "<p>Нет активных турниров</p>"}

                <h2>Популярные задачи</h2>
                {''.join([f"<div class='card'><h3>{p.title}</h3><p>Сложность: <span class='difficulty-{p.difficulty}'>{'★' * p.difficulty}</span></p><p>{p.description[:100]}...</p><a href='/problem/{p.id}' class='btn'>Решить</a></div>" for p in popular_problems])}
            </div>

            <div style="flex: 1;">
                <h2>Топ 20 лидеров</h2>
                <div class="card">
                    {''.join([f"<p>{i + 1}. {u.username} - {u.rating}</p>" for i, u in enumerate(leaderboard)])}
                </div>
            </div>
        </div>
    </body>
    </html>
    '''


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            return "Имя пользователя занято"

        if User.query.filter_by(email=email).first():
            return "Email уже используется"

        user = User(username=username, email=email)
        user.set_password(password)

        if username == 'admin':
            user.is_admin = True

        db.session.add(user)
        db.session.commit()

        # Отправка приветственного email
        send_email(
            email,
            'Добро пожаловать на платформу!',
            f'<h1>Добро пожаловать, {username}!</h1><p>Ваш аккаунт успешно создан.</p>'
        )

        return redirect('/login')

    return '''
    <form method="POST">
        <h2>Регистрация</h2>
        <input type="text" name="username" placeholder="Имя пользователя" required><br>
        <input type="email" name="email" placeholder="Email" required><br>
        <input type="password" name="password" placeholder="Пароль" required><br>
        <button type="submit">Зарегистрироваться</button>
    </form>
    '''


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect('/')

        return "Неверные данные"

    return '''
    <form method="POST">
        <h2>Вход</h2>
        <input type="text" name="username" placeholder="Имя пользователя" required><br>
        <input type="password" name="password" placeholder="Пароль" required><br>
        <button type="submit">Войти</button>
        <a href="/register">Регистрация</a>
    </form>
    '''


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/propose_problem', methods=['GET', 'POST'])
@login_required
def propose_problem():
    if request.method == 'POST':
        # Собираем тесты
        tests = []
        test_count = int(request.form.get('test_count', 0))

        for i in range(1, test_count + 1):
            test_input = request.form.get(f'test_input_{i}')
            test_output = request.form.get(f'test_output_{i}')
            if test_input and test_output:
                tests.append({
                    "input": test_input,
                    "output": test_output,
                    "points": int(request.form.get(f'test_points_{i}', 100 / test_count if test_count > 0 else 100))
                })

        proposal = ProblemProposal(
            title=request.form['title'],
            description=request.form['description'],
            difficulty=request.form['difficulty'],
            author_id=current_user.id,
            tags=request.form.get('tags', ''),
            test_cases=json.dumps({"tests": tests}),
            input_format=request.form.get('input_format', ''),
            output_format=request.form.get('output_format', ''),
            sample_input=request.form.get('sample_input', ''),
            sample_output=request.form.get('sample_output', '')
        )

        db.session.add(proposal)
        db.session.commit()

        send_email(
            app.config['ADMIN_EMAIL'],
            f'Новое предложение задачи: {proposal.title}',
            f'''
            <h1>Новая задача от {current_user.username}</h1>
            <h3>{proposal.title}</h3>
            <p><strong>Сложность:</strong> {proposal.difficulty}</p>
            <p><strong>Описание:</strong></p>
            <div>{proposal.description}</div>
            <p><strong>Количество тестов:</strong> {len(tests)}</p>
            <p><a href="{request.host_url}admin">Перейти к рассмотрению</a></p>
            '''
        )

        return '''
        <div style="text-align: center; margin-top: 50px;">
            <h2>✅ Задача предложена!</h2>
            <p>Задача отправлена на рассмотрение администратору.</p>
            <p>Вы получите email когда задача будет рассмотрена.</p>
            <a href="/">На главную</a>
        </div>
        '''

    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Предложить задачу</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea, select { width: 100%; padding: 8px; margin: 5px 0; }
            .test-case { border: 1px solid #ddd; padding: 15px; margin: 10px 0; background: #f9f9f9; }
            .btn { padding: 10px 20px; background: #3498db; color: white; border: none; cursor: pointer; }
            .btn-add { background: #2ecc71; }
        </style>
        <script>
            let testCount = 0;

            function addTest() {
                testCount++;
                const testsDiv = document.getElementById('tests');
                const testDiv = document.createElement('div');
                testDiv.className = 'test-case';
                testDiv.innerHTML = `
                    <h4>Тест ${testCount}</h4>
                    <input type="hidden" name="test_count" value="${testCount}">

                    <div class="form-group">
                        <label>Входные данные:</label>
                        <textarea name="test_input_${testCount}" rows="3" required></textarea>
                    </div>

                    <div class="form-group">
                        <label>Выходные данные:</label>
                        <textarea name="test_output_${testCount}" rows="3" required></textarea>
                    </div>

                    <div class="form-group">
                        <label>Баллы за тест:</label>
                        <input type="number" name="test_points_${testCount}" value="10" min="1">
                    </div>

                    <button type="button" onclick="this.parentElement.remove(); updateTestCount();">Удалить тест</button>
                `;
                testsDiv.appendChild(testDiv);
            }

            function updateTestCount() {
                testCount--;
                document.querySelectorAll('input[name^="test_count"]').forEach((input, index) => {
                    input.value = index + 1;
                });
            }
        </script>
    </head>
    <body>
        <h1>Предложить новую задачу</h1>
        <form method="POST">

            <div class="form-group">
                <label>Название задачи:</label>
                <input type="text" name="title" required>
            </div>

            <div class="form-group">
                <label>Описание:</label>
                <textarea name="description" rows="10" required></textarea>
            </div>

            <div class="form-group">
                <label>Сложность:</label>
                <select name="difficulty">
                    <option value="1">★ Легкая</option>
                    <option value="2">★★ Средняя</option>
                    <option value="3">★★★ Сложная</option>
                </select>
            </div>

            <div class="form-group">
                <label>Формат входных данных:</label>
                <textarea name="input_format" rows="3"></textarea>
            </div>

            <div class="form-group">
                <label>Формат выходных данных:</label>
                <textarea name="output_format" rows="3"></textarea>
            </div>

            <div class="form-group">
                <label>Пример входных данных:</label>
                <textarea name="sample_input" rows="2"></textarea>
            </div>

            <div class="form-group">
                <label>Пример выходных данных:</label>
                <textarea name="sample_output" rows="2"></textarea>
            </div>

            <div class="form-group">
                <label>Теги (через запятую):</label>
                <input type="text" name="tags" placeholder="математика, строки, алгоритмы">
            </div>

            <h3>Тесты для проверки:</h3>
            <div id="tests"></div>

            <button type="button" class="btn btn-add" onclick="addTest()">+ Добавить тест</button>

            <div style="margin-top: 30px;">
                <button type="submit" class="btn">Отправить задачу на рассмотрение</button>
                <a href="/" style="margin-left: 20px;">Отмена</a>
            </div>
        </form>
    </body>
    </html>
    '''


@app.route('/propose_contest', methods=['GET', 'POST'])
@login_required
def propose_contest():
    if request.method == 'POST':
        proposal = ContestProposal(
            title=request.form['title'],
            description=request.form['description'],
            author_id=current_user.id,
            duration_hours=request.form['duration'],
            proposed_problems=request.form.get('problems', '')
        )

        db.session.add(proposal)
        db.session.commit()

        send_email(
            app.config['ADMIN_EMAIL'],
            f'Новое предложение турнира: {proposal.title}',
            f'<h1>Новый турнир от {current_user.username}</h1><p>{proposal.description}</p>'
        )

        return "Турнир предложен! Ожидайте одобрения."

    problems = Problem.query.filter_by(is_approved=True).all()
    problem_options = ''.join([f'<option value="{p.id}">{p.title}</option>' for p in problems])

    return f'''
    <form method="POST">
        <h2>Предложить турнир</h2>
        <input type="text" name="title" placeholder="Название турнира" required><br>
        <textarea name="description" placeholder="Описание" rows="10" cols="50" required></textarea><br>
        <input type="number" name="duration" placeholder="Длительность (часов)" min="1" max="24" required><br>
        <select name="problems" multiple>
            {problem_options}
        </select><br>
        <button type="submit">Отправить на рассмотрение</button>
    </form>
    '''


@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        return "Доступ запрещен"

    problem_proposals = ProblemProposal.query.filter_by(status='pending').all()
    contest_proposals = ContestProposal.query.filter_by(status='pending').all()

    problems_html = ''
    for p in problem_proposals:
        try:
            tests = json.loads(p.test_cases)['tests']
            tests_html = '<div style="margin: 10px 0; padding: 10px; background: #f5f5f5;">'
            for i, test in enumerate(tests[:3]):  # Показываем первые 3 теста
                tests_html += f'''
                <div style="margin: 5px 0;">
                    <strong>Тест {i + 1}:</strong>
                    <div>Вход: <pre style="background: white; padding: 5px;">{test['input']}</pre></div>
                    <div>Выход: <pre style="background: white; padding: 5px;">{test['output']}</pre></div>
                </div>
                '''
            tests_html += '</div>'
            if len(tests) > 3:
                tests_html += f'<p>... и еще {len(tests) - 3} тестов</p>'
        except:
            tests_html = '<p>Ошибка загрузки тестов</p>'

        problems_html += f'''
        <div style="border:1px solid #ccc; padding:10px; margin:5px;">
            <h3>{p.title} (Сложность: {p.difficulty})</h3>
            <p><strong>Автор:</strong> {User.query.get(p.author_id).username}</p>
            <p><strong>Описание:</strong></p>
            <div style="background: #f9f9f9; padding: 10px;">{p.description}</div>
            <p><strong>Теги:</strong> {p.tags}</p>
            <p><strong>Пример:</strong></p>
            <pre>Вход: {p.sample_input or 'Нет'}</pre>
            <pre>Выход: {p.sample_output or 'Нет'}</pre>
            <p><strong>Тесты:</strong></p>
            {tests_html}
            <form action="/admin/approve_problem/{p.id}" method="POST">
                <textarea name="notes" placeholder="Примечания для автора" style="width:100%;"></textarea><br>
                <button name="action" value="approve" style="background: #2ecc71; color: white; padding: 10px;">✅ Одобрить</button>
                <button name="action" value="reject" style="background: #e74c3c; color: white; padding: 10px;">❌ Отклонить</button>
            </form>
        </div>
        '''

    contests_html = ''.join([f'''
    <div style="border:1px solid #ccc; padding:10px; margin:5px;">
        <h3>{c.title}</h3>
        <p>{c.description[:200]}...</p>
        <form action="/admin/approve_contest/{c.id}" method="POST">
            <textarea name="notes" placeholder="Примечания"></textarea><br>
            <button name="action" value="approve">Одобрить</button>
            <button name="action" value="reject">Отклонить</button>
        </form>
    </div>
    ''' for c in contest_proposals])

    return f'''
    <h1>Админ панель</h1>
    <a href="/">← На главную</a>

    <h2>Предложения задач ({len(problem_proposals)})</h2>
    {problems_html if problems_html else "<p>Нет предложений</p>"}

    <h2>Предложения турниров ({len(contest_proposals)})</h2>
    {contests_html if contests_html else "<p>Нет предложений</p>"}
    '''


@app.route('/admin/approve_problem/<int:id>', methods=['POST'])
@login_required
def approve_problem(id):
    if not current_user.is_admin:
        return "Доступ запрещен"

    proposal = ProblemProposal.query.get_or_404(id)
    action = request.form['action']
    notes = request.form.get('notes', '')

    if action == 'approve':
        problem = Problem(
            title=proposal.title,
            description=proposal.description,
            difficulty=proposal.difficulty,
            author_id=proposal.author_id,
            tags=proposal.tags,
            test_cases=proposal.test_cases,
            input_format=proposal.input_format,
            output_format=proposal.output_format,
            sample_input=proposal.sample_input,
            sample_output=proposal.sample_output,
            is_approved=True
        )
        db.session.add(problem)
        proposal.status = 'approved'

        # Отправка email автору
        author = User.query.get(proposal.author_id)
        send_email(
            author.email,
            f'Задача одобрена: {proposal.title}',
            f'''
            <h1>Ваша задача одобрена!</h1>
            <h3>{proposal.title}</h3>
            <p>Ваша задача была одобрена администратором и теперь доступна для решения.</p>
            <p><strong>Примечания администратора:</strong> {notes}</p>
            <p><a href="{request.host_url}problem/{problem.id}">Перейти к задаче</a></p>
            '''
        )
    else:
        proposal.status = 'rejected'

        author = User.query.get(proposal.author_id)
        send_email(
            author.email,
            f'Задача отклонена: {proposal.title}',
            f'Ваша задача была отклонена.<br><strong>Причина:</strong> {notes}'
        )

    proposal.admin_notes = notes
    db.session.commit()

    return redirect('/admin')


@app.route('/admin/approve_contest/<int:id>', methods=['POST'])
@login_required
def approve_contest(id):
    if not current_user.is_admin:
        return "Доступ запрещен"

    proposal = ContestProposal.query.get_or_404(id)
    action = request.form['action']
    notes = request.form.get('notes', '')

    if action == 'approve':
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=proposal.duration_hours)

        contest = Contest(
            title=proposal.title,
            description=proposal.description,
            author_id=proposal.author_id,
            start_time=start_time,
            end_time=end_time,
            problems=proposal.proposed_problems,
            is_approved=True
        )
        db.session.add(contest)
        proposal.status = 'approved'

        author = User.query.get(proposal.author_id)
        send_email(
            author.email,
            f'Турнир одобрен: {proposal.title}',
            f'Ваш турнир был одобрен!<br>Примечания: {notes}'
        )
    else:
        proposal.status = 'rejected'

        author = User.query.get(proposal.author_id)
        send_email(
            author.email,
            f'Турнир отклонен: {proposal.title}',
            f'Ваш турнир был отклонен.<br>Причина: {notes}'
        )

    proposal.admin_notes = notes
    db.session.commit()

    return redirect('/admin')


@app.route('/problems')
def problems_list():
    problems = Problem.query.filter_by(is_approved=True).all()

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Задачи</title>
        <style>
            body { font-family: Arial; max-width: 1000px; margin: 0 auto; padding: 20px; }
            .problem { border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; }
            .difficulty-1 { border-left: 4px solid #2ecc71; }
            .difficulty-2 { border-left: 4px solid #f39c12; }
            .difficulty-3 { border-left: 4px solid #e74c3c; }
            .btn { padding: 8px 16px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; }
            .tags { color: #666; font-size: 14px; }
        </style>
    </head>
    <body>
        <h1>Задачи</h1>
        <a href="/">← На главную</a>
    '''

    for p in problems:
        html += f'''
        <div class="problem difficulty-{p.difficulty}">
            <h2>#{p.id}. {p.title}</h2>
            <p>Сложность: {'★' * p.difficulty}</p>
            <p>{p.description[:200]}...</p>
            <p class="tags">Теги: {p.tags or 'нет'}</p>
            <a href="/problem/{p.id}" class="btn">Решить задачу</a>
        </div>
        '''

    html += '''
    </body>
    </html>
    '''

    return html


@app.route('/problem/<int:id>')
def problem_view(id):
    problem = Problem.query.get_or_404(id)
    if not problem.is_approved:
        return "Задача не доступна"

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{problem.title}</title>
        <style>
            body {{ font-family: Arial; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .problem-header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
            .samples {{ background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .sample {{ margin: 10px 0; }}
            .io {{ font-family: monospace; background: white; padding: 10px; border: 1px solid #ddd; }}
            .submit-area {{ margin-top: 30px; }}
            textarea {{ width: 100%; height: 300px; font-family: monospace; padding: 10px; }}
            .btn {{ padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; }}
            .nav {{ margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="/problems">← К списку задач</a>
        </div>

        <div class="problem-header">
            <h1>#{problem.id}. {problem.title}</h1>
            <p>Сложность: {'★' * problem.difficulty}</p>
        </div>

        <div class="problem-description">
            {problem.description.replace(chr(10), '<br>')}
        </div>

        {f'<h3>Формат входных данных:</h3><div class="io">{problem.input_format}</div>' if problem.input_format else ''}
        {f'<h3>Формат выходных данных:</h3><div class="io">{problem.output_format}</div>' if problem.output_format else ''}
        {f'<h3>Пример:</h3><div class="samples"><div class="sample"><strong>Вход:</strong><div class="io">{problem.sample_input}</div></div><div class="sample"><strong>Выход:</strong><div class="io">{problem.sample_output}</div></div></div>' if problem.sample_input and problem.sample_output else ''}
        
        <div class="submit-area">
            <h3>Отправить решение</h3>
            <form action="/submit/{problem.id}" method="POST">
                <textarea name="code" placeholder="# Ваше решение на Python
# Например:
# a, b = map(int, input().split())
# print(a + b)"></textarea>
                <br><br>
                <button type="submit" class="btn">▶ Отправить на проверку</button>
            </form>
        </div>
</body>
</html>
'''


@app.route('/submit/<int:problem_id>', methods=['POST'])
@login_required
def submit_solution(problem_id):
    # Проверяем, не отправлял ли уже пользователь решение этой задачи
    previous_submission = Submission.query.filter_by(
        user_id=current_user.id,
        problem_id=problem_id,
        verdict='Accepted'
    ).first()

    if previous_submission:
        return '''
        <div style="text-align: center; margin-top: 100px;">
            <h2>🚫 Решение уже отправлено!</h2>
            <p>Вы уже успешно решили эту задачу.</p>
            <p>Предыдущее решение:</p>
            <pre style="background: #f5f5f5; padding: 10px; max-width: 600px; margin: 0 auto;">
''' + previous_submission.code[:200] + '''...</pre>
            <p>Баллов: <strong>''' + str(previous_submission.score) + '''</p>
            <p>Дата: ''' + str(previous_submission.created_at) + '''</p>
            <a href="/problem/''' + str(problem_id) + '''">← Вернуться к задаче</a>
        </div>
        '''

    code = request.form['code']

    # Тестируем решение
    test_result = test_solution(problem_id, code)

    # Сохраняем результат
    submission = Submission(
        user_id=current_user.id,
        problem_id=problem_id,
        code=code,
        verdict=test_result['verdict'],
        score=test_result['score'],
        passed_tests=test_result['passed'],
        total_tests=test_result['total'],
        execution_time=test_result.get('execution_time', 0),
        details=test_result['details']
    )

    # Обновляем рейтинг
    if test_result['verdict'] == 'Accepted':
        current_user.rating += 10

    db.session.add(submission)
    db.session.commit()

    # Формируем результаты
    results_html = ''
    for test in test_result['results']:
        status_color = {
            'OK': '#2ecc71',
            'WA': '#e74c3c',
            'RE': '#f39c12',
            'TL': '#3498db'
        }.get(test['status'], '#95a5a6')

        results_html += f'''
        <div style="border: 1px solid {status_color}; padding: 10px; margin: 5px 0; border-radius: 4px;">
            <strong>Тест {test['test_id']} ({test['points']} баллов):</strong>
            <span style="color: {status_color}; font-weight: bold;">
                {'✅ OK' if test['status'] == 'OK' else '❌ WA' if test['status'] == 'WA' else '⚠️ RE' if test['status'] == 'RE' else '⏱️ TL'}
            </span>
            <div style="margin-top: 10px;">
                <div><strong>Вход:</strong></div>
                <pre style="background: #f5f5f5; padding: 5px;">{test['input']}</pre>
                <div><strong>Ожидаемый вывод:</strong></div>
                <pre style="background: #f5f5f5; padding: 5px;">{test['expected']}</pre>
                {f'<div><strong>Полученный вывод:</strong></div><pre style="background: #f5f5f5; padding: 5px;">{test["actual"]}</pre>' if test.get('actual') else ''}
            </div>
        </div>
        '''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Результаты проверки</title>
        <style>
            body {{ font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .result {{ padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .accepted {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .rejected {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
            pre {{ background: #f8f9fa; padding: 10px; border-radius: 4px; }}
            .btn {{ padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; display: inline-block; margin: 5px; }}
        </style>
    </head>
    <body>
        <h1>Результаты проверки</h1>

        <div class="result {'accepted' if test_result['verdict'] == 'Accepted' else 'rejected'}">
            <h2>{'✅ Принято' if test_result['verdict'] == 'Accepted' else '❌ ' + test_result['verdict']}</h2>
            <p>Пройдено тестов: <strong>{test_result['passed']}/{test_result['total']}</strong></p>
            <p>Набрано баллов: <strong>{test_result['score']}/{test_result['max_score']}</strong></p>
            {f'<p>🎉 +10 к рейтингу! Новый рейтинг: <strong>{current_user.rating}</strong></p>' if test_result['verdict'] == 'Accepted' else ''}
        </div>

        <h3>Результаты по тестам:</h3>
        {results_html}

        <div style="margin-top: 30px;">
            <a href="/problem/{problem_id}" class="btn">← Вернуться к задаче</a>
            <a href="/problems" class="btn">К списку задач →</a>
            <a href="/submissions" class="btn">Мои посылки →</a>
        </div>
    </body>
    </html>
    '''


@app.route('/submissions')
@login_required
def submissions():
    user_submissions = Submission.query.filter_by(user_id=current_user.id).order_by(
        Submission.created_at.desc()
    ).limit(50).all()

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Мои посылки</title>
        <style>
            body { font-family: Arial; max-width: 1200px; margin: 0 auto; padding: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            .accepted { color: #2ecc71; }
            .wrong-answer { color: #e74c3c; }
            .time-limit { color: #3498db; }
            .runtime-error { color: #f39c12; }
        </style>
    </head>
    <body>
        <h1>Мои посылки</h1>
        <a href="/">← На главную</a>

        <table>
            <tr>
                <th>ID</th>
                <th>Задача</th>
                <th>Вердикт</th>
                <th>Баллы</th>
                <th>Тесты</th>
                <th>Время</th>
                <th>Дата</th>
            </tr>
    '''

    for sub in user_submissions:
        problem = Problem.query.get(sub.problem_id)
        verdict_class = {
            'Accepted': 'accepted',
            'Wrong Answer': 'wrong-answer',
            'Time Limit Exceeded': 'time-limit',
            'Runtime Error': 'runtime-error'
        }.get(sub.verdict, '')

        html += f'''
        <tr>
            <td>{sub.id}</td>
            <td><a href="/problem/{sub.problem_id}">{problem.title if problem else 'Unknown'}</a></td>
            <td class="{verdict_class}">{sub.verdict}</td>
            <td>{sub.score}</td>
            <td>{sub.passed_tests}/{sub.total_tests}</td>
            <td>{sub.execution_time:.1f}ms</td>
            <td>{sub.created_at}</td>
        </tr>
        '''

    html += '''
        </table>
    </body>
    </html>
    '''

    return html


@app.route('/contests')
def contests_list():
    contests = Contest.query.filter_by(is_approved=True).order_by(Contest.start_time.desc()).all()

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Турниры</title>
        <style>
            body { font-family: Arial; max-width: 1000px; margin: 0 auto; padding: 20px; }
            .contest { border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; background: #f9f9f9; }
            .btn { padding: 8px 16px; background: #e74c3c; color: white; text-decoration: none; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>Турниры</h1>
        <a href="/">← На главную</a>
    '''

    for c in contests:
        html += f'''
        <div class="contest">
            <h2>🏆 {c.title}</h2>
            <p>{c.description[:200]}...</p>
            <p><strong>Начало:</strong> {c.start_time}</p>
            <p><strong>Окончание:</strong> {c.end_time}</p>
            <a href="/contest/{c.id}" class="btn">Участвовать</a>
        </div>
        '''

    html += '''
    </body>
    </html>
    '''

    return html


@app.route('/contest/<int:id>')
def contest_view(id):
    contest = Contest.query.get_or_404(id)

    # Парсим задачи
    try:
        problem_ids = json.loads(contest.problems or '[]')
        problems = Problem.query.filter(Problem.id.in_(problem_ids)).all()
    except:
        problems = []

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{contest.title}</title>
        <style>
            body {{ font-family: Arial; max-width: 1000px; margin: 0 auto; padding: 20px; }}
            .contest-header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
            .problem {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .btn {{ padding: 8px 16px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="contest-header">
            <h1>🏆 {contest.title}</h1>
            <div>{contest.description.replace(chr(10), '<br>')}</div>
            <p><strong>Начало:</strong> {contest.start_time}</p>
            <p><strong>Окончание:</strong> {contest.end_time}</p>
        </div>

        <h2>Задачи турнира</h2>
    '''

    for p in problems:
        html += f'''
        <div class="problem">
            <h3>#{p.id}. {p.title}</h3>
            <p>Сложность: {'★' * p.difficulty}</p>
            <p>{p.description[:150]}...</p>
            <a href="/problem/{p.id}" class="btn">Решить</a>
        </div>
        '''

    if not problems:
        html += '<p>В турнире пока нет задач</p>'

    html += '''
    </body>
    </html>
    '''

    return html


@app.route('/api/sync', methods=['POST'])
@login_required
def sync_data():
    data = request.json
    action = data.get('action')

    if action == 'get_user_data':
        submissions = Submission.query.filter_by(user_id=current_user.id).order_by(
            Submission.created_at.desc()
        ).limit(50).all()

        return jsonify({
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'rating': current_user.rating,
                'is_admin': current_user.is_admin
            },
            'submissions': [{
                'id': s.id,
                'problem_id': s.problem_id,
                'verdict': s.verdict,
                'score': s.score,
                'passed_tests': s.passed_tests,
                'total_tests': s.total_tests,
                'created_at': s.created_at.isoformat()
            } for s in submissions]
        })

    elif action == 'submit_solution':
        problem_id = data.get('problem_id')
        code = data.get('code')

        # Тестируем решение
        test_result = test_solution(problem_id, code)

        # Сохраняем
        submission = Submission(
            user_id=current_user.id,
            problem_id=problem_id,
            code=code,
            verdict=test_result['verdict'],
            score=test_result['score'],
            passed_tests=test_result['passed'],
            total_tests=test_result['total'],
            details=test_result['details']
        )

        if test_result['verdict'] == 'Accepted':
            current_user.rating += 10

        db.session.add(submission)
        db.session.commit()

        return jsonify({
            'success': True,
            'verdict': test_result['verdict'],
            'score': test_result['score'],
            'passed': test_result['passed'],
            'total': test_result['total'],
            'new_rating': current_user.rating
        })

    return jsonify({'error': 'Invalid action'})


# Инициализация базы данных и создание тестовых задач
with app.app_context():
    db.create_all()

    # Создаем администратора если нет
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

    # Создаем тестовые задачи если нет
    if Problem.query.count() == 0:
        # Задача A+B
        test_cases_ab = json.dumps({
            "tests": [
                {"input": "1 2\n", "output": "3\n", "points": 25},
                {"input": "10 20\n", "output": "30\n", "points": 25},
                {"input": "-5 5\n", "output": "0\n", "points": 25},
                {"input": "100 -50\n", "output": "50\n", "points": 25}
            ]
        })

        problem1 = Problem(
            title="A + B",
            description="Напишите программу, которая складывает два целых числа.",
            difficulty=1,
            input_format="Два целых числа через пробел.",
            output_format="Одно целое число - сумма.",
            sample_input="1 2",
            sample_output="3",
            test_cases=test_cases_ab,
            is_approved=True
        )
        db.session.add(problem1)

        # Задача Факториал
        test_cases_fact = json.dumps({
            "tests": [
                {"input": "0\n", "output": "1\n", "points": 20},
                {"input": "1\n", "output": "1\n", "points": 20},
                {"input": "5\n", "output": "120\n", "points": 20},
                {"input": "10\n", "output": "3628800\n", "points": 20},
                {"input": "12\n", "output": "479001600\n", "points": 20}
            ]
        })

        problem2 = Problem(
            title="Факториал",
            description="Вычислите факториал числа n (0 ≤ n ≤ 12).",
            difficulty=2,
            input_format="Одно целое число n.",
            output_format="Факториал числа n.",
            sample_input="5",
            sample_output="120",
            test_cases=test_cases_fact,
            is_approved=True
        )
        db.session.add(problem2)

        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))

    app.run(host='0.0.0.0', port=port, debug=False)
else:
    application = app
