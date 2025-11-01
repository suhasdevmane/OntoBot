from flask import Flask, render_template_string, jsonify
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    CORS(app)

    from blueprints.analytics_service import analytics_service

    app.register_blueprint(analytics_service, url_prefix="/analytics")

    @app.route("/")
    def index():
        html = """
        <!doctype html>
        <html lang=\"en\">
          <head>
            <meta charset=\"utf-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <title>Microservices</title>
            <link href=\"https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap\" rel=\"stylesheet\">
            <style>
              body { font-family: 'Poppins', sans-serif; background: linear-gradient(135deg, #f5f7fa, #c3cfe2); color: #444; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
              .container { max-width: 600px; background: #fff; padding: 50px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center; transition: transform 0.3s ease, box-shadow 0.3s ease; }
              .container:hover { transform: translateY(-5px); box-shadow: 0 15px 40px rgba(0,0,0,0.15); }
              h1 { font-weight: 600; color: #2c3e50; margin-bottom: 10px; }
              p { color: #7f8c8d; font-size: 1.1em; }
              .logo { width: 100px; margin-bottom: 20px; }
            </style>
          </head>
          <body>
            <div class=\"container\">
              <img src=\"https://cdn-icons-png.flaticon.com/128/17996/17996772.png\" alt=\"App Logo\" class=\"logo\">
              <h1>Microservices are Running!</h1>
              <p>Welcome to your data analytics platform. Enjoy the journey!</p>
            </div>
          </body>
        </html>
        """
        return render_template_string(html)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "microservices", "components": ["analytics"]}), 200

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=6000, debug=True)