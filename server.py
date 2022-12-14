from flask import Flask, request, render_template, redirect, session, url_for
import data_manager
import util
import hash
from pathlib import Path
from markupsafe import Markup
from bonus_questions import SAMPLE_QUESTIONS
import flask_login

BACK_TO_HOME = """<table><tr><th><a href="/"><h1>Ask Mate</h1></a></th><th><h2> - crowdsourced Q&A site</h2></th></tr></table>"""
UPLOAD_FOLDER = Path(str(Path(__file__).parent.absolute()) + '/static/images')
QUESTION_TABLE_HEADERS = ['Submission time', 'Number of views', 'Number of votes', 'Title', 'Message']
USER_TABLE_HEADERS = ['Id', 'Login', 'Registration date', 'Questions number', 'Answers number', 'Comments number', 'Reputation']
ANSWER_TABLE_HEADERS = ['Submission time', 'Number of votes', 'Message']
COMMENT_TABLE_HEADERS = ['Attachment', 'Submission time', 'Message', 'Edited count']


app = Flask(__name__)
#python -c 'import secrets; print(secrets.token_hex())'
app.secret_key = '9e33e7321f59a3fdc954607f32c9da3f6b74ec0bc36828e0555de5a37987727a'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


@app.route("/bonus-questions")
def main():
    return render_template('bonus_questions.html', questions=SAMPLE_QUESTIONS)


@app.route('/', methods=['GET', 'POST'])
def home_page():
    data = data_manager.get_top_records('question', 'submission_time', size_limit=5)
    data = util.convert_time_to_readable(data)
    return render_template('home_page.html', data=data, headers=QUESTION_TABLE_HEADERS)


@app.route('/list', methods=['GET', 'POST'])
def list_question_page():
    data = data_manager.get_sorted_data('question')
    data = util.convert_time_to_readable(data)

    if request.method == 'GET':
        category = request.args.get('by_category')
        order = request.args.get('by_order')
        data = data_manager.get_sorted_data('question', category, order)
    return render_template('list_questions.html', data=data, headers=QUESTION_TABLE_HEADERS)


@app.route('/question/<question_id>', methods=['GET', 'POST'])
def display_question_with_answers(question_id):
    accept_answer = False
    data_manager.update_record(question_id, {'view_number': 1}, 'question')
    answers_data_base = data_manager.get_sorted_data('answer', question_id=question_id)
    answers_data_base = util.convert_time_to_readable(answers_data_base)
    question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    question['submission_time'] = question['submission_time'].replace(microsecond=0)
    comments_to_question = data_manager.get_records_by_foreign_key({'question_id': question_id}, 'comment')
    number_of_comments_to_question = len(comments_to_question)
    comments_to_question = util.convert_time_to_readable(comments_to_question)
    image = util.get_image(question)
    list_of_tags, comments_to_answer = util.get_all_comments_to_answer(answers_data_base, question_id)
    return render_template('display_a_question.html',
                           question=question,
                           image=image,
                           answers_base=answers_data_base,
                           comments_to_answer=comments_to_answer,
                           comments_to_question=comments_to_question,
                           number_of_comments_to_question=number_of_comments_to_question,
                           list_of_tags=list_of_tags,
                           accept_answer=accept_answer)


def vote_and_user_rep_change(question_id):
    if request.method == 'POST':
        if request.form.get('vote_answer'):
            id = request.form['vote_answer']
            add = int(request.form['vote'])
            util.voting_and_rep_user_update(add, id, 10, 'answer')
        if request.form.get('vote_question'):
            id = request.form['vote_question']
            add = int(request.form['vote'])
            util.voting_and_rep_user_update(add, id, 5, 'question')
    question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    question['submission_time'] = question['submission_time'].replace(microsecond=0)
    answers_data_base = data_manager.get_sorted_data('answer', question_id=question_id)
    answers_data_base = util.convert_time_to_readable(answers_data_base)
    return render_template('display_a_question.html',
                           question=question,
                           answers_data_base=answers_data_base)


def sort_answers(question_id, answers_data_base):
    if request.method == 'GET':
        category = request.args.get('by_category')
        order = request.args.get('by_order')
        answers_data_base = data_manager.get_sorted_data('answer', category, order, question_id)
    return render_template('display_a_question.html', answers_base=answers_data_base)


def is_accepted_answer(question, accept_answer, question_id):
    if flask_login.current_user.is_authenticated:
        user_login_in_session = flask_login.current_user.email
        users = data_manager.get_all_records('user_data')
        accept_answer = util.acceptation_answer(users, user_login_in_session, question, accept_answer)

    if request.form.get('accept_answer'):
        answer_id = request.form.get('accept_answer')
        util.rep_user_update_after_acceptation_answer(question_id, answer_id, True)
    if request.form.get('not_accept_answer'):
        util.rep_user_update_after_acceptation_answer(question_id, None, False)
    return render_template('display_a_question.html', accept_answer=accept_answer)


@app.route('/question/<question_id>/new-answer', methods=['GET', 'POST'])
@flask_login.login_required
def add_answer(question_id):
    question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    if request.method == 'POST':
        description = request.form['description']
        description = util.add_apostrophe(description)
        file = request.files['file']
        if file and util.allowed_file(file.filename):
            file.save(UPLOAD_FOLDER / file.filename)
        data_manager.add_new_answer_record(question_id, description, file.filename,
                                           flask_login.current_user.db_id)
        return redirect(f'/question/{question_id}')
    elif request.method == 'GET':
        return render_template('upload_answer.html', question_id=question['id'])


@app.route('/answer/<answer_id>/edit', methods=['GET', 'POST'])
def edit_answer(answer_id):
    answer_data = data_manager.get_record_by_primary_key({'id': answer_id}, 'answer')
    if request.method == 'POST':
        new_message = request.form['description']
        new_message = util.add_apostrophe(new_message)
        file = request.files['file']
        if file:
            if util.allowed_file(file.filename):
                file.save(UPLOAD_FOLDER / file.filename)
                file = file.filename
            else:
                file = answer_data['image']
        else:
            file = answer_data['image']
        data_manager.update_record(answer_id, {'message': new_message, 'image': file}, 'answer')
        return redirect(f'/question/{answer_data["question_id"]}')
    if request.method == 'GET':
        edited_answer = data_manager.get_record_by_primary_key({'id': answer_id}, 'answer')
        edited_answer['submission_time'] = edited_answer['submission_time'].strftime("%d/%m/%Y %H:%M:%S")
        return render_template('edit_answer.html', answer=edited_answer)


@app.route('/add_question', methods=['POST', 'GET'])
@flask_login.login_required
def new_question():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        description = util.add_apostrophe(description)
        file = request.files['file']
        if file and util.allowed_file(file.filename):
            file.save(UPLOAD_FOLDER / file.filename)
        data_manager.add_new_question_record(title, description, file.filename,
                                             flask_login.current_user.db_id)
        return redirect('/')
    elif request.method == 'GET':
        return render_template('upload_question.html')


@app.route('/question/<question_id>/delete', methods=['POST', 'GET'])
@flask_login.login_required
def delete_question(question_id):
    if request.method == 'POST':
        value = list(request.form)
        if value == ['yes']:
            data_manager.delete_question_by_id_bd(question_id)
            return render_template('delete_question.html')
        else:
            return redirect(f'/question/{question_id}')
    elif request.method == 'GET':
        return render_template('confirm_question_deletion.html')


@app.route('/question/<question_id>/<answer_id>/delete', methods=['GET', 'POST'])
@flask_login.login_required
def delete_answer(question_id, answer_id):
    if request.method == 'POST':
        value = list(request.form)
        if value == ['yes']:
            data_manager.delete_answer_by_id_bd(question_id, answer_id)
            return redirect(f'/question/{question_id}')
        else:
            return redirect(f'/question/{question_id}')
    elif request.method == 'GET':
        return render_template('confirm_answer_deletion.html')


@app.route('/question/<question_id>/edit_page', methods=['GET', 'POST'])
def edit_question(question_id):
    question_data = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    if request.method == 'POST':
        new_title = request.form['title']
        new_question = request.form['message']
        new_question = util.add_apostrophe(new_question)
        file = request.files['file']

        if util.allowed_file(file.filename):
            file.save(UPLOAD_FOLDER / file.filename)
            file = file.filename
        else:
            file = question_data['image']
        data_manager.update_record(question_id, {'title': new_title, 'message': new_question, 'image': file }, 'question')
        return redirect(f'/question/{question_id}')

    elif request.method == 'GET':
        edited_question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
        edited_question['submission_time'] = edited_question['submission_time'].strftime("%d/%m/%Y %H:%M:%S")
        return render_template('edit_question.html', question=edited_question)


@app.route('/question/<question_id>/new_comment', methods=['GET', 'POST'])
@flask_login.login_required
def add_comment_to_question(question_id):
    question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    if request.method == 'POST':
        comment_text = request.form['description']
        comment_text = util.add_apostrophe(comment_text)
        data_manager.add_new_comment_to_question_record(comment_text, question_id,
                                                        flask_login.current_user.db_id)
        return redirect(f'/question/{question_id}')
    return render_template('add_comment_to_question.html', question=question)


@app.route('/answer/<answer_id>/new-comment', methods=['GET', 'POST'])
@flask_login.login_required
def add_comment_to_answer(answer_id):
    answer = data_manager.get_record_by_primary_key({'id': answer_id}, 'answer')
    if request.method == 'POST':
        comment_text = request.form['description']
        comment_text = util.add_apostrophe(comment_text)
        data_manager.add_new_comment_to_answer_record(comment_text, answer_id,
                                                      flask_login.current_user.db_id)
        question_id = answer['question_id']
        return redirect(f'/question/{question_id}')
    return render_template('add_comment_to_answer.html', answer=answer)


@app.route('/comment/<comment_id>/delete', methods=['GET', 'POST'])
@flask_login.login_required
def delete_comment(comment_id):
    comment = data_manager.get_record_by_primary_key({'id': comment_id}, 'comment')
    if request.method == 'POST':
        value = list(request.form)
        if value == ['yes']:
            data_manager.delete_comment(comment_id)
            if comment['question_id'] is not None:
                return redirect(f'/question/{comment["question_id"]}')
            else:
                answer = data_manager.get_record_by_primary_key({'id': comment['answer_id']}, 'answer')
                return redirect(f"/question/{answer['question_id']}")
        else:
            if comment['question_id'] is not None:
                return redirect(f'/question/{comment["question_id"]}')
            else:
                answer = data_manager.get_record_by_primary_key({'id': comment['answer_id']}, 'answer')
                return redirect(f"/question/{answer['question_id']}")
    elif request.method == 'GET':
        return render_template('confirm_comment_deletion.html')


@app.route('/comment/<comment_id>/edit', methods=['GET', 'POST'])
def edit_comment_to_answer(comment_id):
    comment = data_manager.get_record_by_primary_key({'id': comment_id}, 'comment')
    if comment["answer_id"]:
        answer = data_manager.get_record_by_primary_key({'id': comment["answer_id"]}, 'answer')

    if answer["question_id"]:
        question = data_manager.get_record_by_primary_key({'id': answer["question_id"]}, 'question')

    if request.method == 'POST':
        comment_text = request.form['description']
        comment_text = util.add_apostrophe(comment_text)
        data_manager.update_record(comment_id, {'message': comment_text}, 'comment')
        data_manager.update_comment_edited_count(comment['id'])
        return redirect(f'/question/{question["id"]}')

    return render_template('edit_comment.html', comment=comment, answer=answer, question=question)


@app.route('/comment/<comment_id>/editt', methods=['GET', 'POST'])
def edit_comment_to_question(comment_id):
    comment = data_manager.get_record_by_primary_key({'id': comment_id}, 'comment')
    if comment["question_id"]:
        question = data_manager.get_record_by_primary_key({'id': comment["question_id"]}, 'question')

    if request.method == 'POST':
        comment_text = request.form['description']
        comment_text = util.add_apostrophe(comment_text)
        data_manager.update_record(comment_id, {'message': comment_text}, 'comment')
        data_manager.update_comment_edited_count(comment['id'])
        return redirect(f'/question/{question["id"]}')

    return render_template('edit_comment_to_question.html', comment=comment,  question=question)


@app.route('/search')
def search_result():
    search_phrase = request.args['search'].lower().strip()
    data = data_manager.search_by_phrase(search_phrase)
    for question in data:
        question['submission_time'] = question['submission_time'].strftime("%d/%m/%Y %H:%M:%S")
        question['message'] = Markup(question['message'].replace(search_phrase, f"<mark>{search_phrase}</mark>"))
        question['title'] = Markup(question['title'].replace(search_phrase, f"<mark>{search_phrase}</mark>"))
    return render_template('list_questions.html', data=data, headers=QUESTION_TABLE_HEADERS)


@app.route('/question/<question_id>/new_tag', methods=['GET', 'POST'])
def add_tag_to_question(question_id):
    question = data_manager.get_record_by_primary_key({'id': question_id}, 'question')
    tags = data_manager.get_all_records('tag')
    if request.method == 'POST':
        if request.form.get('thisistag'):
            tag = request.form.get('thisistag')
            data_manager.add_new_tag(tag)
        elif request.form.get('all_tags'):
            tag = request.form.get('all_tags')
        tag_id = data_manager.get_record_by_primary_key({'name': tag}, 'tag', 'id')
        data_manager.add_tag_to_question_tag_bd(question_id, tag_id['id'])

        return redirect(f'/question/{question["id"]}')
    return render_template('add_tag_to_question.html', question=question, tags=tags)


@app.route('/question/<question_id>/tag/<tag_id>/delete_tag', methods=['GET', 'POST'])
def remove_tag_from_question(question_id, tag_id):
    if request.method == 'POST':
        value = list(request.form)
        if value == ['yes']:
            data_manager.delete_tag_from_question(question_id, tag_id)
            return redirect(f'/question/{question_id}')
        else:
            return redirect(f'/question/{question_id}')
    elif request.method == 'GET':
        return render_template('confirm_tag_deletion.html')
    else:
        return redirect('/')


################Sprint_3########


@app.route('/tags', methods=['GET'])
def tags():
    headers = ['Tag name', 'Use count']
    all_tags = data_manager.get_tags_and_use_count()
    return render_template('all_tags.html', headers=headers, all_tags=all_tags)


@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'POST':
        email = request.form['email']
        if data_manager.is_email_exists(email):
            return BACK_TO_HOME + '''<h1>Login already exists!</h1><br>
    <form action='/registration'>
        <button>Back to registration page</button>
    </form>
    '''
        password = hash.hash_password(request.form['password'])
        data_manager.add_new_user(email, password)
        return redirect('/')
    else:
        return render_template('registration.html')


@app.route('/users', methods=['GET', 'POST'])
@flask_login.login_required
def display_users():
    if flask_login.current_user.is_authenticated:
        users = data_manager.get_users_records()
        return render_template('users_page.html', users=users, headers=USER_TABLE_HEADERS[1:])
    return BACK_TO_HOME + """
    <br><br><br><br><center><h1>Option not available. You must login!</h1></center>
    """


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    email = request.form['email']
    if data_manager.is_email_exists(email):
        if hash.verify_password(request.form['password'], dict(data_manager.get_password_by_email(email))['password']):
            user = User()
            user.id = email
            flask_login.login_user(user)
            return redirect(url_for('protected'))
    return redirect('/login')


@app.route('/user/<user_id>', methods=['GET', 'POST'])
def user_account(user_id):
    if flask_login.current_user.is_authenticated:
        user = data_manager.get_single_user_record(user_id)
        questions = data_manager.get_questions_written_by_user(user_id)
        answers = data_manager.get_answers_written_by_user(user_id)
        comments = data_manager.get_comments_written_by_user(user_id)
        return render_template('user_single_page.html',
                               user=user, user_headers=USER_TABLE_HEADERS,
                               questions=questions, question_headers=QUESTION_TABLE_HEADERS,
                               answers=answers, answer_headers=ANSWER_TABLE_HEADERS,
                               comments=comments, comment_headers=COMMENT_TABLE_HEADERS
                               )
    return BACK_TO_HOME + """
    <br><br><br><br><center><h1>Option not available. You must login!</h1></center>
    """


@app.route('/protected')
@flask_login.login_required
def protected():
    print(f'user {flask_login.current_user.email} has logged in')
    return redirect('/')


@app.route('/logout')
@flask_login.login_required
def logout():
    print(f'user {flask_login.current_user.email} logged out')
    flask_login.logout_user()
    return redirect('/')


@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('error.html')


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    if not data_manager.is_email_exists(email):
        return
    user = User()
    user.email = email
    user.db_id = data_manager.get_user_id_by_email(email)['id']
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    if not data_manager.is_email_exists(email):
        return
    user = User()
    user.id = email
    user.is_authenticated = hash.verify_password(request.form['password'], data_manager.get_password_by_email(email))
    return user


##############################################


if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        port=8000,
        debug=True,
    )
