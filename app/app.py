import os

from flask import Flask, jsonify

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "0.0.0")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")


@app.route("/")
def root():
    return jsonify(service="task-app", version=APP_VERSION, environment=ENVIRONMENT), 200


@app.route("/healthz")
def health():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
