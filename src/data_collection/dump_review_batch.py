"""
review_status 수작업 검토를 위해 welfare_candidates.csv에서 특정
senior_relevance 값에 해당하는 행을 사람이 읽기 좋은 텍스트로 배치 출력한다.
"""
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CANDIDATES_PATH = ROOT_DIR / "data" / "processed" / "welfare_candidates.csv"


def main():
    relevance = sys.argv[1]
    batch_size = int(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(CANDIDATES_PATH, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["senior_relevance"] == relevance]

    print(f"{relevance}: {len(rows)}건, 배치 크기 {batch_size}")

    for batch_idx in range(0, len(rows), batch_size):
        batch = rows[batch_idx:batch_idx + batch_size]
        out_path = out_dir / f"{relevance}_batch{batch_idx // batch_size + 1}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            for r in batch:
                f.write("=" * 80 + "\n")
                f.write(f"service_id: {r['service_id']}  source_api: {r['source_api']}\n")
                f.write(f"service_name: {r['service_name']}\n")
                f.write(f"region: {r['sido']} {r['sigungu']}\n")
                f.write(f"matched_keyword: {r['matched_keyword']}  matched_field: {r['matched_field']}\n")
                f.write(f"[target_original]\n{r['target_original']}\n")
                f.write(f"[criteria_original]\n{r['criteria_original']}\n")
                f.write(f"[support_original]\n{r['support_original']}\n")
                f.write(f"[application_original]\n{r['application_original']}\n")
                f.write(f"[contact]\n{r['contact']}\n")
        print(f"  -> {out_path} ({len(batch)}건)")


if __name__ == "__main__":
    main()
