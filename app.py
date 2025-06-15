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
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.hpmfkifmugvnbmlggsex:Qwe123rty%40@aws-0-eu-north-1.pooler.supabase.com:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


file_author = db.Table('file_author',
    db.Column('file_id', db.Integer, db.ForeignKey('uploaded_file.id'), primary_key=True),
    db.Column('author_id', db.Integer, db.ForeignKey('author.id'), primary_key=True)
)

class Author(db.Model):
    __tablename__ = 'author'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    files = db.relationship('UploadedFile', secondary=file_author, back_populates='authors')

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    publisher = db.Column(db.String(255))
    authors = db.relationship('Author', secondary=file_author, back_populates='files')


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
        author_ids = request.form.getlist('author_ids')
        file = request.files['file']
        if file and author_ids:
            custom_name = request.form.get('custom_filename', '').strip()
            if not custom_name:
                custom_name = os.path.splitext(file.filename)[0]

            ext = os.path.splitext(file.filename)[1]
            filename = (custom_name + ext)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            if os.path.exists(filepath):
                filename = f"{(custom_name)}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(filepath)

            upload_date_str = request.form.get('upload_date', '').strip()

            if upload_date_str:
                try:
                    upload_date = datetime.strptime(upload_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    upload_date = datetime.utcnow()  # fallback у випадку помилки
            else:
                upload_date = datetime.utcnow()

            publisher = request.form.get('publisher', '').strip()

            new_file = UploadedFile(filename=filename, filepath=filepath, upload_date=upload_date, publisher=publisher)

            
            # Добавляем авторов
            authors = Author.query.filter(Author.id.in_(author_ids)).all()
            new_file.authors = authors

            db.session.add(new_file)
            db.session.commit()
            return redirect(url_for('upload_file'))

    authors = Author.query.all()
    return render_template('upload.html', authors=authors)



@app.route('/files', methods=['GET'])
def list_files():
    author_ids = request.args.getlist('author_ids')  # список id авторов (много)
    sort_order = request.args.get('sort', 'asc')
    search_query = request.args.get('search', '').strip()
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    query = UploadedFile.query

    # Фильтр по авторам (список)
    if author_ids:
        author_ids_int = [int(a) for a in author_ids if a.isdigit()]
        if author_ids_int:
            query = query.filter(UploadedFile.authors.any(Author.id.in_(author_ids_int)))

    # Поиск по названию
    if search_query:
        query = query.filter(UploadedFile.filename.ilike(f'%{search_query}%'))

    # Фильтрация по диапазону дат upload_date
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
            query = query.filter(UploadedFile.upload_date >= date_from)
        except ValueError:
            pass

    if date_to_str:
        try:
            # Чтобы включить весь день date_to, можно добавить время до конца дня
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
            date_to_end = date_to.replace(hour=23, minute=59, second=59)
            query = query.filter(UploadedFile.upload_date <= date_to_end)
        except ValueError:
            pass

    # Сортировка
    if sort_order == 'desc':
        query = query.order_by(UploadedFile.upload_date.desc())
    else:
        query = query.order_by(UploadedFile.upload_date.asc())

    files = query.all()
    authors = Author.query.order_by(Author.name).all()

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
            .filter(UploadedFile.authors.any(Author.id == author.id)) \
            .filter(UploadedFile.upload_date <= end_date)

        if start_date:
            count = count.filter(UploadedFile.upload_date >= start_date)

        author_file_counts[author.name] = count.scalar()



    fig1, ax1 = plt.subplots()
    ax1.bar(['Загальна кількість файлів'], [total_files]) 
    ax1.set_ylabel('Кількість файлів')
    ax1.set_title(f'Загальна кількість файлів з {start_date.strftime("%Y-%m-%d") if start_date else "не вказано"} по {end_date.strftime("%Y-%m-%d")}')


    fig2, ax2 = plt.subplots(figsize=(10, 10))  # ← збільшуємо розмір графіка
    authors_names = list(author_file_counts.keys())
    author_counts = list(author_file_counts.values())

    ax2.bar(authors_names, author_counts)
    ax2.set_ylabel('Кількість файлів')
    ax2.set_title(f'Кількість файлів по авторам з {start_date.strftime("%Y-%m-%d") if start_date else "не вказано"} по {end_date.strftime("%Y-%m-%d")}')
    ax2.tick_params(axis='x', rotation=45, labelsize=8)

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


    



if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
