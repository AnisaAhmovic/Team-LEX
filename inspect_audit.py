"""Inspect local S4-10 records without exposing a public log endpoint."""
import argparse
import json

from api.audit import AuditStore, DEFAULT_AUDIT_PATH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--id", help="Interaction ID returned by the API")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--purge-expired", action="store_true")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    store = AuditStore(args.path, retention_days=args.retention_days)
    if args.purge_expired:
        print(json.dumps({"deleted": store.purge_expired()}))
    else:
        print(json.dumps(store.read(args.id, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
