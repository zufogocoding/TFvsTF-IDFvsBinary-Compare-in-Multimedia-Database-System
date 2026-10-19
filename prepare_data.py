import argparse
import json
from ir_system.dataset import prepare

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and validate the original Cranfield collection")
    parser.add_argument("--archive", help="Import an already downloaded cran.tar.gz")
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive), indent=2, ensure_ascii=False))
