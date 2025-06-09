import os
from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask import send_from_directory
from flask_migrate import Migrate
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('author.id'), nullable=False)
    author = db.relationship('Author', backref=db.backref('files', lazy=True))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/')
def index():
    return redirect(url_for('upload_file'))

@app.route('/add_author', methods=['GET', 'POST'])
def add_author():
    if request.method == 'POST':
        name = request.form['name']
        new_author = Author(name=name)
        db.session.add(new_author)
        db.session.commit()
        return redirect(url_for('add_author'))
    
    authors = Author.query.all()
    return render_template('add_author.html', authors=authors)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        author_id = request.form['author_id']
        file = request.files['file']
        if file and author_id:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            new_file = UploadedFile(filename=filename, filepath=filepath, author_id=author_id)
            db.session.add(new_file)
            db.session.commit()
            return redirect(url_for('upload_file'))

    authors = Author.query.all()
    return render_template('upload.html', authors=authors)

@app.route('/files', methods=['GET', 'POST'])
def list_files():
    author_id = request.args.get('author_id')
    sort_order = request.args.get('sort', 'asc')
    search_query = request.args.get('search', '').strip()

    query = UploadedFile.query

    if author_id:
        query = query.filter(UploadedFile.author_id == int(author_id))

    if search_query:
        query = query.filter(UploadedFile.filename.ilike(f'%{search_query}%'))

    if sort_order == 'desc':
        query = query.order_by(UploadedFile.upload_date.desc())
    else:
        query = query.order_by(UploadedFile.upload_date.asc())

    files = query.all()

    authors = Author.query.all()
    return render_template('list_files.html', files=files, authors=authors, sort_order=sort_order, search_query=search_query)


@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    file = UploadedFile.query.get_or_404(file_id)

    if os.path.exists(file.filepath):
        os.remove(file.filepath)

    db.session.delete(file)
    db.session.commit()
    return redirect(url_for('list_files'))

@app.route('/delete_author/<int:author_id>', methods=['POST'])
def delete_author(author_id):
    author = Author.query.get_or_404(author_id)
    

    for file in author.files:
        if os.path.exists(file.filepath):
            os.remove(file.filepath)
        db.session.delete(file)
    

    db.session.delete(author)
    db.session.commit()
    
    return redirect(url_for('add_author'))

@app.route('/activity', methods=['GET', 'POST'])
def author_activity():

    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.utcnow()

    query = db.session.query(db.func.count(UploadedFile.id))

    if start_date:
        query = query.filter(UploadedFile.upload_date >= start_date)
    query = query.filter(UploadedFile.upload_date <= end_date)

    total_files = query.scalar()

    authors = Author.query.all()
    author_file_counts = {}
    for author in authors:
        count = db.session.query(db.func.count(UploadedFile.id)) \
            .filter(UploadedFile.author_id == author.id) \
            .filter(UploadedFile.upload_date <= end_date)

        if start_date:
            count = count.filter(UploadedFile.upload_date >= start_date)

        author_file_counts[author.name] = count.scalar()



    fig1, ax1 = plt.subplots()
    ax1.bar(['Общее количество файлов'], [total_files]) 
    ax1.set_ylabel('Количество файлов')
    ax1.set_title(f'Общее количество файлов с {start_date.strftime("%Y-%m-%d") if start_date else "не указано"} по {end_date.strftime("%Y-%m-%d")}')


    fig2, ax2 = plt.subplots()
    authors_names = list(author_file_counts.keys())
    author_counts = list(author_file_counts.values())
    ax2.bar(authors_names, author_counts)
    ax2.set_ylabel('Количество файлов')
    ax2.set_title(f'Количество файлов по авторам с {start_date.strftime("%Y-%m-%d") if start_date else "не указано"} по {end_date.strftime("%Y-%m-%d")}')

    img1 = io.BytesIO()
    fig1.savefig(img1, format='png')
    img1.seek(0)
    graph_url1 = base64.b64encode(img1.getvalue()).decode('utf-8')

    img2 = io.BytesIO()
    fig2.savefig(img2, format='png')
    img2.seek(0)
    graph_url2 = base64.b64encode(img2.getvalue()).decode('utf-8')

    return render_template('activity.html', graph_url1=graph_url1, graph_url2=graph_url2, total_files=total_files, start_date=start_date, end_date=end_date)




@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


    



with app.app_context():
    db.create_all()

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
