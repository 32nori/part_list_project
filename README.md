# part_list_project
開発環境、動作環境の構築方法を以下に示します。

```powershell
>mkdir part_list_project
>cd part_list_project
>python -m venv venv
>.\venv\Scripts\activate
(venv)>python -m pip install --upgrade pip
(venv)>pip install django
(venv)>pip install django-bootstrap5
(venv)>pip freeze
sgiref==3.7.2
Django==4.2.7
django-bootstrap5==23.3
sqlparse==0.4.4
tzdata==2023.3

(venv)>django-admin startproject part_list_project .
(venv)>python manage.py migrate
(venv) >python manage.py createsuperuser
ユーザー名 (leave blank to use 'hoge'): admin
メールアドレス: admin@example.com
Password: hogefuga
Password (again): hogefuga
Superuser created successfully.

(venv) >python manage.py runserver

(venv) >python manage.py startapp part_list_app


(venv) >python manage.py makemigrations
(venv) >python manage.py migrate

(venv) >python manage.py loaddata part_list_app/fixtures/part_data.json
```
part_dataの中に製品、部品のコードが入っていますので、こちらより選択して動作確認してみて下さい。
