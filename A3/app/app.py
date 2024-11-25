import os
import sqlite3
import datetime

from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from flask_htmx import HTMX
from flask_htmx import make_response

app = Flask(__name__)
htmx = HTMX(app)


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/messages", methods=["GET"])
def message():
    conn = get_db_connection()
    messages = conn.execute("SELECT * FROM message").fetchall()
    conn.close()

    tmpl = """
    <tr>
        <td>{}</td>
        <td>{}</td>
        <td>{}</td>
    </tr>
    """
    body = [tmpl.format(m["person"], m["text"], m["created"]) for m in messages]
    resp = "".join(body)

    return make_response(resp, push_url=False)


@app.route("/sentiment", methods=["GET"])
def sentiment():
    endpoint = os.environ["AZ_ENDPOINT"]
    key = os.environ["AZ_KEY"]

    if endpoint and key:
        client = TextAnalyticsClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )

        conn = get_db_connection()
        query = conn.execute("SELECT text FROM message LIMIT 10").fetchall()
        conn.close()

        messages = [m["text"] for m in query]
        result = client.analyze_sentiment(messages)
        docs = [doc for doc in result if not doc.is_error]

        sentiments = ""
        for idx, doc in enumerate(docs):
            m = f'<div class="col-md-6"><i>{messages[idx]}</i></div>'
            score = max(dict(doc.confidence_scores).values())
            s = f'<div class="col-md-6"><b>{doc.sentiment.capitalize()} with {score} certainty</b></div>'
            info = "".join([m, s])

            sentiments = "".join([sentiments, '<div class="row">'])
            sentiments = "".join([sentiments, info])
            sentiments = "".join([sentiments, "</div>"])

        tmpl = """
        <div id="modal-backdrop" class="modal-backdrop fade show" style="display:block;"></div>
        <div id="modal" class="modal fade show" tabindex="-1" style="display:block;">
            <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Sentiment analysis</h5>
                </div>
                <div class="modal-body">
                    <div class="container-fluid">
                        {}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button>
                </div>
            </div>
            </div>
        </div>
        """
        resp = tmpl.format(sentiments)

        return make_response(resp, push_url=False)

    else:
        print("error")
        return None


@app.route("/hello", methods=["POST"])
def hello():
    name = request.form.get("name")
    message = request.form.get("message")
    timestamp = str(datetime.datetime.now())

    if name and message:
        print(f"Request for hello page received with name={name} and message={message}")

        conn = get_db_connection()
        conn.execute(
            f"INSERT INTO message (person, text, created) VALUES ('{name}', '{message}', '{timestamp}')"
        )
        conn.commit()
        conn.close()

        resp = f"""
        <tr>
            <td>{name}</td>
            <td>{message}</td>
            <td>{timestamp}</td>
        </tr>
        """

        return make_response(resp, push_url=False)
    else:
        print("error")
        return None


if __name__ == "__main__":
    app.run()
