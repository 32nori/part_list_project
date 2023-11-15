# part_list_project
- 昔から部品表のサンプルをネット上で検索していましがた見かける事がなかったので
自分で作ってみようと思い立ちました。お役立ちになるか分かりませんが動くものをつくりましたのでよろしければお使い下さい。

# インストール方法

## 1.リポジトリのクローン
GitHubからプロジェクトをクローンします。
```powershell
git clone https://github.com/your-username/your-project-name.git
cd your-project-name
```

## 2.依存関係のインストール
必要なライブラリと依存関係をインストールします。
```powershell
pip install -r requirements.txt
```

## 3.データベースのセットアップ
データベースマイグレーションを実行します。
```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata part_list_app/fixtures/part_data.json
```
part_dataの中に製品、部品のコードが入っていますので、こちらより選択して動作確認してみて下さい。

## 4.サーバーの起動
Django開発サーバーを起動します。
```powershell
python manage.py runserver
```
サーバーが起動したら、ブラウザで http://127.0.0.1:8000/ にアクセスしてプロジェクトを表示します。

# 使用方法
プロジェクトの使用方法や機能についての説明を記述します。ユーザーがプロジェクトを使用するためのステップやヒントを提供します。
# ライセンス
このプロジェクトのライセンス情報を記述します。例えば、MITライセンスやGPLライセンスなどです。
