import os
import threading
import webbrowser

from werkzeug.serving import make_server

from app import app


def serve():
    srv = make_server("127.0.0.1", int(os.environ.get("SMART_EXPLORER_PORT", 0)), app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return "http://127.0.0.1:%d" % srv.server_port


def main():
    url = serve()
    if os.environ.get("SMART_EXPLORER_HEADLESS") == "1":
        print(url, flush=True)
        return threading.Event().wait()
    try:
        import webview
        webview.create_window("Smart Explorer", url, width=1200, height=820, min_size=(900, 640), background_color="#0b0c0e")
        webview.start()
    except Exception:
        webbrowser.open(url)
        threading.Event().wait()


if __name__ == "__main__":
    main()
