import argparse
import json
from ir_system.service import Service
from ir_system.experiment import run_experiment

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Binary/TF/TF-IDF on held-out Cranfield queries")
    parser.add_argument("--split", choices=("DEV", "TEST"), default="TEST")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--bootstrap", type=int, default=10000)
    args = parser.parse_args()
    service = Service()
    def progress(value):
        if value["done"] % 20 == 0 or value["done"] == value["total"]:
            print(value["stage"], value["done"], "/", value["total"], flush=True)
    result = run_experiment(service.engine, service.database, service.queries, service.qrels,
                            service.manifest, split=args.split, repeats=args.repeats,
                            bootstrap=args.bootstrap, progress=progress)
    print(json.dumps(result, indent=2, ensure_ascii=False))
