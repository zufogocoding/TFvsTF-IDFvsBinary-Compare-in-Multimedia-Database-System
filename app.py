import argparse
import webbrowser
from ir_system.service import Service
from ir_system.server import make_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binary / TF / TF-IDF retrieval laboratory")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    service = Service()
    server = make_server(service, port=args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"\nIR Compare: {url}\nCtrl+C to stop.\n", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
