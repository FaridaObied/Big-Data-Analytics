import argparse
from engine import run


def main():
    p = argparse.ArgumentParser(description="Mini MapReduce — Word Count Engine")
    p.add_argument("--input",    default="input",  help="Folder of .txt splits")
    p.add_argument("--output",   default="output", help="Output folder")
    p.add_argument("--reducers", default=2, type=int, help="Number of reducers")
    args = p.parse_args()

    print(f"\n{'='*50}")
    print(f"  MapReduce Engine  |  reducers={args.reducers}")
    print(f"{'='*50}\n")

    data = run(args.input, args.output, args.reducers)

    print(f"Splits processed : {len(data['splits'])}")
    print(f"Splits           : {', '.join(data['splits'])}\n")

    for rid, results in data["results"].items():
        print(f"Reducer {rid}  →  output/reducer_{rid}.txt")
        for word, count in results:
            print(f"  {word:<15} {count}")
        print()

    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()